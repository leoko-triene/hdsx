import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from app.agents.knowledge_graph import KnowledgeGraphAgent
from app.api.schemas import KnowledgeGraphGenerateRequest
from app.services.knowledge_graph import KnowledgeGraphService


class FakeResult:
    def __init__(self, content):
        self.content = content


def test_knowledge_graph_agent_declares_skill():
    agent = KnowledgeGraphAgent()
    assert agent.skill_name == "knowledge_graph_extraction"
    assert agent.skill_version == "1.0.0"


def test_generate_from_documents_rejects_empty_extraction():
    db = MagicMock()
    service = KnowledgeGraphService(db)
    service._owned_course = MagicMock()

    chunk = SimpleNamespace(content="fake content")
    doc = SimpleNamespace(id=1, filename="test.pdf")
    db.execute.return_value.all.return_value = [(chunk, doc)]

    agent_result = FakeResult('{"knowledge_points": [], "relations": []}')

    with patch.object(KnowledgeGraphAgent, "run", new=AsyncMock(return_value=agent_result)):
        with pytest.raises(Exception) as exc_info:
            asyncio.run(service.generate_from_documents(
                SimpleNamespace(id=1, role="teacher"), course_id=1
            ))
    assert "未能" in str(exc_info.value)


def test_student_mastery_reuses_mastery_snapshot():
    db = MagicMock()
    service = KnowledgeGraphService(db)
    service._owned_course = MagicMock()

    q1 = SimpleNamespace(knowledge_point_ids_json=[10, 20])
    a1 = SimpleNamespace(id=1, course_id=1)

    kp10 = SimpleNamespace(id=10, course_id=1, name="KP10", description="")
    kp20 = SimpleNamespace(id=20, course_id=1, name="KP20", description="")
    snap10 = SimpleNamespace(student_id=5, knowledge_point_id=10, score=0.95, level="已掌握", created_at=datetime.now().astimezone())
    snap20 = SimpleNamespace(student_id=5, knowledge_point_id=20, score=0.4, level="薄弱", created_at=datetime.now().astimezone())

    first_call = True
    def fake_execute(stmt):
        nonlocal first_call
        result = MagicMock()
        if first_call:
            first_call = False
            result.all.return_value = [(q1, a1)]
        else:
            result.all.return_value = [(snap10, kp10), (snap20, kp20)]
        return result

    db.execute.side_effect = fake_execute

    result = service.get_student_mastery(5, 1)

    assert result["student_id"] == 5
    assert result["course_id"] == 1
    assert len(result["knowledge_points"]) == 2
    levels = {item["knowledge_point_id"]: item["level"] for item in result["knowledge_points"]}
    assert levels[10] == "mastered"
    assert levels[20] == "weak"
    assert "KP20" in result["recommended_path"]


def test_knowledge_graph_generate_request_schema():
    req = KnowledgeGraphGenerateRequest(course_id=1, document_ids=[1, 2])
    assert req.course_id == 1
    assert req.document_ids == [1, 2]
