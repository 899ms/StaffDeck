from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.chat import message_read, session_read
from app.db import get_session
from app.db.models import AgentEvent, ChatSession, Message, utc_now
from app.security.tenant import ensure_tenant

router = APIRouter(prefix="/api/enterprise/sessions", tags=["enterprise:sessions"])


@router.get("")
def list_sessions(tenant_id: str = Query(...), db: Session = Depends(get_session)) -> list[dict]:
    ensure_tenant(db, tenant_id)
    rows = db.exec(
        select(ChatSession).where(ChatSession.tenant_id == tenant_id).order_by(ChatSession.updated_at.desc())
    ).all()
    return [session_read(row).model_dump() for row in rows]


@router.get("/{session_id}")
def get_session_detail(
    session_id: str,
    tenant_id: str = Query(...),
    db: Session = Depends(get_session),
) -> dict:
    row = _get_chat_session(db, tenant_id, session_id)
    messages = db.exec(
        select(Message)
        .where(Message.tenant_id == tenant_id, Message.session_id == session_id)
        .order_by(Message.created_at)
    ).all()
    events = db.exec(
        select(AgentEvent)
        .where(AgentEvent.tenant_id == tenant_id, AgentEvent.session_id == session_id)
        .order_by(AgentEvent.created_at)
    ).all()
    return {
        "session": session_read(row).model_dump(),
        "messages": [message_read(message).model_dump() for message in messages],
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "payload": event.payload_json,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
    }


@router.post("/{session_id}/reset")
def reset_session(
    session_id: str,
    tenant_id: str = Query(...),
    db: Session = Depends(get_session),
) -> dict:
    row = _get_chat_session(db, tenant_id, session_id)
    row.active_skill_id = None
    row.active_step_id = None
    row.slots_json = {}
    row.skill_stack_json = []
    row.resume_after_answer_json = None
    row.summary = None
    row.last_agent_question = None
    row.status = "active"
    row.updated_at = utc_now()
    db.add(row)
    db.commit()
    db.refresh(row)
    return session_read(row).model_dump()


def _get_chat_session(db: Session, tenant_id: str, session_id: str) -> ChatSession:
    ensure_tenant(db, tenant_id)
    row = db.get(ChatSession, session_id)
    if not row or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return row

