"""
# 放到：backend/app/agents/knowledge_graph.py
# 说明：知识点图谱抽取 Agent 入口，skill_name 对应 prompt 版本
"""
from app.agents.base import DomainAgent

class KnowledgeGraphAgent(DomainAgent):
    skill_name = "knowledge_graph_extraction"