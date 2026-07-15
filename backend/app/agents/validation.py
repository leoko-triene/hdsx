from app.agents.answer import StandardAnswerAgent
from app.agents.assignment import AssignmentAgent
from app.agents.grading import GradingAgent
from app.agents.lesson import LessonAgent
from app.agents.report import ReportAgent
from app.agents.tutor import TutorAgent
from app.prompts.registry import get_prompt_registry
from app.skills.registry import get_skill_registry


AGENT_TYPES = (
    StandardAnswerAgent, AssignmentAgent, GradingAgent,
    LessonAgent, ReportAgent, TutorAgent,
)


def validate_agent_contracts() -> dict:
    """在启动阶段验证 Agent 固定版本、Skill 和 Prompt 可完整解析。"""
    skills = get_skill_registry()
    prompts = get_prompt_registry()
    resolved = []
    for agent_type in AGENT_TYPES:
        skill = skills.get(agent_type.skill_name, agent_type.skill_version)
        prompt = prompts.get(skill.prompt, skill.prompt_version)
        resolved.append({
            "agent": agent_type.__name__, "skill": f"{skill.name}@{skill.version}",
            "prompt": f"{prompt.name}@{prompt.version}",
        })
    return {"ok": True, "contracts": resolved}
