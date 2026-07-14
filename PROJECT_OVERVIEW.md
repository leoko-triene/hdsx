# AI 教育智能备课与个性化学习辅导智能体 —— 项目概览与开发指南

## 1. 项目简介

本项目是一个面向 K12/高等教育场景的 **AI 教学智能体系统**，核心定位是：

- **教师端**：智能备课、课程知识库管理、作业创建与批改复核、课堂高频问题分析、学生薄弱知识画像。
- **学生端**：加入课程、查看作业、提交作业、即时获得批改与标准答案、答疑会话、学习报告。
- **家长端**：绑定多名学生、接收站内通知、查看家长友好的学习报告。
- **管理员/多角色**：支持多角色注册、课程多负责人、课程成员审批、CSV 批量导入学生。

项目当前状态为 **MVP 已完成**，后端使用 FastAPI + MySQL + Milvus，前端使用 Vue 3，本地大模型通过 Ollama 调用。

---

## 2. 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| Python 3.11（Conda 环境 `llm_learn`） | 主开发语言 |
| FastAPI + Uvicorn | Web API 与 ASGI 服务 |
| SQLAlchemy 2.x | ORM |
| Alembic | 数据库迁移 |
| MySQL 8.4（Docker 容器 `edu-mysql`） | 业务数据库 |
| Milvus | 向量存储与召回 |
| Ollama | 本地 LLM / Embedding 服务 |
| PyMySQL / python-multipart / httpx / pydantic | 数据库连接、文件上传、HTTP 调用、校验 |

### 前端

| 技术 | 用途 |
|------|------|
| Vue 3.5 + TypeScript 5.9 | 主框架 |
| Vite 7 | 构建工具 |
| Vue Router 4 | 路由 |
| Pinia 3 | 状态管理 |
| Axios | HTTP 请求 |

### 本地模型

- `qwen2.5:latest`：主 LLM，用于备课、问答、批改、报告生成。
- `embeddinggemma:latest`：Embedding 模型，向量维度 768。
- `bge-reranker-v2-m3`（CPU）：RAG 重排序。

---

## 3. 项目结构

```
hdsx-main/
├── backend/                      # FastAPI 后端
│   ├── app/
│   │   ├── main.py               # 应用入口
│   │   ├── core/                 # 配置、安全、异常
│   │   │   ├── config.py         # 环境变量与配置
│   │   │   ├── security.py       # JWT、密码哈希
│   │   │   └── exceptions.py     # 全局异常
│   │   ├── db/                   # 数据库会话与基类
│   │   │   ├── base.py           # ORM 基类
│   │   │   └── session.py        # SessionLocal
│   │   ├── modules/models.py     # 所有 SQLAlchemy 模型
│   │   ├── api/                  # 路由层
│   │   │   ├── router.py         # API 路由聚合
│   │   │   ├── dependencies.py   # 依赖注入
│   │   │   └── schemas.py        # Pydantic 输入输出 Schema
│   │   ├── services/             # 业务逻辑层
│   │   │   ├── agents.py         # Agent / 备课 / 批改 / 报告
│   │   │   └── documents.py      # 文档处理
│   │   ├── rag/                  # RAG 检索与分块
│   │   │   ├── service.py        # RAG 服务（向量+关键词+RRF+重排）
│   │   │   ├── splitter.py       # 文本分块
│   │   │   └── types.py          # RAG 类型定义
│   │   └── integrations/         # 外部服务集成
│   │       ├── milvus.py         # Milvus 集合操作
│   │       ├── ollama.py         # Ollama 调用
│   │       └── reranker.py       # BGE 重排序
│   ├── migrations/               # Alembic 迁移脚本
│   │   └── versions/             # 0001_initial_schema ~ 0007_classroom_ops
│   └── tests/                    # pytest 测试
│       ├── test_health.py
│       ├── test_security.py
│       ├── test_fusion.py
│       ├── test_splitter.py
│       └── test_assignment_contracts.py
├── frontend/                     # Vue 3 前端
│   ├── src/
│   │   ├── api/                  # 接口封装
│   │   ├── router/               # 路由配置
│   │   ├── stores/               # Pinia 状态
│   │   └── views/                # 页面组件
│   ├── package.json
│   ├── vite.config.ts
│   └── pnpm-lock.yaml
├── database/
│   └── init_mysql.sql            # MySQL 初始化脚本（首次部署）
├── docs/                         # 六份中文交付文档
│   ├── 01-软件需求规约.md
│   ├── 02-项目开发计划.md
│   ├── 03-数据库设计说明书.md
│   ├── 04-系统架构设计说明书.md
│   ├── 05-测试用例.md
│   └── 06-用户使用手册.md
├── scripts/                      # 辅助与验证脚本
│   ├── check_environment.py      # 环境检查
│   ├── seed_demo.py              # 演示数据
│   ├── e2e_smoke.py              # 端到端冒烟测试
│   ├── verify_account_course_flow.py
│   └── verify_product_features.py
├── bin/                          # 项目级便携 Node.js / npm / pnpm
│   ├── node.cmd
│   ├── npm.cmd
│   └── pnpm.cmd
├── .env.example                  # 环境变量模板
├── pyproject.toml                # Python 项目配置与依赖
├── start_backend.ps1             # 启动后端（开发热重载）
├── start_frontend.ps1            # 启动前端 Vite 开发服务器
├── start_production.ps1          # 单端口生产部署
├── README.md                     # 项目快速开始
├── PROJECT_STATUS.md             # 项目续接状态
└── AGENTS.md                     # 开发约束（Agent 必读）
```

