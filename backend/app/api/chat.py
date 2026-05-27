from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.core import AgentLoop
from app.db import engine, get_session
from app.db.models import AgentEvent, ChatSession, Message, User, new_id, utc_now
from app.security.auth import get_current_user
from app.security.tenant import ensure_tenant
from app.session.session_schema import (
    ChatSessionCreateRequest,
    ChatSessionRead,
    ChatSessionUpdateRequest,
    ChatTurnRequest,
    ChatTurnResponse,
    MessageRead,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def session_read(row: ChatSession) -> ChatSessionRead:
    return ChatSessionRead(
        id=row.id,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        title=row.title,
        active_skill_id=row.active_skill_id,
        active_step_id=row.active_step_id,
        status=row.status,
        summary=row.summary,
        last_agent_question=row.last_agent_question,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def message_read(row: Message) -> MessageRead:
    return MessageRead(
        id=row.id,
        tenant_id=row.tenant_id,
        session_id=row.session_id,
        role=row.role,
        content=row.content,
        created_at=row.created_at.isoformat(),
    )


@router.post("/turn", response_model=ChatTurnResponse)
def chat_turn(
    request: ChatTurnRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ChatTurnResponse:
    _ensure_request_tenant(request.tenant_id, current_user)
    request = request.model_copy(update={"user_id": current_user.id})
    if request.session_id:
        _ensure_chat_session_available(db, request.tenant_id, current_user.id, request.session_id)
    ensure_tenant(db, request.tenant_id)
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    return AgentLoop(db).handle_turn(request)


@router.post("/stream")
def chat_stream(
    request: ChatTurnRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> StreamingResponse:
    _ensure_request_tenant(request.tenant_id, current_user)
    request = request.model_copy(update={"user_id": current_user.id})
    ensure_tenant(db, request.tenant_id)
    if request.session_id:
        _ensure_chat_session_available(db, request.tenant_id, current_user.id, request.session_id)
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    def stream_events() -> Iterator[str]:
        with Session(engine) as db:
            ensure_tenant(db, request.tenant_id)
            for item in AgentLoop(db).handle_turn_stream(request):
                yield _sse(item["event"], item["data"])

    return StreamingResponse(stream_events(), media_type="text/event-stream")


def _sse(event: object, data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/sessions", response_model=ChatSessionRead)
def create_chat_session(
    request: ChatSessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ChatSessionRead:
    _ensure_request_tenant(request.tenant_id, current_user)
    ensure_tenant(db, request.tenant_id)
    title = _normalize_title(request.title)
    row = ChatSession(
        id=new_id("session"),
        tenant_id=request.tenant_id,
        user_id=current_user.id,
        title=title,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return session_read(row)


@router.get("/sessions", response_model=list[ChatSessionRead])
def list_chat_sessions(
    tenant_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[ChatSessionRead]:
    _ensure_request_tenant(tenant_id, current_user)
    ensure_tenant(db, tenant_id)
    rows = db.exec(
        select(ChatSession)
        .where(ChatSession.tenant_id == tenant_id, ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    ).all()
    return [session_read(row) for row in rows]


@router.put("/sessions/{session_id}", response_model=ChatSessionRead)
def rename_chat_session(
    session_id: str,
    request: ChatSessionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ChatSessionRead:
    _ensure_request_tenant(request.tenant_id, current_user)
    row = _get_user_chat_session(db, request.tenant_id, current_user.id, session_id)
    row.title = _normalize_title(request.title)
    row.updated_at = utc_now()
    db.add(row)
    db.commit()
    db.refresh(row)
    return session_read(row)


@router.delete("/sessions/{session_id}")
def delete_chat_session(
    session_id: str,
    tenant_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, str]:
    _ensure_request_tenant(tenant_id, current_user)
    row = _get_user_chat_session(db, tenant_id, current_user.id, session_id)
    messages = db.exec(
        select(Message).where(Message.tenant_id == tenant_id, Message.session_id == session_id)
    ).all()
    events = db.exec(
        select(AgentEvent).where(AgentEvent.tenant_id == tenant_id, AgentEvent.session_id == session_id)
    ).all()
    for message in messages:
        db.delete(message)
    for event in events:
        db.delete(event)
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@router.get("/sessions/{session_id}/messages", response_model=list[MessageRead])
def list_chat_messages(
    session_id: str,
    tenant_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[MessageRead]:
    _ensure_request_tenant(tenant_id, current_user)
    ensure_tenant(db, tenant_id)
    chat_session = db.get(ChatSession, session_id)
    if not chat_session or chat_session.tenant_id != tenant_id or chat_session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = db.exec(
        select(Message)
        .where(Message.tenant_id == tenant_id, Message.session_id == session_id)
        .order_by(Message.created_at)
    ).all()
    return [message_read(row) for row in rows]


def _get_user_chat_session(db: Session, tenant_id: str, user_id: str, session_id: str) -> ChatSession:
    ensure_tenant(db, tenant_id)
    row = db.get(ChatSession, session_id)
    if not row or row.tenant_id != tenant_id or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return row


def _ensure_chat_session_available(db: Session, tenant_id: str, user_id: str, session_id: str) -> None:
    ensure_tenant(db, tenant_id)
    row = db.get(ChatSession, session_id)
    if row and (row.tenant_id != tenant_id or row.user_id != user_id):
        raise HTTPException(status_code=404, detail="Session not found")


def _ensure_request_tenant(tenant_id: str, current_user: User) -> None:
    if tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")


def _normalize_title(value: str | None) -> str | None:
    if value is None:
        return None
    title = value.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Session title cannot be empty")
    return title[:80]
