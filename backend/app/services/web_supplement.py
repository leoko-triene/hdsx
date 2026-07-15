"""Read-only web knowledge supplementation for grounded classroom Q&A."""

import asyncio
from dataclasses import dataclass, field
from typing import Callable

from app.integrations.web import WebArticleCrawler


@dataclass(slots=True)
class WebKnowledgeSupplement:
    context: str = ""
    citations: list[dict] = field(default_factory=list)


class WebSupplementService:
    """Search and fetch a small, bounded set of public learning pages."""

    def __init__(self, crawler_factory: Callable[[], WebArticleCrawler] = WebArticleCrawler):
        self.crawler_factory = crawler_factory

    async def collect(self, query: str, max_articles: int = 2) -> WebKnowledgeSupplement:
        max_articles = max(1, min(2, max_articles))
        try:
            return await asyncio.wait_for(self._collect(query, max_articles), timeout=10)
        except (asyncio.TimeoutError, Exception):
            return WebKnowledgeSupplement()

    async def _collect(self, query: str, max_articles: int) -> WebKnowledgeSupplement:
        try:
            results = await asyncio.wait_for(self.crawler_factory().search(query, 10), timeout=5)
        except (asyncio.TimeoutError, Exception):
            return WebKnowledgeSupplement()

        async def fetch(item: dict):
            try:
                article = await asyncio.wait_for(self.crawler_factory().fetch(item["url"]), timeout=5)
                if len(article.text) < 100:
                    return None
                keywords = [k for k in query.split() if len(k) >= 2]
                if keywords and not any(k in article.text[:500] for k in keywords):
                    return None
                return item, article
            except (asyncio.TimeoutError, Exception):
                return None

        fetched = await asyncio.gather(*(fetch(item) for item in results))
        sections, citations = [], []
        for value in fetched:
            if not value or len(sections) >= max_articles:
                continue
            item, article = value
            index = len(sections) + 1
            sections.append(
                f"[网络资料{index}|{article.title}|{article.resolved_url}]\n"
                f"{article.text[:6000]}"
            )
            citations.append({
                "chunk_id": None, "document_id": None, "chunk_index": 0,
                "filename": article.title, "source_url": article.resolved_url,
                "source_type": "web", "platform": item.get("platform", "网络资料"),
            })
        return WebKnowledgeSupplement(context="\n\n".join(sections), citations=citations)