### 后端分层约定

依赖方向固定为：

```
API (router) -> Service -> Repository/ORM -> 数据库
```

- **api/**：只负责路由、参数校验、依赖注入，不写业务逻辑。
- **services/**：写业务逻辑、事务、权限校验。
- **modules/models.py**：定义数据表结构。
- **integrations/**：封装 Milvus / Ollama / 重排序等外部调用。

---

## 4. 运行环境

### 必需

1. **Conda 环境 `llm_learn`（Python 3.11）**
2. **MySQL 8.4**：通过 Docker 容器 `edu-mysql` 运行，数据目录 `D:\Docker\mysql`
3. **Milvus**：已部署的 Docker 服务，默认端口 `19530`
4. **Ollama**：本地运行，`http://localhost:11434`，并已拉取：
   - `qwen2.5:latest`
   - `embeddinggemma:latest`
5. **Node.js 24 LTS**：项目已内置便携版本，位于 `.runtime/node-v24.18.0-win-x64`，无需全局安装 Node/npm/pnpm。

### 环境变量

复制 `.env.example` 为 `.env`，按需修改：

```bash
cp .env.example .env
```

关键配置项：

| 变量 | 说明 |
|------|------|
| `SECRET_KEY` | JWT 签名密钥，生产环境必须替换为长随机字符串 |
| `MYSQL_*` | MySQL 连接信息 |
| `MILVUS_*` | Milvus 连接信息 |
| `OLLAMA_BASE_URL` / `OLLAMA_LLM_MODEL` / `OLLAMA_EMBEDDING_MODEL` | Ollama 配置 |
| `RERANKER_MODEL_PATH` | BGE 重排序模型本地路径 |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` / `RAG_*_TOP_K` | RAG 分块与召回参数 |

---

## 5. 如何运行

### 5.1 首次部署

```powershell
# 1. 复制环境变量
cp .env.example .env
# 编辑 .env，填写 MySQL 账号密码

# 2. 启动 MySQL（假设 Docker Desktop 已运行）
docker start edu-mysql
# 首次自行部署时执行 database/init_mysql.sql 创建数据库和用户

# 3. 激活 Python 环境并安装依赖
conda activate llm_learn
pip install -e ".[dev]"

# 4. 执行数据库迁移
cd backend
alembic upgrade head
cd ..

# 5. 环境检查
python scripts/check_environment.py
```

### 5.2 开发模式启动

```powershell
# 后端（自动使用 llm_learn 环境，reload 范围限制在 backend）
powershell -ExecutionPolicy Bypass -File .\start_backend.ps1

# 前端（自动使用项目内置 Node.js / pnpm）
powershell -ExecutionPolicy Bypass -File .\start_frontend.ps1
```

- 后端地址：http://127.0.0.1:8000
- API 文档：http://127.0.0.1:8000/docs
- 前端地址：http://127.0.0.1:5173（Vite 默认）

### 5.3 生产模式启动（单端口）

```powershell
powershell -ExecutionPolicy Bypass -File .\start_production.ps1
```

FastAPI 同源托管 Vue 生产包，访问 `http://127.0.0.1:8000`。公网部署仍需在前方配置 Nginx/Caddy、HTTPS、防火墙、正式随机密钥和备份。

---

## 6. 如何修改并增加功能

### 6.1 新增业务接口

遵循 **API -> Service -> Repository -> ORM** 的分层方向：

1. **在 `backend/app/modules/models.py` 中定义新表**（如需新增数据表）。
2. **生成 Alembic 迁移**：
   ```bash
   cd backend
   alembic revision --autogenerate -m "描述"
   alembic upgrade head
   ```
3. **在 `backend/app/api/schemas.py` 中定义版本化输入输出 Schema**。
4. **在 `backend/app/services/` 中新增或扩展 Service**，处理业务逻辑、事务和权限。
5. **在 `backend/app/api/router.py`（或新建子路由并在 router.py 注册）中添加 API 路由**。
6. **前端**：在 `frontend/src/api/` 添加接口，在 `frontend/src/views/` 添加页面，在 `frontend/src/router/` 配置路由，必要时在 `frontend/src/stores/` 添加状态。

### 6.2 新增 RAG / Agent 能力

1. 如需新的文档类型或分块策略：修改 `backend/app/rag/splitter.py`。
2. 如需调整检索策略：修改 `backend/app/rag/service.py`。
3. 如需新增 Agent（备课、出题、批改、报告）：在 `backend/app/services/agents.py` 中新增 Prompt 与调用逻辑。
4. 新 Agent、Tool 和 Prompt 必须：
   - 使用版本化输入输出 Schema（Pydantic）。
   - 添加对应的 pytest 测试。

### 6.3 前端新增页面

1. 在 `frontend/src/views/` 创建 Vue 组件。
2. 在 `frontend/src/router/` 注册路由，注意按角色区分访问权限。
3. 在 `frontend/src/api/` 调用后端接口。
4. 在 `frontend/src/stores/` 管理共享状态（如用户信息、课程列表）。

### 6.4 数据库变更强制要求

- **必须使用 Alembic 迁移**，禁止用 `create_all()` 代替。
- 修改表结构后，务必将迁移脚本提交到 `backend/migrations/versions/`。
- 测试环境也要执行 `alembic upgrade head`。

### 6.5 安全与规范

- 不得硬编码密码、JWT 密钥或机器绝对路径，统一使用 `.env` 环境变量。
- 不得让模型执行自由 SQL；所有写操作经过 Service 权限和事务校验。
- 需要下载、安装或修改现有 Docker 服务时，先报告并获得用户授权。

---

## 7. 测试

### 后端测试

```bash
conda activate llm_learn
cd backend
pytest
```

当前已有测试覆盖：健康检查、安全、RAG 融合、文本分块、作业契约。

### 前端检查与构建

```powershell
# 使用项目内置 pnpm
cd frontend
..\bin\pnpm.cmd install
..\bin\pnpm.cmd build
```

### 端到端验证

```bash
# 环境检查
python scripts/check_environment.py

# 真实服务端到端验证
python scripts/e2e_smoke.py
python scripts/verify_account_course_flow.py
python scripts/verify_product_features.py
```

---

## 8. 部署说明

### 开发环境

- 后端使用 `start_backend.ps1`（reload 启用）。
- 前端使用 `start_frontend.ps1`（Vite dev server）。

### 生产环境

- 使用 `start_production.ps1`，FastAPI 同源托管前端生产包。
- 生产环境必须：
  - 替换 `SECRET_KEY` 为长随机字符串。
  - 配置 HTTPS（Nginx/Caddy 反向代理）。
  - 限制 `.env` 与 `storage/` 目录权限。
  - 配置数据库备份。

---

## 9. 关键文档索引

| 文档 | 内容 |
|------|------|
| `README.md` | 快速开始、环境、运行方式 |
| `PROJECT_STATUS.md` | 项目续接状态、当前阶段、已完成清单 |
| `AGENTS.md` | Agent 开发约束（修改前必读） |
| `docs/01-软件需求规约.md` | 功能需求 |
| `docs/02-项目开发计划.md` | 开发计划与里程碑 |
| `docs/03-数据库设计说明书.md` | 数据表设计 |
| `docs/04-系统架构设计说明书.md` | 系统架构 |
| `docs/05-测试用例.md` | 测试用例 |
| `docs/06-用户使用手册.md` | 用户操作手册 |

---

## 10. 快速开发 Checklist

- [ ] 修改前已阅读 `AGENTS.md`、`PROJECT_STATUS.md` 和相关模块代码。
- [ ] 新增表/字段已通过 Alembic 生成迁移并执行 `alembic upgrade head`。
- [ ] 新增接口已定义 Pydantic Schema，Service 层处理权限与事务。
- [ ] 新增 Agent / Tool / Prompt 已添加版本化 Schema 和 pytest 测试。
- [ ] 未硬编码密码、密钥、绝对路径。
- [ ] 已运行 `pytest`、`vue-tsc`、`vite build` 并通过。
- [ ] 已检查 `PROJECT_STATUS.md`、`README.md`、`docs/` 是否需要同步更新。
- [ ] 外部服务（MySQL、Milvus、Ollama）不可用时返回明确错误，不降级到 SQLite 或伪造模型结果。

---

*本文档生成时间：2026-07-13。若项目结构或运行方式发生变更，请同步更新本文件。*
