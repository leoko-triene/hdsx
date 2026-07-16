import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from app.agents.knowledge_graph import KnowledgeGraphAgent
from app.api.schemas import KnowledgeGraphGenerateRequest
from app.core.exceptions import AppError, NotFoundError
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


class FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return FakeScalarResult(self._items)


def _make_syncable_db(points, relations, graph=None):
    """Create a MagicMock db that supports _sync_latest_graph reads."""
    db = MagicMock()

    def fake_scalar(stmt):
        # Duplicate checks and latest graph lookup.
        s = str(stmt)
        if "KnowledgePointGraph" in s:
            return graph
        return None

    db.scalar.side_effect = fake_scalar

    def fake_scalars(stmt):
        s = str(stmt)
        if "KnowledgePoint" in s and "Relation" not in s:
            return FakeScalarResult(points)
        return FakeScalarResult([])

    db.scalars.side_effect = fake_scalars

    def fake_execute(stmt):
        s = str(stmt)
        if "KnowledgePointRelation" in s:
            return FakeExecuteResult(relations)
        return FakeExecuteResult([])

    db.execute.side_effect = fake_execute
    return db


def test_sync_latest_graph_rebuilds_nodes_and_edges():
    db = MagicMock()
    service = KnowledgeGraphService(db)

    graph = SimpleNamespace(
        id=1, course_id=1, version=1,
        nodes_json=[{"id": 999, "code": "OLD", "name": "old"}],
        edges_json=[{"from": 999, "to": 999, "type": "related"}],
    )
    p1 = SimpleNamespace(id=10, course_id=1, code="PY-10", name="Loop", description="loop", chapter_id=None)
    p2 = SimpleNamespace(id=11, course_id=1, code="PY-11", name="Condition", description="", chapter_id=None)
    r1 = SimpleNamespace(id=1, course_id=1, from_kp_id=10, to_kp_id=11, relation_type="prerequisite", confidence=0.9)

    db.scalar.return_value = graph
    db.scalars.return_value = FakeScalarResult([p1, p2])
    db.execute.return_value = FakeExecuteResult([r1])

    service._sync_latest_graph(1)

    assert len(graph.nodes_json) == 2
    assert {n["id"] for n in graph.nodes_json} == {10, 11}
    assert len(graph.edges_json) == 1
    assert graph.edges_json[0]["from"] == 10
    assert graph.edges_json[0]["to"] == 11
    assert graph.edges_json[0]["type"] == "prerequisite"


def test_create_point_calls_sync():
    db = MagicMock()
    service = KnowledgeGraphService(db)
    service._owned_course = MagicMock()
    service._sync_latest_graph = MagicMock()
    service._latest_graph_or_create = MagicMock()

    db.scalar.return_value = None  # no duplicate
    captured = {}

    def fake_add(obj):
        obj.id = 10
        captured["point"] = obj

    db.add.side_effect = fake_add

    user = SimpleNamespace(id=1, role="teacher")
    point = service.create_point(user, 1, {"code": "PY-10", "name": "循环"})

    assert point.id == 10
    assert point.code == "PY-10"
    service._sync_latest_graph.assert_called_once_with(1)


def test_update_point_calls_sync():
    db = MagicMock()
    service = KnowledgeGraphService(db)
    service._owned_course = MagicMock()
    service._sync_latest_graph = MagicMock()

    point = SimpleNamespace(
        id=10, course_id=1, code="PY-10", name="循环", description="", chapter_id=None
    )
    db.get.return_value = point
    db.scalar.return_value = None  # no code duplicate

    user = SimpleNamespace(id=1, role="teacher")
    updated = service.update_point(user, 10, {"name": "循环语句", "description": "for/while"})

    assert updated.name == "循环语句"
    assert updated.description == "for/while"
    service._sync_latest_graph.assert_called_once_with(1)


def test_delete_point_calls_sync():
    db = MagicMock()
    service = KnowledgeGraphService(db)
    service._owned_course = MagicMock()
    service._sync_latest_graph = MagicMock()

    point = SimpleNamespace(id=10, course_id=1)
    db.get.return_value = point

    user = SimpleNamespace(id=1, role="teacher")
    service.delete_point(user, 10)

    db.delete.assert_called_once_with(point)
    service._sync_latest_graph.assert_called_once_with(1)


