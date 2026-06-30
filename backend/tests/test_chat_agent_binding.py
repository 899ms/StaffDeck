from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.chat import (
    _bind_request_to_session_agent,
    _ensure_chat_agent_available,
    _user_message_metadata,
    create_chat_session,
)
from app.core.agent_loop import AgentLoop, AgentLoopPreconditionError
from app.db.models import AgentProfile, ChatSession, ModelConfig, Tenant, User
from app.session.session_schema import ChatSessionCreateRequest, ChatTurnRequest


def test_existing_chat_session_cannot_switch_agent() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        current_user = User(id="user_demo", tenant_id="tenant_demo", username="demo", password_hash="x")
        db.add(current_user)
        db.add(AgentProfile(id="agent_a", tenant_id="tenant_demo", name="客服 A", is_overall=False))
        db.add(AgentProfile(id="agent_b", tenant_id="tenant_demo", name="客服 B", is_overall=False))
        session = ChatSession(
            id="session_bound",
            tenant_id="tenant_demo",
            user_id="user_demo",
            agent_id="agent_a",
        )
        db.add(session)
        db.commit()

        request = ChatTurnRequest(
            tenant_id="tenant_demo",
            session_id=session.id,
            user_id="user_demo",
            agent_id="agent_b",
            message="你好",
        )

        with pytest.raises(HTTPException) as exc_info:
            _bind_request_to_session_agent(db, request, session, current_user)

        assert exc_info.value.status_code == 409
        assert db.get(ChatSession, session.id).agent_id == "agent_a"


def test_chat_agent_must_be_active_non_overall_agent() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        current_user = User(id="user_demo", tenant_id="tenant_demo", username="demo", password_hash="x")
        db.add(current_user)
        db.add(AgentProfile(id="agent_overall", tenant_id="tenant_demo", name="整体", is_overall=True))
        db.add(AgentProfile(id="agent_archived", tenant_id="tenant_demo", name="已归档", is_overall=False, status="archived"))
        db.commit()

        with pytest.raises(HTTPException) as missing:
            _ensure_chat_agent_available(db, "tenant_demo", None, current_user)
        with pytest.raises(HTTPException) as overall:
            _ensure_chat_agent_available(db, "tenant_demo", "agent_overall", current_user)
        with pytest.raises(HTTPException) as archived:
            _ensure_chat_agent_available(db, "tenant_demo", "agent_archived", current_user)

        assert missing.value.status_code == 400
        assert overall.value.status_code == 404
        assert archived.value.status_code == 404


def test_create_chat_session_always_creates_new_agent_session() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        current_user = User(id="user_demo", tenant_id="tenant_demo", username="demo", password_hash="x")
        db.add(current_user)
        db.add(
            AgentProfile(
                id="agent_demo",
                tenant_id="tenant_demo",
                name="研发",
                is_overall=False,
                metadata_json={"owner_user_id": "user_demo"},
            )
        )
        db.add(
            ChatSession(
                id="session_existing",
                tenant_id="tenant_demo",
                user_id="user_demo",
                agent_id="agent_demo",
            )
        )
        db.commit()

        first = create_chat_session(
            ChatSessionCreateRequest(tenant_id="tenant_demo", agent_id="agent_demo"),
            current_user=current_user,
            db=db,
        )
        second = create_chat_session(
            ChatSessionCreateRequest(tenant_id="tenant_demo", agent_id="agent_demo"),
            current_user=current_user,
            db=db,
        )
        session_rows = db.exec(select(ChatSession).where(ChatSession.agent_id == "agent_demo")).all()

        assert first.id != "session_existing"
        assert second.id not in {"session_existing", first.id}
        assert len(session_rows) == 3


def test_scheduled_task_chat_turn_marks_user_message_metadata() -> None:
    request = ChatTurnRequest(
        tenant_id="tenant_demo",
        session_id="session_demo",
        user_id="user_demo",
        agent_id="agent_demo",
        message="每天18点复盘差评",
        interaction_mode="scheduled_task",
    )

    assert _user_message_metadata(request) == {"interaction_mode": "scheduled_task"}


def test_normal_chat_turn_user_message_metadata_is_empty() -> None:
    request = ChatTurnRequest(
        tenant_id="tenant_demo",
        session_id="session_demo",
        user_id="user_demo",
        agent_id="agent_demo",
        message="每天18点复盘差评",
    )

    assert _user_message_metadata(request) == {}


def test_chat_turn_can_select_enabled_model_config() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        db.add(
            ModelConfig(
                id="model_default",
                tenant_id="tenant_demo",
                name="默认模型",
                api_key_encrypted="",
                model="default-model",
                is_default=True,
            )
        )
        db.add(
            ModelConfig(
                id="model_selected",
                tenant_id="tenant_demo",
                name="选择模型",
                api_key_encrypted="",
                model="selected-model",
            )
        )
        db.commit()
        loop = AgentLoop(db)

        model = loop._get_request_model(
            ChatTurnRequest(
                tenant_id="tenant_demo",
                agent_id="agent_demo",
                model_config_id="model_selected",
                message="你好",
            )
        )

        assert model is not None
        assert model.id == "model_selected"


def test_chat_turn_rejects_disabled_selected_model_config() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        db.add(
            ModelConfig(
                id="model_disabled",
                tenant_id="tenant_demo",
                name="停用模型",
                api_key_encrypted="",
                model="disabled-model",
                enabled=False,
            )
        )
        db.commit()
        loop = AgentLoop(db)

        with pytest.raises(AgentLoopPreconditionError) as exc_info:
            loop._get_request_model(
                ChatTurnRequest(
                    tenant_id="tenant_demo",
                    agent_id="agent_demo",
                    model_config_id="model_disabled",
                    message="你好",
                )
            )

        assert exc_info.value.code == "disabled_model_config"


def _test_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)
