# Spider 源码组合模块

本目录保存协作者提供的课程资料爬虫源码，已经直接组合进主项目，不是运行时可选插件，也不需要复制到 `backend/app`。

## 主项目接入

稳定调用入口是：

```text
backend/app/integrations/web/crawler.py
  → plugins/spider/spider_plugin/TextCourseFetcher
```

知识库的搜索、抓取预览、确认入库继续使用原 `/api/v1/courses/{course_id}/web-imports/*` 接口。课堂答疑在课程知识库证据不足时，也会通过同一爬虫补充最多两篇公开网页并返回来源，但不会自动入库。

`spider_router.py` 保留作为协作者原始参考实现，主应用不会挂载其中的直接入库路由，以确保所有知识库写入都经过已有的权限、预览确认、事务、去重和 RAG 索引流程。

## 文件

```text
spider/
├─ __init__.py
├─ README.md
└─ spider_plugin/
   ├─ __init__.py
   ├─ spider_fetcher.py   # 当前实际使用的搜索与抓取引擎
   ├─ spider_tool.py      # 命令行/脚本调用
   ├─ spider_router.py    # 原始参考路由，主应用不挂载
   └─ standalone_dev.py  # 独立调试服务
```

## 安全边界

`TextCourseFetcher` 当前执行：

- 只允许公开 HTTP/HTTPS 页面；
- 只允许 80/443 端口；
- DNS 结果不得是本机、内网、链路本地或保留地址；
- 每次重定向前重新校验目标，最多 5 次；
- 只接受 HTML/XHTML/纯文本；
- 响应正文最多 2MB；
- 不执行 JavaScript、不携带登录态。

网页内容属于不可信外部数据，不能覆盖系统 Prompt，也不应被当作已由教师审核的事实。

## 依赖

依赖已写入项目根 `pyproject.toml`：

```toml
"requests>=2.31"
"beautifulsoup4>=4.12"
```

## 独立调用

```python
from plugins.spider import TextCourseFetcher

fetcher = TextCourseFetcher()
results = fetcher.search("Python 装饰器", 5)
article = fetcher.fetch(results[0].url)
print(article.title, article.length)
```

在后端业务代码中不要直接使用上述接口，应依赖 `app.integrations.web.WebArticleCrawler`，以获得异步适配和统一错误响应。

## 验证

```powershell
conda activate program-hd
cd Code1
python -m pytest backend/tests/test_web_crawler.py backend/tests/test_web_supplement.py -q
```
