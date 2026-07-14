# 项目续接状态

## 2026-07-14 新增备课导出 Word/PPT

在智能备课页面，教师可将生成的教案/讲稿导出为 `.docx`，将 PPT 大纲导出为 `.pptx`。后端新增 `generated_documents` 表与 Alembic 迁移 `0008_generated_documents`，使用 `python-docx` 与 `python-pptx` 本地生成文件；前端 `LessonView` 在每个备课记录上显示对应的导出按钮。后端测试 13 项通过，前端 TypeScript 检查与生产构建通过。

## 2026-07-14 修复 PPT 导出文件仅 1 KB 问题

原 `POST /lesson-resources/{id}/export` 返回的是导出记录 JSON 元数据，前端将其作为 Blob 保存，导致下载到的 `.pptx` 实际只有 1 KB 的 JSON 内容。已将该端点改为直接返回 `FileResponse` 文件流（前端 `responseType: 'blob'` 无需调整），下载文件大小恢复正常。`GET /generated-documents/{id}/download` 仍保留作为备用下载入口。

## 2026-07-14 插件化架构重构（以备课导出为示例）

为了降低后续功能扩展成本，已将项目改造为插件化架构：

- **后端**：新增 `backend/app/api/features/` 目录和 `backend/app/api/registry.py`。每个功能模块自包含一个 `APIRouter`，通过 `register_feature_router(router)` 注册。新增后端功能只需创建 `features/<feature>.py` 并在 `registry.py` 加一行 `from .features import <feature>`。
- **前端**：新增 `frontend/src/features/` 目录和 `frontend/src/features/registry.ts`。每个功能模块可注册路由、导航项、首页卡片和动作组件。新增前端功能只需创建 `features/<feature>/` 并在 `features/index.ts` 加一行 `import './<feature>'`。
- **示例**：把备课导出（`document-export`）拆成了第一个前后端插件，`LessonView.vue` 通过动作插槽渲染导出按钮，不再硬编码导出逻辑。
- **验证**：后端 13 项测试通过，前端 `vue-tsc` 与生产构建通过。

## 2026-07-14 支持多模型服务（Ollama / OpenAI 兼容 API）

已完成 LLM / Embedding Provider 抽象：

- 新增 `backend/app/integrations/llm.py` 作为 Provider 注册中心和抽象接口。
- 改造 `backend/app/integrations/ollama.py` 为 `OllamaLLMProvider` / `OllamaEmbeddingProvider`。
- 新增 `backend/app/integrations/openai_compatible.py`，支持 OpenAI、DeepSeek、阿里云百炼、智谱 AI 等兼容 `/v1/chat/completions` 和 `/v1/embeddings` 的服务。
- 所有业务代码（备课、答疑、批改、报告、RAG）统一通过 `get_llm_provider()` / `get_embedding_provider()` 调用，不再直接依赖 Ollama。
- `backend/app/core/config.py` 和 `.env.example` 新增 `LLM_PROVIDER`、`EMBEDDING_PROVIDER`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`EMBEDDING_DIMENSION` 等配置项，保留旧 `OLLAMA_*` 配置做兼容。
- `/health/ready` 中的 `ollama` 检查改为 `llm` 和 `embedding` 两个检查。
- 新增 `backend/tests/test_llm_providers.py`（12 项测试），全部后端测试达到 25 项通过。
- 重写 `docs/07-本地启动与部署指南.md`，去掉 Windows 绝对路径强绑定，新增多模型服务配置章节（Ollama、DeepSeek、OpenAI、百炼、智谱）。

## 2026-07-14 修复课堂答疑页面无法下拉滚动

`ChatView.vue` 的聊天区域因外层容器高度固定为 `calc(100vh - 150px)` 且未考虑 header/page padding，导致内容超出视口时整页无法滚动。已调整样式：

- `main` 添加 `overflow-y: auto`，作为整页滚动兜底。
- `.chat-page` 改为 flex column 布局，`.ai-chat-shell` 使用 `flex:1` 自适应填充剩余高度。
- `.chat-main` 设置 `height:100%; overflow:hidden`，`.chat-history` 设置 `overflow-y:auto; min-height:0`，确保聊天内容在区域内可滚动。

前端生产构建通过。

## 2026-07-13 教学闭环产品化更新

已完成页面状态记忆、备课历史、多角色注册与家长多学生隔离、课程权限、知识库材料生成、薄弱画像、课堂高频问题、教师答疑修正、站内通知、家长友好报告和聊天式答疑界面。真实 MySQL 已升级到 `0007_classroom_ops`；后端测试 9 项通过，Vue TypeScript 检查与生产构建通过。备课检索已增加课程资料回退，新建课程后各业务页面重新激活时会刷新课程，注册 422 会显示具体字段原因。

更新时间：2026-07-11（Asia/Shanghai）

启动环境修复：2026-07-13

- Uvicorn reload 已限制为 `backend`，不会再扫描 `frontend/node_modules`。
- 新增 `start_backend.ps1`，自动选择 `llm_learn` Python 并使用 `python -m uvicorn`。
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

总体任务状态：**项目 MVP 已完成并通过真实服务端到端验证**。

## 已完成

- 已读取并遵循仓库根目录 `11.md` 与 `44.md`。
- 已确认 Python 环境固定使用 Conda `llm_learn`（Python 3.11.15）。
- 已在 `llm_learn` 安装：Alembic、PyMySQL、pytest。
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
conda activate llm_learn
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
