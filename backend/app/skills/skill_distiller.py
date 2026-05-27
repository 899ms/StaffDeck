from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import sleep
from typing import Any

from app.db.models import ModelConfig
from app.llm import LLMClient, LLMError
from app.skills.skill_schema import SkillDistillRequest, SkillDistillResponse, SkillCard, SkillStep


PROMPT_PATH = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "skill_distiller_prompt.md"
STREAM_INTERVAL_SECONDS = 0.035


class SkillDistiller:
    def distill(self, request: SkillDistillRequest, model_config: ModelConfig) -> SkillDistillResponse:
        payload = self._payload(request)
        raw = LLMClient(model_config).generate_json(PROMPT_PATH.read_text(encoding="utf-8"), payload)
        return self._normalize_response(raw, request)

    def distill_stream(self, request: SkillDistillRequest, model_config: ModelConfig) -> SkillDistillResponse:
        payload = {
            "title": request.title,
            "business_domain": request.business_domain,
            "raw_content": request.raw_content,
            "available_tools": request.available_tools,
        }
        text = "".join(LLMClient(model_config).generate_text_stream(PROMPT_PATH.read_text(encoding="utf-8"), payload))
        return self._normalize_response(json.loads(_extract_json(text)), request)

    def stream_text(self, request: SkillDistillRequest, model_config: ModelConfig):
        payload = self._payload(request)
        chunks: list[str] = []
        try:
            for chunk in LLMClient(model_config).generate_text_stream(PROMPT_PATH.read_text(encoding="utf-8"), payload):
                chunks.append(chunk)
                yield {"event": "chunk", "data": {"content": chunk}}
            response = self._normalize_response(json.loads(_extract_json("".join(chunks))), request)
        except (LLMError, json.JSONDecodeError, ValueError) as exc:
            response = self._fallback_response(request, f"模型输出未能直接解析，已使用规则兜底生成：{exc}")
            for chunk in _chunk_text(json.dumps(response.draft_skill.model_dump(), ensure_ascii=False, indent=2)):
                yield {"event": "chunk", "data": {"content": chunk}}
                sleep(STREAM_INTERVAL_SECONDS)
        yield {"event": "complete", "data": response.model_dump(mode="json")}

    def _payload(self, request: SkillDistillRequest) -> dict[str, Any]:
        return {
            "title": request.title,
            "business_domain": request.business_domain,
            "raw_content": request.raw_content,
            "available_tools": request.available_tools,
        }

    def _normalize_response(self, raw: dict[str, Any], request: SkillDistillRequest) -> SkillDistillResponse:
        draft = raw.get("draft_skill") if isinstance(raw.get("draft_skill"), dict) else raw
        warnings = list(raw.get("warnings") or [])
        fallback = self._fallback_card(request)

        required_info = _string_list(draft.get("required_info"), fallback.required_info)
        steps = self._normalize_steps(draft.get("steps"), fallback.steps)
        normalized = {
            "skill_id": _string(draft.get("skill_id"), fallback.skill_id),
            "name": _string(draft.get("name"), fallback.name),
            "version": _string(draft.get("version"), "1.0.0"),
            "business_domain": _string(draft.get("business_domain"), fallback.business_domain or "general"),
            "description": _string(draft.get("description"), fallback.description),
            "trigger_intents": _string_list(draft.get("trigger_intents"), fallback.trigger_intents),
            "user_utterance_examples": _string_list(
                draft.get("user_utterance_examples"), fallback.user_utterance_examples
            ),
            "goal": _string_list(draft.get("goal"), fallback.goal),
            "required_info": required_info,
            "slot_filling_policy": _slot_filling_policy(
                draft.get("slot_filling_policy"),
                required_info,
                steps,
                fallback.slot_filling_policy,
            ),
            "steps": steps,
            "interruption_policy": _string_dict(draft.get("interruption_policy"), fallback.interruption_policy),
            "response_rules": _string_list(draft.get("response_rules"), fallback.response_rules),
        }
        response = SkillDistillResponse(draft_skill=SkillCard.model_validate(normalized), warnings=warnings)
        if not response.draft_skill.steps:
            response.draft_skill.steps = fallback.steps
            response.warnings.append("模型未生成步骤，已使用规则生成默认步骤。")
        return response

    def _normalize_steps(self, value: Any, fallback_steps: list[SkillStep]) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return [step.model_dump() for step in fallback_steps]
        steps: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            fallback = fallback_steps[min(index, len(fallback_steps) - 1)]
            steps.append(
                {
                    "step_id": _string(item.get("step_id"), fallback.step_id),
                    "name": _string(item.get("name"), fallback.name),
                    "instruction": _string(item.get("instruction"), fallback.instruction),
                    "expected_user_info": _string_list(
                        item.get("expected_user_info"), fallback.expected_user_info
                    ),
                    "allowed_actions": _normalize_actions(
                        _string_list(item.get("allowed_actions"), fallback.allowed_actions)
                    ),
                }
            )
        return steps or [step.model_dump() for step in fallback_steps]

    def _fallback_response(self, request: SkillDistillRequest, warning: str) -> SkillDistillResponse:
        return SkillDistillResponse(draft_skill=self._fallback_card(request), warnings=[warning])

    def _fallback_card(self, request: SkillDistillRequest) -> SkillCard:
        title = request.title.strip() or "新技能"
        raw = request.raw_content
        inferred_fields = _infer_required_fields(raw)
        required_info = [field for field, _label in inferred_fields]
        required_labels = [label for _field, label in inferred_fields]
        tool_actions = _tool_actions(request.available_tools)
        steps: list[SkillStep] = []
        if required_info:
            labels = "、".join(required_labels)
            steps.append(
                SkillStep(
                    step_id="collect_required_info",
                    name="收集必要信息",
                    instruction=(
                        f"询问并记录完成该流程所需的信息：{labels}。如果用户一次提供多个信息，"
                        "需要同时提取并写入对应 slot，不要重复追问已提供的信息。"
                    ),
                    expected_user_info=required_info,
                    allowed_actions=["ask_user", "continue_flow"],
                )
            )
        if tool_actions:
            steps.append(
                SkillStep(
                    step_id="execute_with_tools",
                    name="执行工具处理",
                    instruction=(
                        "根据技能目标、已收集信息和工具 input_schema 选择合适工具处理；"
                        "只能使用 available_tools 中存在且参数已满足的工具。"
                    ),
                    expected_user_info=[],
                    allowed_actions=["continue_flow", *tool_actions],
                )
            )
        steps.append(
            SkillStep(
                step_id="reply_result",
                name="反馈结果",
                instruction="根据已收集的信息和工具结果给用户明确回复；信息不足时继续追问，不要编造事实。",
                expected_user_info=[],
                allowed_actions=["answer_user", "handoff_human"],
            )
        )
        return SkillCard(
            skill_id=_slugify(title, raw),
            name=title,
            version="1.0.0",
            business_domain=request.business_domain or "general",
            description=raw[:120] or "根据原始技能文本生成的流程。",
            trigger_intents=[title],
            user_utterance_examples=[title],
            goal=_infer_goals(raw),
            required_info=required_info,
            slot_filling_policy=_default_slot_filling_policy(required_info),
            steps=steps,
            interruption_policy={
                "related_question": "回答相关问题后回到当前流程。",
                "unrelated_business": "可切换新流程并保留当前进度。",
                "chitchat": "简短回应后引导用户继续当前流程。",
                "user_wants_human": "直接转人工。",
            },
            response_rules=["信息不足时先追问，不要编造事实。"],
        )


