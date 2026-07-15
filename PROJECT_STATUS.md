# 项目续接状态

## 2026-07-15 知识点图谱合并

- 从 `code/hdsx` 的 `7e0532f` 提交选择性移植“知识点图谱”功能，保留 Code1 已有的 `Question.explanation`、题型计数、`MasterySnapshot` 掌握度和版本化 Agent Runtime。
- 新增 `knowledge_point_relations`、`knowledge_point_graphs` 两张表，Alembic 升级到 `0011_knowledge_graph`（基于 `0010_question_explanation`）。
- 新增 `KnowledgeGraphAgent` 及 `knowledge_graph_extraction@1.0.0` Skill / Prompt，真正接入 Agent Runtime。
- 教师/管理员可从“知识点图谱”按课程生成、查看、审核知识图谱；ECharts 力导向图渲染知识点与前置/相关/包含关系。
- 题目编辑新增 `KnowledgePointSelector`，支持把题目关联到课程知识点。
- 学生可在“我的知识点掌握度”按课程查看掌握度、薄弱项和推荐学习路径；数据复用现有 `MasterySnapshot`，避免多次提交重复计数。
- 知识图谱 API 使用 Code1 现有 `owned_course` / `visible_course` 校验，未加入课程、非负责人、未绑定家长均无法访问。
- 重新生成时版本号递增；模型返回空知识点时回滚事务并返回明确错误，不会创建空图谱。
- 验证：后端 42 项测试通过（新增 4 项知识图谱单测），Agent 契约校验通过，ruff 无告警，前端生产构建通过（含 echarts 动态加载）。

## 2026-07-14 课程路由、检索筛选与课程学情更新

- Vue `KeepAlive` 改为按完整路由分别缓存，同一组件的不同课程不再复用首次课程状态；作业列表实例不会在进入详情前被改成详情状态，面包屑返回恢复正常。
- 作业中心、课堂运营、学情分析和教师学习报告课程页统一显示固定课程名称及“返回课程列表”；智能备课收藏夹面包屑中的“智能备课”恢复可点击。
- 课程卡片桌面端每行最多 3 个，窄屏自适应 2/1 列；按钮、状态和徽标统一禁止文字换行。
- 课程中心进入知识库时按 `course` 查询参数创建独立缓存实例，直接显示所点课程。
- RAG 结果增加正相关、最短内容及单文档数量限制；未配置 BGE 时保留融合分数筛选结果，而不是把全部候选误判为零分。
- 学生课程学情新增全部已发布作业完成/未完成、逾期、最新得分率、课堂提问和需教师关注回答的综合分析；知识点掌握度按课程隔离。
- 本轮不修改 MySQL 表结构，迁移版本仍为 `0009_submission_attempts`。
- 验证：`program-hd` 后端 36 项测试通过，前端 Markdown 2 项测试通过，Vite 生产构建 140 模块通过；Vue TypeScript 独立检查的扩展权限审核连续超时，尚未取得结果。

## 2026-07-14 知识库文档预览与管理员模型 Provider 更新

- 知识库文件新增预览；课程成员可查看已解析内容，Markdown/网页来源安全渲染，普通解析文本保留换行，单次预览限制 10 万字符。
- 参考 `hdsx-main`，在 `plugins/model_providers` 提取独立于业务框架的 Ollama/OpenAI-compatible LLM 与 Embedding 契约、工厂及加密存储。
- 新增仅管理员可用的“模型服务”页面及查询、连接测试、保存接口；API Key 只加密落盘，不回传明文。
- Agent、RAG、作业、批改、备课、答疑和启动预热统一经过运行时 Provider；Milvus collection 与维度随配置读取，维度冲突时明确拒绝。
- 本轮不修改 MySQL 表结构，迁移版本仍为 `0009_submission_attempts`。

## 2026-07-14 plugins 爬虫、联网答疑、模型预热与页面布局更新

