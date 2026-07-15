# AI 教育智能备课与个性化学习辅导智能体

课程型功能现在按完整路由隔离页面缓存：从课程卡片进入作业、课堂运营、学情分析、学习报告、知识库或知识点图谱时，会直接打开所选课程，不再残留第一次进入的课程。课程页顶部固定显示课程名称和返回课程列表按钮；桌面课程卡片每行最多 3 个，所有按钮/徽标文字保持单行。

知识检索结果经过重排正相关、内容长度和来源多样性筛选。学生学情分析同时统计课程全部已发布作业（已完成、未完成和逾期）、最新提交得分率、课堂提问次数及低置信度/需教师关注回答，并生成可解释的课程状况说明。

知识库文件现支持按课程权限预览：Markdown/网页资料渲染显示，其他解析文本保留原始换行。管理员可在“模型服务”页面分别配置 Ollama 或 OpenAI-compatible 的 LLM 与 Embedding；实现位于源码组合模块 `plugins/model_providers`，现有 Agent、RAG、备课、作业、批改和启动预热均统一使用运行时 Provider。

模型 API Key 使用 `SECRET_KEY` 派生密钥加密到 `storage/system/model-providers.enc`，查询接口不会返回明文。切换 Embedding 时必须填写真实维度；若维度变化，请使用新的 Milvus collection 名称并为既有资料重新建立向量索引。未保存管理员配置时继续使用 `.env` 的 Ollama 默认值。

当前版本进一步提供可恢复的答疑会话与备课历史、多角色注册和家长多学生绑定、基于知识库的作业材料生成、薄弱知识画像、知识点图谱、课堂高频问题、教师修正 AI 回答、站内通知及家长友好学习报告。教师可查看全部课程信息，但教学操作严格限制在其负责课程。

作业中心现支持严格契约解析 AI 材料、多选与判断题完整选项、已添加题目再次编辑、空标准答案由课程知识库自动补充，以及学生多次提交后逐次立即批改并显示标准答案。批改、材料生成和学习报告均使用 JSON Schema、Pydantic 校验和确定性兜底，模型格式异常不会再直接造成 5xx。

智能备课按完整教案、课堂讲稿、PPT 提纲和课堂练习分别生成可阅读的 Markdown 文本，支持历史预览与 Markdown 下载。全局顶部导航会显示当前位置，并固定提供退出登录入口；作业返回按钮采用醒目样式。作业材料生成使用 Ollama JSON Schema、容错归一化和文本降级，避免模型格式波动导致整批失败。

备课检索采用“整句命中优先、混合检索与 BGE 相关性阈值兜底”，无相关证据时拒绝生成，避免无论主题都引用同一份 Vue 等资料。作业材料生成可同时选择最多 10 份 ready 参考文件，并按文件均衡抽取上下文。

后端已按 `44.md` 补齐并接入 `agents`、`common`、`prompts`、`skills`、`tools`、`mcp` 与分层 RAG 结构。六类 Skill 使用版本化 Prompt；六个只读 Tool 和一个网页预览 Tool 通过白名单注册并复用权限；内部 MCP 网关支持版本协商、`ping`、`tools/list`、`tools/call`，远端 MCP 默认关闭并受主机白名单限制。管理员可从“Agent 能力”页面检查当前实际注册的版本、变量、工具和 MCP 状态。

知识库现在使用 `plugins/spider` 中的协作者爬虫：课程负责人可以按主题搜索或粘贴网页 URL，查看正文 Markdown 预览，明确确认后才写入知识库、分块并向量化。系统阻止内网地址、非 80/443 端口、危险重定向、非文本响应和超大页面。课堂答疑在课程证据不足时还可临时补充最多两篇公开网页，并提供可点击来源；网络补充不会自动写入知识库。

华迪实训小组项目。

协作者可以把算法、解析器或第三方服务适配放在根目录 `plugins/<模块名>/`，项目负责人再通过 `backend/app/integrations` 的薄适配层组合进知识库、作业或报告等原有功能。它不是运行时可选插件，也不会出现单独插件页面；完整边界、示例和 Git 协作方式见 [`plugins.md`](plugins.md)。当前真实示例是 `plugins/spider`。

课程型模块先显示颜色加深的课程卡片，整张卡片可直接点击进入。课堂答疑支持修改会话名称，课程选择位于“新对话”上方。知识库网页抓取历史支持 Markdown 渲染预览、待确认入库和删除记录。

