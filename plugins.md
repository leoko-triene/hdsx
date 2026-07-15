# `plugins` 源码组合模块使用说明

## 当前模型 Provider 组合模块

`plugins/model_providers` 从 `hdsx-main` 的模型切换能力提取，提供 Ollama 与 OpenAI-compatible 两套 LLM/Embedding 实现，不依赖 FastAPI、SQLAlchemy 或课程业务模型。`backend/app/integrations/model_runtime.py` 负责 `.env` 默认值、地址/维度/collection 校验和业务异常转换；原 `OllamaClient` 保留兼容外观，使 Agent 和 RAG 无需复制调用逻辑。

管理员配置由核心 API 执行 RBAC 后交给模块加密存储，API Key 不会出现在查询响应中。“模型服务”页面选择的是模块内部 Provider，不是启停源码模块。

```text
管理员模型服务页
  → admin-only API + 参数校验
  → integrations/model_runtime.py
  → plugins/model_providers
      ├→ Ollama
      └→ OpenAI-compatible API
  → Agent / RAG / 启动预热
```

该模块新增 `cryptography>=42.0` 依赖，用于以 `SECRET_KEY` 派生的 Fernet 密钥加密本地配置。Embedding 模型切换还必须同步真实向量维度和 Milvus collection；维度不匹配时核心适配层会拒绝写入。

## 1. 设计目的

这里的 `plugins` 不是运行时插件市场，也不需要管理员在页面中选择启用。它是可信协作者源码的隔离存放区：协作者把相对独立的算法、解析器或第三方服务适配放在 `Code1/plugins/<模块名>/`，主项目通过一个稳定适配层调用，以减少对核心业务文件的修改。

模块代码会和主项目运行在同一 Python 进程中，因此必须经过代码审查；它不是安全沙箱。

```text
Code1/
├─ plugins/                         # 协作者源码
│  ├─ __init__.py
│  └─ spider/                       # 当前已接入的网页爬虫
│     ├─ README.md
│     └─ spider_plugin/
│        ├─ spider_fetcher.py       # 实际搜索与正文提取引擎
│        ├─ spider_tool.py
│        └─ ...
└─ backend/app/integrations/web/
   └─ crawler.py                    # 主项目稳定适配层
```

旧的 `Code1/p` 组合目录已经撤销，不应再向其中添加模块。

## 2. 当前真实示例：`plugins/spider`

主项目没有复制爬虫实现，也没有挂载协作者提供的直接入库路由。`backend/app/integrations/web/crawler.py` 只负责：

1. 定位项目根目录并导入 `plugins.spider.TextCourseFetcher`。
2. 把同步 `requests` 调用放入工作线程，避免阻塞 FastAPI 事件循环。
3. 将结果转换为主项目稳定的 `WebArticleCrawler` / `WebArticle` 契约。
4. 把抓取错误转换为统一业务错误。

协作者爬虫已补充 HTTP/HTTPS、80/443 端口、DNS 公网地址、逐跳重定向、文本类型和 2MB 响应限制。它不执行 JavaScript、不携带登录态，也不尝试绕过付费墙或反爬限制。

### 知识库调用链

```text
教师搜索或输入 URL
  → WebImportService
  → WebArticleCrawler 适配层
  → plugins/spider/TextCourseFetcher
  → 待确认 Markdown 预览
  → 教师确认
  → MySQL Document/Chunk + Milvus
```

课程权限、SHA-256 去重、临时草稿、确认入库、事务、文件存储、分块、Embedding 和 Milvus 索引仍由主项目负责。协作者爬虫不直接写数据库。

### 课堂答疑调用链

```text
学生提问
  → 课程知识库混合检索
  → 证据少于两个片段？
      ├─ 否：只使用课程资料
      └─ 是：plugins/spider 搜索并抓取最多两篇公开网页
  → Grounded QA Prompt（网页正文按不可信资料处理）
  → 返回课程引用与可点击网络来源
```

网络补充只服务当前回答，不会自动写入课程知识库。网页搜索或抓取失败时自动降级，仍可使用已有课程证据；两类来源都为空时提示证据不足。

## 3. 添加新的协作模块

以 OCR 模块为例：

```text
plugins/
└─ image_ocr/
   ├─ __init__.py
   ├─ engine.py
   ├─ README.md
   └─ tests/
```

推荐流程：

1. 协作者只在 `plugins/image_ocr` 内实现核心能力和独立测试。
2. `__init__.py` 只导出少量稳定接口，不暴露内部辅助函数。
3. 项目负责人在 `backend/app/integrations/ocr/` 添加薄适配层。
4. Service 调用适配层，并继续负责身份权限、事务、幂等、审计和业务状态。
5. 如果需要 Agent 调用，再注册有版本、输入 Schema 和只读/写入属性的 Tool；不要让模型直接导入模块。
6. 在现有业务页面增加入口，不创建与业务割裂的“插件页面”。

稳定接口示例：

```python
# plugins/image_ocr/__init__.py
from .engine import OCRResult, recognize

__all__ = ["OCRResult", "recognize"]
```

```python
# backend/app/integrations/ocr/client.py
from plugins.image_ocr import recognize

def recognize_upload(path: str):
    return recognize(path)
```

## 4. 模块边界

协作模块可以负责：

- 算法和数据转换；
- 第三方公开接口或文件格式适配；
- 明确输入输出的无状态处理；
- 自己能力范围内的单元测试。

核心项目必须负责：

- 登录、RBAC 和课程归属；
- MySQL Session、事务和 Alembic；
- Milvus 与业务数据一致性；
- 文件路径、配额、审计和错误响应；
- Agent/Skill/Prompt/Tool 契约；
- 前端业务流程。

禁止事项：

- 在模块内建立 SQLite 或第二套业务数据库；
- 调用 `create_all` 或维护独立迁移链；
- 硬编码密码、令牌、机器绝对路径；
- 接收模型生成的自由 SQL 或系统命令；
- 绕过 Service 直接写课程、作业、成绩或知识库；
- 在未说明的情况下自动联网下载模型或依赖。

## 5. 依赖与安全

新依赖必须写入模块 README，并由项目负责人审核后加入根 `pyproject.toml`。当前爬虫需要：

```toml
"requests>=2.31"
"beautifulsoup4>=4.12"
```

网络模块必须限制协议、端口、DNS/IP、重定向、超时、响应类型与大小。外部正文一律按不可信数据处理，不能覆盖系统 Prompt。

## 6. 验证和 Git

至少完成：

```powershell
conda activate program-hd
cd Code1
python -m pytest -q

cd frontend
pnpm test
pnpm build
```

提交时应包含：模块源码、稳定适配层、业务接线、契约测试、README、`PROJECT_STATUS.md` 和受影响的 `docs/*.md`。推荐提交说明：

```text
feat: 接入协作者OCR源码模块

- 在 plugins/image_ocr 增加稳定识别接口
- 通过 integrations/ocr 接入上传流程
- 保留主项目权限、事务和审计边界
- 补充回归测试与文档
```