- 源码组合目录由 `Code1/p` 统一迁移为 `Code1/plugins`；撤下旧 `p/course_web_crawler`，实际搜索与正文提取改用协作者提供的 `plugins/spider/TextCourseFetcher`，核心项目仅保留异步与错误契约适配层。
- `plugins/spider` 增加公开 HTTP/HTTPS、80/443 端口、DNS/IP、逐跳重定向、文本响应和 2MB 上限校验；知识库仍执行“抓取预览 → 人工确认 → 标准入库”。
- 课堂答疑优先使用课程知识库；证据少于两个片段时，通过爬虫补充最多两篇公开网页，网页不会自动入库，回答中显示可点击的网络引用，失败时安全降级。
- Grounded QA Skill 升级到 `1.1.0`，白名单增加只读 `search_web_knowledge` Tool，网页正文继续按不可信资料隔离提示注入。
- 智能备课收藏按钮只修改收藏状态，独立“★ 收藏夹”按钮负责进入收藏页；历史四个操作桌面端等宽单行排列，标题统一使用填写的章节或主题。
- 知识库页面在标题说明下方使用可横向滚动的课程标签，当前课程高亮；主体左侧为上传/爬虫，右侧为知识检索/知识库文件。
- FastAPI 启动阶段预载 Ollama 对话、Embedding 和已配置的本地 BGE 重排模型；Ollama 默认 `keep_alive=-1`，预热结果进入 readiness，严格模式可阻止预热失败的实例启动。
- 验证：后端 27 项测试、模型真实预热、Markdown 2 项前端单测、Vue TypeScript 检查和 136 模块生产构建通过；本轮不涉及数据库迁移，MySQL 仍为 `0009_submission_attempts`。

## 2026-07-14 源码组合模块与交互优化更新

- 根据协作方式澄清，撤下运行时可选插件、动态导航和 iframe 宿主；该阶段曾使用 `p/<模块>/`，现已按后续要求迁移为 `plugins/<模块>/` 源码组合机制。
- 该阶段的 `p/course_web_crawler` 已由后续 `plugins/spider` 实现替换；权限、事务、确认入库和 RAG 索引始终由核心项目控制。
- 重写 `plugins.md`，说明 p 目录模块边界、稳定接口、核心接线、数据库与安全约束以及 Git 协作流程。
- 作业中心、课堂运营、学情分析和报告的课程入口卡片加深颜色，整张卡片均可点击进入。
- 课堂答疑把课程选择移到侧栏“新对话”上方，支持修改已有会话名称。
- 知识库待确认与历史抓取增加安全渲染 Markdown 预览、待确认记录入库和所有状态记录删除按钮；删除已确认抓取记录不会连带删除已入库文档。
- 智能备课生成后和历史预览均进入独立页面，Markdown 经转义后渲染标题、列表、代码块、引用、表格和安全链接。
- 从普通备课历史进入时导航为“工作台 > 智能备课 > 文件名”；仅从收藏页进入时为“工作台 > 智能备课 > 收藏 > 文件名”。
- 验证：后端 24 项测试、Markdown 2 项前端单测、Vue TypeScript 检查和 135 模块生产构建通过；本次不涉及数据库结构迁移。

## 2026-07-14 结构化输出、课程分层导航与可维护性更新

- 批改、作业材料和家长报告统一使用 JSON Schema 约束、Pydantic 契约校验与确定性兜底；模型返回非 JSON 或缺字段时不再因格式导致请求失败。
- 作业支持多次提交，每次提交独立保存 `attempt_no` 并立即批改；MySQL 已升级到 `0009_submission_attempts`。
- 知识库支持删除指定文档并清理数据库分块、文件和可用的 Milvus 向量；作业与课程使用归档删除，保留历史成绩审计数据。
- 新建课程的名称、学科、学段和描述均为必填项，负责人可修改、删除课程。
- 作业中心、课堂运营、学情分析、学习报告改为先选课程再进入，并显示“工作台 > 模块 > 课程 > 作业”的层级导航。
- 智能备课增加收藏页及预览、下载、取消收藏、删除操作；历史操作按钮网格化，收藏黄色、删除红色。
- 左侧任务栏在桌面端固定于视口，正文滚动不会带动任务栏。
- 验证：真实 MySQL 迁移到 `0009`；后端 `22 passed`；Vue TypeScript 检查通过；生产构建 `130 modules transformed`。

## 2026-07-14 网络资料确认入库更新

