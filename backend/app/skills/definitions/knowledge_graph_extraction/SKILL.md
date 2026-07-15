# knowledge_graph_extraction

## 功能
从课程教材/文档中自动抽取结构化知识点并构建知识关系图谱。

## 输入
- 教材文本内容（已分块的 DocumentChunk 集合）
- 课程 ID（用于上下文）

## 输出
- JSON 格式的知识图谱：包含 knowledge_points 和 relations
- 知识点编码规则：KP-章节号-序号

## 版本
- v1: 基础抽取，支持 prerequisite / related / contains 三种关系