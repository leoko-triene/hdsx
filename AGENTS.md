# Agent 开发约束

1. 修改前阅读根目录 `../44.md`、本文件、相关模块和测试。
2. Python 命令统一在 `llm_learn` 环境运行。
3. 业务数据库只能使用 MySQL；Milvus 仅保存向量。
4. 依赖方向固定为 API -> Service -> Repository -> ORM。
5. 新表或字段必须带 Alembic 迁移；禁止以 `create_all` 代替正式迁移。
6. 新 Agent、Tool 和 Prompt 必须有版本化输入输出 Schema 与测试。
7. 不得硬编码密码、JWT 密钥或机器绝对路径；使用环境变量。
8. 不得让模型执行自由 SQL；写操作必须通过 service 权限和事务校验。
9. 需要下载、安装或修改现有 Docker 服务时，先报告并获得用户授权。
10. 每次交付需运行相关测试，并同步 README、OpenAPI 或设计文档。
11. 每次代码、配置或数据库修改完成后，必须逐项检查 `PROJECT_STATUS.md`、`README.md` 和 `docs/` 目录下全部 Markdown 文档是否受影响；需要时在同一任务中同步更新，不需要时也应在交付说明中明确已检查且无需修改。
12. 文档检查至少覆盖：功能范围与当前状态、启动和部署方式、需求规约、开发计划、数据库设计、系统架构、测试用例及用户使用手册。
13. 新增功能应遵循插件化架构：后端通过 `backend/app/api/features/<feature>.py` + `registry.py` 注册，前端通过 `frontend/src/features/<feature>/` + `features/index.ts` 注册；避免直接修改 `router.py`、`App.vue`、`DashboardView.vue` 等集中式文件。详见 `docs/08-插件化开发规范.md`。
14. 模型调用必须通过 `app.integrations.llm` 中的 `get_llm_provider()` / `get_embedding_provider()`，禁止在业务代码中直接实例化 `OllamaClient` 或写死某个厂商的 API。新增 Provider 需在 `llm.py` 注册并补充单元测试。