- 参考 `course_spider.py` 实现关键词搜索、直接 URL 抓取、正文清洗和来源保留。
- 网页内容先保存到 `web_import_drafts`，必须由课程负责人确认后才生成 Document、分块、Embedding 和 Milvus 索引；草稿 24 小时过期并支持拒绝。
- 增加 SSRF 防护、DNS/IP 校验、80/443 端口限制、逐跳重定向校验、robots.txt、2MB 响应和 5 万字符限制。
- MCP 白名单新增 `preview_web_source@1.0.0`，只能生成待确认预览，不能替用户确认入库。
- 备课、作业、问答和标准答案 Prompt 升级至 `1.1.0`，明确把网页资料内命令视为不可信正文。
- MySQL 已从 `0007_classroom_ops` 升级到 `0008_web_imports`；该阶段后端 `18 passed`，Vue 生产构建 `125 modules transformed`。

## 2026-07-13 Agent 平台与目录对齐更新

- 已补齐并实际接入 `common`、`agents`、`prompts`、`skills`、`tools`、`mcp` 以及 RAG 子模块，不再把核心提示词和编排全部集中在 `services/agents.py`。
- 已建立 6 类 Skill、6 个领域 Agent、10 个保留历史版本的 Prompt，以及 5 个只读 Tool + 1 个需人工确认的网页预览 Tool；备课、作业生成、批改、标准答案、答疑、学习报告均通过统一 Runtime。
- 已实现站内认证 MCP JSON-RPC 安全网关和默认禁用的远端 MCP 客户端；所有 Tool 复用课程/学生数据权限，模型不能执行自由 SQL。
- RAG 已拆分 loader、cleaner、splitter、embedding、index、fusion、deduplicator、filter、reranker、context builder、citation 和 pipeline。
- 前端新增公共组件、composable、类型目录和管理员“Agent 能力中心”。
- 验证：后端 `16 passed`；Vue TypeScript 检查通过；Vite 生产构建 `124 modules transformed`。

## 2026-07-13 教学闭环产品化更新

已完成页面状态记忆、备课文本与历史预览、多角色注册与家长多学生隔离、课程权限、知识库材料生成、薄弱画像、课堂高频问题、教师答疑修正、站内通知、家长友好报告和聊天式答疑界面。真实 MySQL 已升级到 `0007_classroom_ops`；后端自动化测试通过，Vue TypeScript 检查与生产构建通过。备课按资源类型输出 Markdown 文本，只使用相关性通过的知识证据；作业材料使用 JSON Schema、降级解析并支持最多 10 份参考文件；全局顶部显示当前位置和固定退出入口。

更新时间：2026-07-11（Asia/Shanghai）

启动环境修复：2026-07-13

- Uvicorn reload 已限制为 `backend`，不会再扫描 `frontend/node_modules`。
- 新增 `start_backend.ps1`，自动选择 `program-hd` Python 并使用 `python -m uvicorn`。
- Windows Installer 策略阻止系统 Node 修复，因此已配置项目便携 Node.js 24.18.0。
- 项目便携 npm 版本 11.16.0、pnpm 版本 11.7.0。
- 新增 `start_frontend.ps1` 和 `bin/node.cmd`、`bin/npm.cmd`、`bin/pnpm.cmd`。
- 后端 reload 启动和前端 Vite 开发服务器均已实际验证成功。

产品化功能迭代：2026-07-13

- 知识库支持最多 20 个文件批量上传和逐文件结果。
- 使用内容 SHA-256 查重；MySQL `0003_document_dedup` 提供并发唯一约束。
- 知识库显示当前文件、分类、分块、状态和上传时间。
- 导航、路由、总览和操作按教师/学生/家长/管理员角色区分。
- 总览功能卡片可以直接跳转到对应页面。
- 作业中心已拆分教师创建/发布/提交队列/批改复核与学生列表/详情/填写/结果。
- 作业列表显示标题、课程、分值、题数、提交数、截止时间和个人状态。
- 学生作业接口不返回标准答案和 rubric。
- 新增课程学生列表，报告和学情页面不再要求教师手填学生 ID。
- 新增 `start_production.ps1`，FastAPI 可同源托管 Vue 生产包。
- 后端测试 9 项通过，Vue 生产构建通过，真实产品功能脚本验证通过。

