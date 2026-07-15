from typing import Any

from app.agents.runtime import AgentRuntime
from app.common.contracts import AgentResult


class DomainAgent:
    skill_name = ""
    skill_version = "1.0.0"

    def __init__(self, runtime: AgentRuntime | None = None):
        self.runtime = runtime or AgentRuntime()

    async def run(self, values: dict[str, Any], *, output_schema: dict | None = None, tools_used: list[str] | None = None) -> AgentResult:
        return await self.runtime.complete(
            self.skill_name, values, skill_version=self.skill_version,
            output_schema=output_schema, tools_used=tools_used,
        )