def _extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end >= start:
        return stripped[start : end + 1]
    return stripped


def _chunk_text(text: str, size: int = 18):
    for index in range(0, len(text), size):
        yield text[index : index + size]


def _string(value: Any, fallback: str | None = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback or ""


def _string_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        if items:
            return items
    return fallback


def _string_dict(value: Any, fallback: dict[str, str]) -> dict[str, str]:
    if isinstance(value, dict):
        items = {str(key): str(item) for key, item in value.items() if str(key)}
        if items:
            return items
    return fallback


def _slot_filling_policy(
    value: Any,
    required_info: list[str],
    steps: list[dict[str, Any]],
    fallback_policy: dict[str, Any],
) -> dict[str, Any]:
    has_explicit_policy = isinstance(value, dict)
    if has_explicit_policy:
        policy = dict(value)
    else:
        policy = dict(fallback_policy or {})
    expected_infos = set(required_info)
    for step in steps:
        expected_infos.update(str(field) for field in step.get("expected_user_info", []))
    if has_explicit_policy and isinstance(policy.get("target_info"), list):
        expected_infos.update(str(field) for field in policy["target_info"] if str(field).strip())
    default_policy = _default_slot_filling_policy(sorted(expected_infos))
    return {
        **default_policy,
        **policy,
        "enabled": True,
        "multi_slot_per_turn": True,
        "extract_scope": "all_skill_expected_user_info",
        "skip_satisfied_steps": True,
        "target_info": sorted(expected_infos),
    }


def _default_slot_filling_policy(expected_infos: list[str]) -> dict[str, Any]:
    return {
        "enabled": True,
        "multi_slot_per_turn": True,
        "extract_scope": "all_skill_expected_user_info",
        "skip_satisfied_steps": True,
        "description": "每轮用户消息都应同时抽取所有可识别的信息；如果用户一次提供多个字段，必须一次性写入 slot_updates，不要按步骤重复追问。",
        "target_info": expected_infos,
    }


def _normalize_actions(actions: list[str]) -> list[str]:
    aliases = {
        "ask_for_info": "ask_user",
        "ask": "ask_user",
        "reply": "answer_user",
        "respond": "answer_user",
    }
    normalized: list[str] = []
    for action in actions:
        value = aliases.get(action, action)
        if value not in normalized:
            normalized.append(value)
    return normalized


def _tool_actions(available_tools: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for tool in available_tools:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name") or "").strip()
        if name:
            actions.append(f"call_tool:{name}")
    return actions


def _infer_goals(raw: str) -> list[str]:
    clauses = [clause.strip() for clause in _split_clauses(raw) if clause.strip()]
    return clauses or ["理解用户诉求", "收集必要信息", "完成流程处理", "向用户反馈结果"]


def _infer_required_fields(raw: str) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    seen: set[str] = set()
    for clause in _split_clauses(raw):
        label = _extract_info_label(clause)
        if not label:
            continue
        field = _field_id(label, len(fields) + 1)
        if field in seen:
            continue
        fields.append((field, label))
        seen.add(field)
    return fields


def _split_clauses(text: str) -> list[str]:
    normalized = text.replace("\n", "，").replace("；", "，").replace(";", "，").replace(",", "，").replace("。", "，")
    return [part.strip() for part in normalized.split("，")]


def _extract_info_label(clause: str) -> str | None:
    text = clause.strip()
    for verb in ("获取", "收集", "询问", "确认", "记录", "填写", "提供", "输入"):
        if text.startswith(verb):
            label = text[len(verb) :].strip(" ：:，。")
            label = label.removeprefix("用户").removeprefix("客户").removeprefix("您的").strip(" 的")
            if label and not any(word in label for word in ("是否", "结果", "流程", "状态")):
                return label[:24]
    return None


def _field_id(label: str, index: int) -> str:
    common = {
        "姓名": "user_name",
        "名字": "user_name",
        "联系方式": "contact",
        "手机号": "phone",
        "电话": "phone",
    }
    for key, value in common.items():
        if key in label:
            return value
    ascii_slug = "".join(char.lower() if char.isalnum() else "_" for char in label if ord(char) < 128)
    ascii_slug = "_".join(part for part in ascii_slug.split("_") if part)
    return ascii_slug[:48] if ascii_slug else f"info_{index}"


def _slugify(title: str, raw: str) -> str:
    ascii_slug = "".join(char.lower() if char.isalnum() else "_" for char in title if ord(char) < 128)
    ascii_slug = "_".join(part for part in ascii_slug.split("_") if part)
    if ascii_slug:
        return ascii_slug[:48]
    digest = hashlib.md5(f"{title}:{raw}".encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
    return f"skill_{digest}"