账号与课程成员迭代：2026-07-13

- 新增学生公开注册、个人资料修改和当前密码校验后的改密功能。
- 新增课程多负责人 `course_managers`，历史 owner 已自动迁移。
- 新增课程成员 `course_members` 和学生加入申请/负责人审批流程。
- 新增 CSV 批量导入学生，支持创建新学生和加入已有学生。
- 学生只能看到和访问正式加入课程的知识库、作业和答疑。
- 作业中心按课程分组；课堂答疑使用课程名称选择器。
- 新增账号设置、注册、课程发现、审批、导入和负责人管理界面。
- Alembic 已升级到 `0004_course_membership`。
- 真实验证结果：审批前访问 403、审批后 200、多负责人 2、批量导入成功。

## 当前阶段

总体任务状态：**产品闭环与 Agent 平台第一版已完成并通过自动化及真实服务验证**。

## 已完成

- 已读取并遵循仓库根目录 `11.md` 与 `44.md`。
- 已确认 Python 环境固定使用 Conda `program-hd`（Python 3.11.15）。
- 已在 `program-hd` 安装：Alembic、PyMySQL、pytest。
- 已确认 Ollama 可访问：
  - `qwen2.5:latest`
  - `embeddinggemma:latest`，向量维度 768
- 已确认本地 Qwen2-0.5B 与 BGE reranker 路径存在。
- 已完成 FastAPI + MySQL + SQLAlchemy + Alembic 后端骨架。
- 已完成用户/JWT/RBAC、课程、章节、知识点、文档上传和分块。
- 已完成 TXT/MD/PDF/DOCX 解析入口、关键词检索、引用式问答。
- 已完成 Ollama 备课、客观题判分、主观题辅助评分、教师复核接口。
- 已完成掌握度查询和报告生成接口。
- 已完成 Vue 3 页面：登录、总览、课程、知识库、备课、作业、答疑、学情、报告。
- 已固定前端依赖版本并生成 `pnpm-lock.yaml`。
- 已完成 MySQL 初始化 SQL、Alembic 基线迁移、环境检查和演示数据脚本。
- 已完成六份中文 Markdown 文档，位于 `docs/`。

## 已通过验证

- 后端：`5 passed in 2.06s`。
- 前端：TypeScript 检查通过。
- 前端 Vite 生产构建通过：103 modules transformed，产物位于 `frontend/dist/`。

## 当前环境与验证结果

- MySQL 使用官方 `mysql:8.4` 容器 `edu-mysql`，实际版本 8.4.10，数据位于 `D:\Docker\mysql`。
- Alembic 已升级到 `0002_learning_family`，真实 MySQL 已创建全部当前数据表。
- Milvus `edu_chunks_dev` 已创建并完成真实向量写入/召回。
- 已实现 RRF 融合与本地 BGE CPU 重排序。
- 已完成真实 MySQL + Milvus + Ollama + BGE 的端到端教学闭环测试。
- 掌握度、学习路径、家长授权、报告发布均已验证落库。
- SSE、Celery/Redis、完整班级管理 UI 属于后续工程增强，不阻塞 MVP。

## 重启后的第一步

1. 读取本文件、`AGENTS.md`、根目录 `44.md`。
2. 执行：

```powershell
conda activate program-hd
cd D:\class\Season4_5\hdsx-d\Code1
python scripts\check_environment.py
```

3. 若服务未启动，启动 Docker Desktop、Ollama，并执行 `docker start edu-mysql`；Milvus 使用已有容器。
4. 运行 `alembic upgrade head` 检查迁移，再运行测试。
5. 启动后端与前端继续功能增强。

## 计划状态

- [x] 环境和 Code1 审计
- [x] 项目骨架、配置、MySQL 数据层和 FastAPI 核心模块
- [x] 核心业务/RAG/Agent MVP
- [x] Vue 前端与 API 接入
- [x] 真实 MySQL/Milvus、迁移、演示数据和端到端验证收尾
- [x] 六份中文项目文档
