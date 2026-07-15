"""
spider_fetcher.py — 网络爬虫核心模块
=====================================
独立模块，无项目依赖，可单独测试。
负责从网页提取正文内容，支持搜索和单页抓取。
"""

import re
import os
import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class ArticleResult:
    """爬取结果"""
    title: str = ""
    url: str = ""
    text: str = ""
    platform: str = "其他"

    @property
    def length(self) -> int:
        return len(self.text)


@dataclass
class SearchResult:
    """搜索结果条目"""
    title: str
    url: str
    platform: str


class TextCourseFetcher:
    """文本学习资料爬取工具 — 聚焦博客、教程、文档等文本内容"""

    KNOWN_PLATFORMS = {
        "blog.csdn.net": "CSDN博客",
        "cnblogs.com": "博客园",
        "juejin.cn": "掘金",
        "zhuanlan.zhihu.com": "知乎专栏",
        "liaoxuefeng.com": "廖雪峰教程",
        "runoob.com": "菜鸟教程",
        "jianshu.com": "简书",
        "github.com": "GitHub",
        "w3school.com.cn": "W3School",
        "segmentfault.com": "思否",
        "imooc.com": "慕课网文章",
        "toutiao.io": "开发者头条",
        "mp.weixin.qq.com": "微信公众号",
    }

    CONTENT_SELECTORS = {
        "blog.csdn.net": "article, #content_views, .article_content",
        "cnblogs.com": "#cnblogs_post_body, .postBody, article, #mainContent",
        "juejin.cn": ".article-content, .markdown-body, article",
        "zhuanlan.zhihu.com": ".RichText, .Post-RichText, .css-376mun, article",
        "liaoxuefeng.com": ".x-wiki-content, .wiki-content, article",
        "runoob.com": ".article-body, .article, .content, main",
        "jianshu.com": ".show-content, article, .article, ._2rhmJa",
        "github.com": ".markdown-body, article, .readme, .Box-body",
        "segmentfault.com": ".article-content, article, .content",
        "baike.baidu.com": ".main-content, .content-wrapper, .para, .lemma-content, .basicInfo-item",
    }

    MAX_RESPONSE_BYTES = 2_000_000

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        retry = Retry(total=2, connect=2, read=1, backoff_factor=0.4,
                      status_forcelist=(429, 500, 502, 503, 504), allowed_methods={"GET"})
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def match_platform(self, url: str) -> str:
        """判断 URL 属于哪个已知平台"""
        for domain, label in self.KNOWN_PLATFORMS.items():
            if domain in url:
                return label
        return "其他"

    @staticmethod
    def validate_public_url(url: str) -> None:
        """Reject non-HTTP and local/private destinations before any request."""
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("只允许抓取公开的 http/https 网页")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in {80, 443}:
            raise ValueError("只允许抓取使用 80/443 端口的公开网页")
        host = parsed.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith(".localhost"):
            raise ValueError("不允许抓取本机或内网地址")
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
        except socket.gaierror as exc:
            raise ValueError("网页域名无法解析") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise ValueError("不允许抓取本机、内网或保留地址")

    def _download_html(self, url: str, timeout: int = 20) -> tuple[requests.Response, bytes]:
        current_url = url
        response = None
        for _ in range(6):
            self.validate_public_url(current_url)
            response = self.session.get(current_url, timeout=timeout, allow_redirects=False, stream=True)
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("location")
                response.close()
                if not location:
                    raise ValueError("网页重定向缺少目标地址")
                current_url = urljoin(current_url, location)
                continue
            break
        else:
            raise ValueError("网页重定向次数过多")
        if response is None:
            raise ValueError("网页请求没有返回响应")
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if content_type and not any(value in content_type for value in ("text/html", "application/xhtml+xml", "text/plain")):
            response.close()
            raise ValueError("该地址不是可解析的文本网页")
        declared = int(response.headers.get("content-length", "0") or 0)
        if declared > self.MAX_RESPONSE_BYTES:
            response.close()
            raise ValueError("网页内容超过 2MB 限制")
        chunks, total = [], 0
        try:
            for chunk in response.iter_content(64 * 1024):
                total += len(chunk)
                if total > self.MAX_RESPONSE_BYTES:
                    raise ValueError("网页内容超过 2MB 限制")
                chunks.append(chunk)
        finally:
            response.close()
        return response, b"".join(chunks)

    # ==================== 搜索 ====================

    def search(self, topic: str, max_results: int = 15) -> list[SearchResult]:
        """Search Bing first and fall back to DuckDuckGo's HTML endpoint."""
        # 直接使用用户的搜索词，不加额外后缀以免干扰搜索引擎对原始意图的理解
        query = topic

        results, errors = [], []
        try:
            response = self.session.get(
                "https://www.bing.com/search",
                params={"q": query, "setlang": "zh-cn", "count": 30},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            for item in soup.select("li.b_algo"):
                h2 = item.find("h2")
                a_tag = h2.find("a", href=True) if h2 else item.find("a", href=True)
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                url = a_tag["href"]
                if title and url.startswith("http"):
                    platform = self.match_platform(url)
                    results.append(SearchResult(title=title, url=url, platform=platform))
        except Exception as exc:
            errors.append(f"Bing: {exc}")

        if not results or not any(item.platform != "其他" for item in results):
            try:
                response = self.session.get(
                    "https://html.duckduckgo.com/html/", params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"}, timeout=15,
                )
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                duck_results = []
                for a_tag in soup.select("a.result__a[href]"):
                    title, url = a_tag.get_text(" ", strip=True), a_tag["href"]
                    if url.startswith("//"):
                        url = "https:" + url
                    parsed = urlsplit(url)
                    if "duckduckgo.com" in (parsed.hostname or "") and parsed.path.startswith("/l/"):
                        url = unquote(parse_qs(parsed.query).get("uddg", [""])[0])
                    if title and url.startswith("http"):
                        duck_results.append(SearchResult(title=title, url=url, platform=self.match_platform(url)))
                results = duck_results + results
            except Exception as exc:
                errors.append(f"DuckDuckGo: {exc}")

        seen, unique = set(), []
        for item in results:
            if item.url not in seen:
                seen.add(item.url)
                unique.append(item)
        known = [item for item in unique if item.platform != "其他"]
        other = [item for item in unique if item.platform == "其他"]
        output = (known + other)[:max_results]
        if not output and errors:
            raise RuntimeError("搜索失败: " + "; ".join(errors))
        return output

    # ==================== 正文提取 ====================

    def _extract_body(self, soup: BeautifulSoup, url: str):
        """提取正文 DOM 元素"""
        # 平台专用选择器
        for domain, selector in self.CONTENT_SELECTORS.items():
            if domain in url:
                body = soup.select_one(selector)
                if body:
                    return body

        # 通用选择器
        for sel in [
            "article", ".article", ".post", ".content", ".markdown-body",
            ".post-content", ".entry-content", "#content", ".article-content",
            "main", ".main-content", ".detail-content", ".read-content",
        ]:
            body = soup.select_one(sel)
            if body and len(body.get_text(strip=True)) > 200:
                return body

        return soup.find("body") or soup

    def _clean_body(self, body):
        """移除无关元素"""
        for tag_name in ["script", "style", "nav", "footer",
                         "noscript", "iframe", "button", "input"]:
            for t in body.find_all(tag_name):
                t.decompose()

        noise = [
            ".sidebar", ".ad", ".recommend", ".related", ".comment",
            ".footer", ".header", ".nav-bar", ".toolbar", ".catalog",
            ".share", ".copyright", ".report", ".login", ".mask",
            ".modal", ".popup", "#sidebar", "#footer", "#header",
        ]
        for cls in noise:
            for t in body.select(cls):
                t.decompose()

        return body

    def fetch(self, url: str) -> ArticleResult:
        """抓取单篇文章的正文内容"""
        try:
            resp, raw = self._download_html(url)
            soup = BeautifulSoup(raw, "html.parser")

            # --- 标题 ---
            title = ""
            for sel in ["h1", ".title", ".article-title", ".post-title",
                        '[class*="title"]', "h2"]:
                tag = soup.select_one(sel)
                if tag:
                    t = tag.get_text(strip=True)
                    if t and 5 < len(t) < 250:
                        title = t
                        break
            if not title and soup.title:
                title = soup.title.get_text(strip=True)
                title = re.sub(
                    r'\s*[-_|–—]\s*(CSDN|博客园|掘金|知乎|简书|社区|博客|专栏).*$',
                    "", title,
                )

            # --- 正文 ---
            body = self._extract_body(soup, url)
            body = self._clean_body(body)

            paragraphs = []
            for tag in body.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6",
                                       "li", "pre", "code", "blockquote", "td", "th",
                                       "span", "div"]):
                text = tag.get_text(strip=True)
                if not text or len(text) < 2:
                    continue
                # 跳过纯导航文本
                if text in ["首页", "登录", "注册", "搜索", "返回", "顶部",
                            "下一页", "上一页", "目录", "分享", "收藏", "点赞", "评论"]:
                    continue

                tag_name = tag.name
                if tag_name.startswith("h"):
                    paragraphs.append(f"\n## {text}")
                elif tag_name == "li":
                    paragraphs.append(f"- {text}")
                elif tag_name in ("pre", "code"):
                    paragraphs.append(f"\n```\n{text}\n```")
                elif tag_name == "blockquote":
                    paragraphs.append(f"> {text}")
                else:
                    paragraphs.append(text)

            article_text = "\n\n".join(paragraphs)

            # 结构化提取太少时回退到原始文本
            if len(article_text) < 300:
                raw = body.get_text(separator="\n", strip=True)
                raw = re.sub(r"\n{3,}", "\n\n", raw)
                article_text = raw

            article_text = re.sub(r"\n{4,}", "\n\n\n", article_text)

            return ArticleResult(
                title=title or url.split("/")[-1][:80],
                url=resp.url,
                text=article_text,
                platform=self.match_platform(resp.url),
            )

        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"抓取失败 ({url[:60]}): {e}") from e

    def fetch_as_markdown(self, url: str) -> str:
        """抓取并返回 Markdown 格式文本"""
        article = self.fetch(url)
        md = f"# {article.title}\n\n"
        md += f"> 来源: {article.url}  \n"
        md += f"> 平台: {article.platform}\n\n"
        md += "---\n\n"
        md += article.text
        md += "\n\n---\n*由爬虫自动抓取 · 仅用于个人学习*"
        return md

    # ==================== 保存到本地 ====================

    def save_to_disk(self, article: ArticleResult, topic: str, output_dir: str = ".") -> str:
        """将文章保存到本地目录，返回 .md 文件路径"""
        if len(article.text) < 50:
            raise ValueError(f"正文过短（{len(article.text)}字符），可能需 JS 渲染或登录")

        safe = re.sub(r'[\\/*?:"<>|]', "_", article.title or topic)
        safe = safe.strip()[:40] or topic
        folder = os.path.join(output_dir, f"学习资料_{topic}")
        os.makedirs(folder, exist_ok=True)

        md = (
            f"# {article.title}\n\n"
            f"> 来源: {article.url}\n\n"
            f"---\n\n{article.text}\n\n"
            f"---\n\n*由爬虫自动抓取 · 仅用于个人学习*\n"
        )
        md_path = os.path.join(folder, f"{safe}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)

        txt_path = os.path.join(folder, f"{safe}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"{article.title}\n来源: {article.url}\n{'=' * 60}\n\n{article.text}")

        return md_path


# ==================== 独立测试 ====================
if __name__ == "__main__":
    import sys
    fetcher = TextCourseFetcher()
    topic = sys.argv[1] if len(sys.argv) > 1 else "Python基础"
    print(f"\n🔍 搜索「{topic}」...")
    results = fetcher.search(topic, 5)
    for r in results:
        print(f"  [{r.platform}] {r.title}")
        print(f"      {r.url}")
