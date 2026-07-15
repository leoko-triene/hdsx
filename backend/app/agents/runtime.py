from typing import Any

from app.common.contracts import AgentResult, InvocationMeta
from app.common.tracing import TraceContext
from app.integrations.ollama import OllamaClient
from app.prompts.registry import get_prompt_registry
from app.skills.registry import get_skill_registry
from app.core.exceptions import AppError


class AgentRuntime:
    """统一执行 Skill/Prompt，阻止未声明工具并返回可追踪元数据。"""

    def __init__(self, client: OllamaClient | None = None):
        self.client = client or OllamaClient()

    async def complete(
        self, skill_name: str, values: dict[str, Any], *, skill_version: str = "1.0.0",
        output_schema: dict | None = None, tools_used: list[str] | None = None,
    ) -> AgentResult:
        try:
            skill = get_skill_registry().get(skill_name, skill_version)
            prompt = get_prompt_registry().get(skill.prompt, skill.prompt_version)
        except KeyError as exc:
            raise AppError("AGENT_CONTRACT_INVALID", str(exc), 503) from exc
        requested_tools = tools_used or []
        invalid = set(requested_tools) - set(skill.allowed_tools)
        if invalid:
            raise ValueError(f"Skill {skill_name} 禁止调用工具：{sorted(invalid)}")
        trace = TraceContext(skill.name, skill.version)
        for tool in requested_tools:
            trace.mark_tool(tool)
        system, user = prompt.render(**values)
        json_mode: bool | dict = output_schema or skill.output_schema or (prompt.output_mode == "json")
        content = await self.client.chat(system, user, json_mode)
        return AgentResult(
            status="success", content=content,
            meta=InvocationMeta(trace_id=trace.trace_id, capability=skill.name, version=skill.version, duration_ms=trace.duration_ms, tools_used=trace.tools_used),
        )
