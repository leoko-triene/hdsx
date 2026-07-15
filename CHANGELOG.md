# v1.1.0 知识点图谱功能更新说明

## 新增功能

### 1. 知识点图谱自动生成
- 教师可从课程教材/文档中一键生成知识点图谱
- AI 自动识别知识点（code、name、description、level）
- AI 自动分析知识点之间的关系（prerequisite/related/contains）
- 可视化展示图谱（节点-关系图）

### 2. 知识点与作业关联
- 布置作业时可为每道题目选择关联的知识点
- 知识点下拉选择器，支持多选
- 题目自动记录关联的知识点 ID

### 3. 学生知识点掌握度分析
- 学生可查看自己在各知识点上的掌握程度
- 自动分级：mastered / proficient / developing / weak
- 识别薄弱知识点并推荐学习路径
- 基于作业提交和 AI 批改结果实时计算

### 4. 教师审核机制
- 生成的知识图谱为 draft 状态
- 教师可审核通过后发布
- 支持重新生成

---

## 新增文件（11个）

| 文件 | 说明 |
|------|------|
| `backend/app/services/knowledge_graph.py` | 核心服务：AI 抽取、图谱存储、掌握度分析 |
| `backend/app/api/knowledge_graph.py` | REST API 路由 |
| `backend/app/agents/knowledge_graph.py` | Agent 技能注册 |
| `backend/app/skills/definitions/knowledge_graph_extraction/SKILL.md` | 技能定义 |
| `backend/app/skills/definitions/knowledge_graph_extraction/v1.md` | 技能版本 |
| `backend/migrations/versions/0010_knowledge_graph.py` | 知识点图谱表迁移 |
| `frontend/src/views/KnowledgeGraphView.vue` | 教师图谱管理页面 |
| `frontend/src/views/KnowledgeGraphStudent.vue` | 学生掌握度页面 |
| `frontend/src/components/KnowledgeGraphChart.vue` | 图谱可视化组件 |
| `frontend/src/components/KnowledgePointSelector.vue` | 知识点选择器组件 |
| `frontend/src/router/index.ts` | 新增路由（已有文件，新增路由配置） |

---

## 修改文件（20个）

| 文件 | 修改内容 |
|------|---------|
| `backend/app/main.py` | 注册 `knowledge_graph_router` |
| `backend/app/modules/models.py` | 新增 `KnowledgePoint`、`KnowledgePointGraph`、`KnowledgePointRelation` 模型；`Question` 新增 `knowledge_point_ids_json` |
| `backend/app/api/schemas.py` | 新增知识点图谱相关 Schema |
| `backend/migrations/versions/0003_document_dedup.py` | 添加存在性检查，修复重复列报错 |
| `backend/migrations/versions/0004_course_membership.py` | 添加存在性检查，修复重复表报错 |
| `backend/migrations/versions/0007_classroom_operations.py` | 修复括号不匹配语法错误 |
| `plugins/model_providers/providers.py` | 修复 OpenAI 兼容 API 400 错误：去掉空 system 消息和 temperature |
| `frontend/src/App.vue` | 添加"知识点图谱"导航入口 |
| `frontend/src/components/AppBreadcrumb.vue` | 修复知识图谱面包屑路径 |
| `frontend/src/views/AssignmentView.vue` | 修复 v-else 编译错误，添加知识点关联功能 |
| `frontend/src/views/CourseModuleEntryView.vue` | 修复路由 base 路径缺失 |
| `frontend/src/views/AnalyticsView.vue` | 微调（已有修改） |
| `docs/06-用户使用手册.md` | 文档更新 |
| `PROJECT_STATUS.md` | 状态更新 |
| `frontend/package.json` | 依赖更新 |
| `frontend/pnpm-lock.yaml` | 锁定文件更新 |
| `frontend/pnpm-workspace.yaml` | 工作区配置更新 |

---

## Bug 修复

| 问题 | 修复方式 |
|------|---------|
| Alembic 迁移 `dedup_key` 重复列 | 添加 `if not in tables` 存在性检查 |
| Alembic 迁移 `course_managers` 表已存在 | 添加 `if not in tables` 存在性检查 |
| Alembic 迁移 `knowledge_point_relations` 重复建表 | 添加 `if not in tables` 存在性检查 |
| 迁移脚本 `0007` 括号不匹配 | 修复语法错误 |
| Vue `v-else` 无相邻 `v-if` | 修正模板结构 |
| 路由 `/course/1` 无效路径 | 修复 App.vue、Breadcrumb、EntryView 路径逻辑 |
| AI 返回非 JSON 导致 500 | 使用 `validate_or_fallback` 兜底，避免崩溃 |
| Kimi API 400 Bad Request | 去掉空 system 消息和 temperature 参数 |
| 多次生成后返回旧空图谱 | `get_graph` 按 `id.desc()` 排序取最新 |
| 上下文过长导致 AI 忽略指令 | 缩短 context 从 12000 到 3000 字符 |

---

## 使用方式

### 教师
1. 进入课程 → 左侧导航"知识点图谱"
2. 点击"从教材生成知识点图谱"
3. 审核通过后点击"审核通过"
4. 布置作业时，在题目编辑区选择关联知识点

### 学生
1. 进入课程 → 左侧导航"知识点图谱"
2. 查看"我的掌握度"
3. 查看薄弱知识点和推荐学习路径

---

## 技术栈变更

- **后端**：新增 `KnowledgePoint`、`KnowledgePointGraph`、`KnowledgePointRelation` 3 张表
- **前端**：新增 ECharts 知识图谱可视化
- **AI**：Prompt 优化，支持 Ollama / OpenAI 兼容 API
- **迁移**：Alembic 版本更新至 `0010`

---

*版本：v1.1.0*
*更新日期：2025-07-15*
