from types import SimpleNamespace
import asyncio

import pytest

from app.agents.runtime import AgentRuntime
from app.mcp.server import InternalMCPServer
from app.prompts.registry import get_prompt_registry
from app.skills.registry import get_skill_registry
from app.tools.contracts import ToolContext
from app.tools.registry import get_tool_registry
from app.agents.validation import validate_agent_contracts
from app.agents.tutor import TutorAgent


class FakeOllama:
    async def chat(self, system: str, user: str, json_mode=False) -> str:
        assert system and user
        return "生成结果"


def test_prompt_and_skill_versions_are_resolvable():
    prompts = get_prompt_registry()
    skills = get_skill_registry()
    for skill in skills.list():
        prompt = prompts.get(skill.prompt, skill.prompt_version)
        assert prompt.version == skill.prompt_version
    assert len(skills.list()) >= 6
    assert len(prompts.list()) >= 6


def test_every_domain_agent_pins_a_resolvable_skill_and_prompt():
    result = validate_agent_contracts()
    assert result["ok"] is True
    assert len(result["contracts"]) == 6
    tutor = next(item for item in result["contracts"] if item["agent"] == "TutorAgent")
    assert tutor["skill"] == "grounded_qa@1.1.0"
    assert tutor["prompt"] == "grounded_qa@1.1.0"


def test_tutor_agent_uses_registered_grounded_qa_version():
    result = asyncio.run(TutorAgent(AgentRuntime(FakeOllama())).run(
        {"query": "什么是回归？", "context": "[资料1] 回归用于预测连续值。"},
        tools_used=["search_course_knowledge"],
    ))
    assert result.content == "生成结果"
    assert result.meta.capability == "grounded_qa"
    assert result.meta.version == "1.1.0"


def test_tool_registry_is_an_explicit_allowlist_with_confirmation_boundary():
    tools = get_tool_registry().list()
    assert {item.name for item in tools} == {"search_course_knowledge", "search_web_knowledge", "get_course_context", "get_document_context", "get_assignment_rubric", "get_student_mastery_summary", "preview_web_source"}
    assert [item.name for item in tools if not item.read_only] == ["preview_web_source"]


def test_runtime_blocks_tool_not_declared_by_skill():
    runtime = AgentRuntime(FakeOllama())
    with pytest.raises(ValueError, match="禁止调用工具"):
        asyncio.run(runtime.complete("learning_report", {"metrics": "{}"}, tools_used=["get_course_context"]))


def test_internal_mcp_only_lists_registered_tools():
    context = ToolContext(db=None, user=SimpleNamespace(role="admin"), trace_id="test")
    response = asyncio.run(InternalMCPServer().handle({"jsonrpc":"2.0","id":1,"method":"tools/list"}, context))
    assert "error" not in response
    assert {item["name"] for item in response["result"]["tools"]} == {item.name for item in get_tool_registry().list()}