def test_create_relation_calls_sync_and_rejects_self_loop():
    db = MagicMock()
    service = KnowledgeGraphService(db)
    service._owned_course = MagicMock()
    service._sync_latest_graph = MagicMock()
    service._latest_graph_or_create = MagicMock()

    p10 = SimpleNamespace(id=10, course_id=1)
    p11 = SimpleNamespace(id=11, course_id=1)
    db.get.side_effect = lambda model, pk: {10: p10, 11: p11}.get(pk)
    db.scalar.return_value = None  # no duplicate relation

    captured = {}

    def fake_add(obj):
        obj.id = 100
        captured["relation"] = obj

    db.add.side_effect = fake_add

    user = SimpleNamespace(id=1, role="teacher")
    relation = service.create_relation(
        user, 1, {"from_id": 10, "to_id": 11, "relation_type": "prerequisite", "confidence": 0.9}
    )

    assert relation.from_kp_id == 10
    assert relation.to_kp_id == 11
    assert relation.source == "manual"
    service._sync_latest_graph.assert_called_once_with(1)

    with pytest.raises(AppError) as exc_info:
        service.create_relation(user, 1, {"from_id": 10, "to_id": 10, "relation_type": "related"})
    assert "自环" in str(exc_info.value)


def test_update_relation_calls_sync():
    db = MagicMock()
    service = KnowledgeGraphService(db)
    service._owned_course = MagicMock()
    service._sync_latest_graph = MagicMock()

    relation = SimpleNamespace(
        id=100, course_id=1, from_kp_id=10, to_kp_id=11,
        relation_type="prerequisite", confidence=0.9
    )
    db.get.return_value = relation

    user = SimpleNamespace(id=1, role="teacher")
    updated = service.update_relation(user, 100, {"relation_type": "related", "confidence": 0.7})

    assert updated.relation_type == "related"
    assert updated.confidence == 0.7
    service._sync_latest_graph.assert_called_once_with(1)


def test_delete_relation_calls_sync():
    db = MagicMock()
    service = KnowledgeGraphService(db)
    service._owned_course = MagicMock()
    service._sync_latest_graph = MagicMock()

    relation = SimpleNamespace(id=100, course_id=1)
    db.get.return_value = relation

    user = SimpleNamespace(id=1, role="teacher")
    service.delete_relation(user, 100)

    db.delete.assert_called_once_with(relation)
    service._sync_latest_graph.assert_called_once_with(1)


def test_edit_requires_course_owner():
    db = MagicMock()
    service = KnowledgeGraphService(db)
    service._owned_course = MagicMock(side_effect=PermissionError("Forbidden"))

    user = SimpleNamespace(id=1, role="teacher")
    with pytest.raises(PermissionError):
        service.create_point(user, 1, {"code": "PY-10", "name": "循环"})


def test_list_graph_versions_orders_by_version_desc():
    db = MagicMock()
    service = KnowledgeGraphService(db)

    g1 = SimpleNamespace(
        id=1, course_id=1, version=1, status="approved",
        generated_by=1, reviewed_by=2, reviewed_at=None, created_at=datetime.now().astimezone()
    )
    g2 = SimpleNamespace(
        id=2, course_id=1, version=2, status="draft",
        generated_by=1, reviewed_by=None, reviewed_at=None, created_at=datetime.now().astimezone()
    )
    db.scalars.return_value = FakeScalarResult([g2, g1])

    versions = service.list_graph_versions(1)

    assert len(versions) == 2
    assert versions[0].version == 2
    assert versions[1].version == 1


def test_get_graph_by_id_returns_version():
    db = MagicMock()
    service = KnowledgeGraphService(db)

    graph = SimpleNamespace(
        id=5, course_id=1, version=3, status="approved",
        generated_by=1, reviewed_by=2, reviewed_at=None, created_at=datetime.now().astimezone()
    )
    db.get.return_value = graph

    result = service.get_graph_by_id(5)

    assert result == graph
    db.get.assert_called_once()


def test_get_graph_by_id_raises_when_missing():
    db = MagicMock()
    service = KnowledgeGraphService(db)
    db.get.return_value = None

    with pytest.raises(NotFoundError):
        service.get_graph_by_id(999)
