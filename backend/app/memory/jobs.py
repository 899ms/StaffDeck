from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.async_jobs import AsyncJob, enqueue_async_job
from app.db import engine
from app.db.models import AgentEvent, ChatSession, ModelConfig
from app.memory.service import MemoryService, memory_read
from app.observability import EventLog
from app.observability.spans import bind_span_sink
from app.session.session_schema import ChatTurnRequest, StepAgentResult
from app.tools.tool_schema import ToolResult


def enqueue_memory_capture(
    request: ChatTurnRequest,
    session_id: str,
    reply: str,
    step_result: StepAgentResult,
    tool_result: ToolResult | None,
    model_config_id: str,
    recent_messages: list[dict[str, str]],
) -> AsyncJob:
    payload = {
        "request": request.model_dump(mode="json"),
        "session_id": session_id,
        "reply": reply,
        "step_result": step_result.model_dump(mode="json"),
        "tool_result": tool_result.model_dump(mode="json") if tool_result else None,
        "model_config_id": model_config_id,
        "recent_messages": recent_messages,
    }
    return enqueue_async_job(
        "memory.capture_turn",
        run_memory_capture_job,
        payload,
        metadata={
            "tenant_id": request.tenant_id,
            "session_id": session_id,
            "user_id": request.user_id,
        },
    )


def run_memory_capture_job(payload: dict[str, Any]) -> None:
    request = ChatTurnRequest.model_validate(payload["request"])
    session_id = str(payload["session_id"])
    model_config_id = str(payload["model_config_id"])
    step_result = StepAgentResult.model_validate(payload["step_result"])
    tool_result = ToolResult.model_validate(payload["tool_result"]) if payload.get("tool_result") else None
    recent_messages = _normalize_recent_messages(payload.get("recent_messages"))
    reply = str(payload.get("reply") or "")

    with Session(engine) as db:
        events = EventLog(db)
        chat_session = db.get(ChatSession, session_id)
        model_config = db.get(ModelConfig, model_config_id)
        if not chat_session or not model_config:
            events.record(
                request.tenant_id,
                session_id,
                "memory_error",
                {
                    "message": "后台 Memory 任务缺少 session 或 model_config。",
                    "missing_session": not bool(chat_session),
                    "missing_model_config": not bool(model_config),
                },
            )
            db.commit()
            return

        user_events = db.exec(
            select(AgentEvent)
            .where(
                AgentEvent.tenant_id == request.tenant_id,
                AgentEvent.session_id == session_id,
                AgentEvent.event_type == "user_message_received",
            )
            .order_by(AgentEvent.created_at.desc(), AgentEvent.id.desc())
        ).all()
        latest_user_event = next(
            (
                event
                for event in user_events
                if request.client_turn_id
                and str((event.payload_json or {}).get("client_turn_id") or "")
                == request.client_turn_id
            ),
            user_events[0] if user_events else None,
        )
        latest_user_payload = dict(latest_user_event.payload_json or {}) if latest_user_event else {}
        turn_id = str(
            latest_user_payload.get("turn_id")
            or latest_user_payload.get("user_message_id")
            or latest_user_payload.get("message_id")
            or ""
        )

        def persist_span(event_type: str, event_payload: dict[str, Any]) -> None:
            traced_payload = dict(event_payload)
            if turn_id:
                traced_payload.setdefault("turn_id", turn_id)
                traced_payload.setdefault("user_message_id", turn_id)
            if request.client_turn_id:
                traced_payload.setdefault("client_turn_id", request.client_turn_id)
            events.record(request.tenant_id, session_id, event_type, traced_payload)
            db.commit()

        try:
            with bind_span_sink(persist_span):
                rows = MemoryService(db).capture_turn(
                    request,
                    chat_session,
                    reply,
                    step_result,
                    tool_result,
                    model_config,
                    recent_messages,
                )
        except Exception as exc:  # noqa: BLE001 - persist failure without affecting the request path.
            events.record(
                request.tenant_id,
                session_id,
                "memory_error",
                {"message": str(exc)},
            )
            db.commit()
            return

        saved = [memory_read(row) for row in rows]
        if saved:
            events.record(
                request.tenant_id,
                session_id,
                "memory_saved",
                {"memories": saved, "async": True},
            )
        db.commit()


def _normalize_recent_messages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    messages: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role and content:
            messages.append({"role": role, "content": content})
    return messages[-12:]