智能备课 Markdown 使用独立渲染预览页。历史标题取填写的章节或主题，收藏按钮只切换状态，独立“★ 收藏夹”按钮进入收藏页，历史四项操作在桌面端等宽单行排列。只有从收藏页点击预览时，导航才显示收藏层级。知识库页面采用横向课程标签和左右双栏工作区。

本目录是依据仓库根目录 `11.md` 与 `44.md` 实现的项目。后端采用 FastAPI + MySQL + Milvus，前端采用 Vue 3；默认使用 Ollama 的 `qwen2.5:latest` 与 `embeddinggemma:latest`，管理员也可以切换为其他本地模型或 API 模型。

后端启动时默认预载 Ollama 对话模型、Embedding 模型以及已配置的本地 BGE 重排模型，Ollama 通过 `OLLAMA_KEEP_ALIVE=-1` 常驻内存/显存。严格预热默认开启，失败会阻止服务接受请求；如需仅诊断外部服务，可临时设 `MODEL_WARMUP_STRICT=false`。系统不会自动下载缺失模型。

## 环境

- Conda：`program-hd`（Python 3.11）
- MySQL：官方 `mysql:8.4` Docker 容器 `edu-mysql`，数据位于 `D:\Docker\mysql`
- Milvus：现有 Docker 服务，默认端口 19530
- Ollama：默认 `http://localhost:11434`

## 快速开始

1. 复制 `.env.example` 为 `.env`，填写 MySQL 账号。
2. 启动已配置的 `edu-mysql` 容器；首次自行部署时可执行 `database/init_mysql.sql`。
3. 激活环境：`conda activate program-hd`。
4. 执行迁移：`cd backend && alembic upgrade head`。
5. 启动后端：`powershell -ExecutionPolicy Bypass -File .\start_backend.ps1`。脚本将 reload 范围限制在 `backend`，避免扫描前端依赖目录。
6. 启动前端：`powershell -ExecutionPolicy Bypass -File .\start_frontend.ps1`。

当前数据库迁移版本为 `0011_knowledge_graph`。升级后可使用知识点图谱、网页确认入库以及作业多次提交记录。

作业中心、课堂运营、学情分析和教师学习报告采用“先选课程、再进入课程功能”的路由；面包屑会继续显示课程和具体作业。课程必填信息可维护，课程/作业可归档删除，知识库文档可单独删除。智能备课收藏页提供预览、下载、取消收藏和删除。桌面端左侧任务栏固定在视口中。

也可以手动启动后端：

```powershell
uvicorn app.main:app --reload --reload-dir backend --app-dir backend
```

### 前端运行环境修复

本机 Windows Installer 策略可能阻止系统级 Node 安装，因此项目使用便携 Node.js 24 LTS，位于 `.runtime/node-v24.18.0-win-x64`。启动脚本会自动设置临时 PATH 和项目级 Corepack 缓存，不要求全局 `node`、`npm` 或 `pnpm`。

可以在 `Code1` 目录直接验证：

```powershell
.\bin\node.cmd --version
.\bin\npm.cmd --version
.\bin\pnpm.cmd --version
```

不要再执行 `npm install -g pnpm`；直接运行 `start_frontend.ps1` 即可。

## 单端口部署运行

完成配置和数据库迁移后，可以由 FastAPI 同源托管 Vue 生产包：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_production.ps1
```

访问 `http://127.0.0.1:8000`。该模式不启用 reload，也不需要单独运行 Vite。公网部署时仍应在前方配置 Nginx/Caddy HTTPS、防火墙、正式随机密钥、备份和域名。

后端文档：http://127.0.0.1:8000/docs

## 演示范围

已实现身份与课程、文档入库、Milvus 向量召回、MySQL 关键词召回、RRF 融合、BGE 重排、备课、作业批改、教师复核、问答、掌握度、学习路径、家长授权和报告发布，并提供自动化与真实端到端测试。外部服务不可用时会返回明确错误，不会静默切换到 SQLite 或伪造模型结果。

Agent 采用确定性编排：业务服务先通过受控查询获得证据，再由对应 Domain Agent 运行指定 Skill 和 Prompt。模型本身不能选择任意工具、执行 SQL 或绕过课程权限。新增能力应同时增加 Skill manifest、`SKILL.md`、版本化 Prompt、Schema 和测试。

## 项目文档

六份交付文档位于 `docs/`：软件需求规约、项目开发计划、数据库设计说明书、系统架构设计说明书、测试用例、用户使用手册。
