import asyncio
from types import SimpleNamespace

from app.services.web_supplement import WebSupplementService


class FakeCrawler:
    async def search(self, query, limit):
        return [
            {"title": "资料甲", "url": "https://example.com/a", "platform": "示例站"},
            {"title": "资料乙", "url": "https://example.com/b", "platform": "示例站"},
        ]

    async def fetch(self, url):
        suffix = url.rsplit("/", 1)[-1]
        return SimpleNamespace(title=f"网络资料{suffix}", resolved_url=url, text=f"{suffix} 的知识点正文" * 20)


def test_web_supplement_is_bounded_and_traceable():
    supplement = asyncio.run(WebSupplementService(lambda: FakeCrawler()).collect("知识点 装饰器", max_articles=1))
    assert len(supplement.citations) == 1
    assert supplement.citations[0]["source_type"] == "web"
    assert supplement.citations[0]["source_url"] == "https://example.com/a"
    assert "网络资料1" in supplement.context
