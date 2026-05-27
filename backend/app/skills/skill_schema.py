from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SkillStep(BaseModel):
    step_id: str
    name: str
    instruction: str
    expected_user_info: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)


class SkillCard(BaseModel):
    skill_id: str
    name: str
    version: str = "1.0.0"
    business_domain: Optional[str] = None
    description: str = ""
    trigger_intents: list[str] = Field(default_factory=list)
    user_utterance_examples: list[str] = Field(default_factory=list)
    goal: list[str] = Field(default_factory=list)
    required_info: list[str] = Field(default_factory=list)
    slot_filling_policy: dict[str, Any] = Field(default_factory=dict)
    steps: list[SkillStep] = Field(default_factory=list)
    interruption_policy: dict[str, str] = Field(default_factory=dict)
    response_rules: list[str] = Field(default_factory=list)


class SkillCreateRequest(BaseModel):
    tenant_id: str
    content: SkillCard
    status: Literal["draft", "published", "archived"] = "draft"


class SkillUpdateRequest(BaseModel):
    tenant_id: str
    content: SkillCard
    status: Optional[Literal["draft", "published", "archived"]] = None


class SkillRead(BaseModel):
    id: str
    tenant_id: str
    skill_id: str
    version: str
    name: str
    business_domain: Optional[str]
    description: Optional[str]
    content: SkillCard
    status: str
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class SkillDistillRequest(BaseModel):
    tenant_id: str
    title: str
    raw_content: str
    business_domain: Optional[str] = None
    available_tools: list[dict[str, Any]] = Field(default_factory=list)


class SkillDistillResponse(BaseModel):
    draft_skill: SkillCard
    warnings: list[str] = Field(default_factory=list)
