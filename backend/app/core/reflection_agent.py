from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from app.db.models import ChatSession, ModelConfig, Skill, Tool
from app.llm import LLMClient, LLMError
from app.session.helpers import public_session
from app.session.session_schema import RouterDecision, StepAgentResult
from app.tools.tool_schema import ToolResult


PROMPT_PATH = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "reflection_prompt.md"


class ReflectionDecision(BaseModel):
    needs_retry: bool = False
    reason: str | None = None
    target_skill_id: str | None = None
    target_step_id: str | None = None
    target_tool_name: str | None = None


class ReflectionAgent:
    def review(
        self,
        message: str,
        session: ChatSession,
        active_skill: Skill | None,
        router_decision: RouterDecision,
        step_result: StepAgentResult,
        tool_result: ToolResult | None,
        available_skills: list[Skill],
        available_tools: list[Tool],
        model_config: ModelConfig,
    ) -> ReflectionDecision:
        if not _should_reflect(router_decision, step_result, tool_result):
            return ReflectionDecision()

        payload = {
            "user_message": message,
            "current_session": public_session(session).model_dump(),
            "active_skill": active_skill.content_json if active_skill else None,
            "router_decision": router_decision.model_dump(),
            "step_result": step_result.model_dump(),
            "tool_result": tool_result.model_dump() if tool_result else None,
            "available_skills": [
                {
                    "skill_id": skill.skill_id,
                    "name": skill.name,
                    "description": skill.description,
                    "trigger_intents": skill.content_json.get("trigger_intents", []),
                    "required_info": skill.content_json.get("required_info", []),
                    "steps": [
                        {
                            "step_id": step.get("step_id"),
                            "name": step.get("name"),
                            "allowed_actions": step.get("allowed_actions", []),
                        }
                        for step in skill.content_json.get("steps", [])
                        if isinstance(step, dict)
                    ],
                }
                for skill in available_skills
            ],
            "available_tools": [
                {
                    "name": tool.name,
                    "display_name": tool.display_name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                    "allowed_skills": tool.allowed_skills_json,
                }
                for tool in available_tools
                if tool.enabled
            ],
        }
        try:
            raw = LLMClient(model_config).generate_json(PROMPT_PATH.read_text(encoding="utf-8"), payload)
            return ReflectionDecision.model_validate(raw)
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise LLMError(f"Reflection agent returned invalid JSON schema: {exc}") from exc


def _should_reflect(
    router_decision: RouterDecision,
    step_result: StepAgentResult,
    tool_result: ToolResult | None,
) -> bool:
    if router_decision.decision in {"handoff_human", "clarify"}:
        return True
    if tool_result is not None:
        return True
    return step_result.is_step_completed
