from app.api.router import _answer_tokens, normalized_question_options
from app.api.schemas import AssignmentMaterialGenerate, QASessionUpdate
from app.services.agents import _load_model_json, generate_assignment_materials
from types import SimpleNamespace
import asyncio


def test_model_json_accepts_code_fence_and_embedded_text():
    assert _load_model_json('```json\n{"items": []}\n```') == {"items": []}
    assert _load_model_json('生成结果如下：[{"stem":"题目"}]。') == [{"stem": "题目"}]


def test_multiple_choice_answer_is_order_independent():
    assert _answer_tokens(["B", "A"]) == _answer_tokens("A,B")
    assert _answer_tokens("A，B") != _answer_tokens("A")


def test_true_false_options_are_always_available():
    assert normalized_question_options("true_false", None) == [
        {"key": "true", "content": "正确"},
        {"key": "false", "content": "错误"},
    ]


def test_assignment_material_accepts_multiple_documents():
    request = AssignmentMaterialGenerate(document_ids=[3, 5], chapter_or_topic="第一章")
    assert request.document_ids == [3, 5]


def test_assignment_material_rejects_empty_or_oversized_request():
    import pytest
    with pytest.raises(ValueError):
        AssignmentMaterialGenerate(
            document_ids=[3], chapter_or_topic="第一章", single_choice_count=0,
            multiple_choice_count=0, true_false_count=0, short_answer_count=0, essay_count=0,
        )
    with pytest.raises(ValueError):
        AssignmentMaterialGenerate(
            document_ids=[3], chapter_or_topic="第一章", single_choice_count=10,
            multiple_choice_count=10, true_false_count=1, short_answer_count=0, essay_count=0,
        )


def test_assignment_generation_raises_error_on_empty_result(monkeypatch):
    async def fake_run(self, values, **kwargs):
        return SimpleNamespace(content='{"items": []}')
    monkeypatch.setattr("app.services.agents.AssignmentAgent.run", fake_run)
    from unittest.mock import AsyncMock, MagicMock
    mock_ks = MagicMock()
    mock_ks.hybrid_search = AsyncMock(return_value=[])
    mock_ks.keyword_search = MagicMock(return_value=[])
    monkeypatch.setattr("app.services.agents.KnowledgeService", lambda db: mock_ks)
    request = AssignmentMaterialGenerate(
        document_ids=[3], chapter_or_topic="第一章", single_choice_count=1,
        multiple_choice_count=1, true_false_count=1, short_answer_count=1, essay_count=1,
    )
    documents = [SimpleNamespace(id=3, filename="教材.txt")]
    import pytest
    from app.core.exceptions import AppError
    with pytest.raises(AppError, match="AI 出题失败"):
        asyncio.run(generate_assignment_materials(MagicMock(), 1, [3], documents, request))


def test_qa_session_title_can_be_renamed():
    assert QASessionUpdate(title="  第一章复习  ").title.strip() == "第一章复习"
