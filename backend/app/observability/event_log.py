from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.db.models import AgentEvent


class EventLog:
    def __init__(self, db: Session):
        self.db = db

    def record(self, tenant_id: str, session_id: str, event_type: str, payload: dict[str, Any]) -> AgentEvent:
        event = AgentEvent(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type=event_type,
            payload_json=payload,
        )
        self.db.add(event)
        return event

