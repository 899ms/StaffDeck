from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.db import get_session
from app.db.models import ModelConfig, Skill, Tool, utc_now
from app.llm import LLMError
from app.security.tenant import ensure_tenant
from app.skills import SkillDistiller
from app.skills.skill_schema import (
    SkillCard,
    SkillCreateRequest,
    SkillDistillRequest,
    SkillDistillResponse,
    SkillRead,
    SkillUpdateRequest,
)

router = APIRouter(prefix="/api/enterprise/skills", tags=["enterprise:skills"])


def skill_read(row: Skill) -> SkillRead:
    return SkillRead(
        id=row.id,
        tenant_id=row.tenant_id,
        skill_id=row.skill_id,
        version=row.version,
        name=row.name,
        business_domain=row.business_domain,
        description=row.description,
        content=SkillCard.model_validate(row.content_json),
        status=row.status,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


@router.get("", response_model=list[SkillRead])
def list_skills(tenant_id: str = Query(...), db: Session = Depends(get_session)) -> list[SkillRead]:
    ensure_tenant(db, tenant_id)
    rows = db.exec(select(Skill).where(Skill.tenant_id == tenant_id)).all()
    return [skill_read(row) for row in rows]


@router.post("", response_model=SkillRead)
def create_skill(request: SkillCreateRequest, db: Session = Depends(get_session)) -> SkillRead:
    ensure_tenant(db, request.tenant_id)
    existing = db.exec(
        select(Skill).where(
            Skill.tenant_id == request.tenant_id, Skill.skill_id == request.content.skill_id
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Skill ID already exists for this tenant")
    content = request.content.model_dump()
    row = Skill(
        tenant_id=request.tenant_id,
        skill_id=request.content.skill_id,
        version=request.content.version,
        name=request.content.name,
        business_domain=request.content.business_domain,
        description=request.content.description,
        content_json=content,
        status=request.status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return skill_read(row)


@router.get("/{skill_id}", response_model=SkillRead)
def get_skill(skill_id: str, tenant_id: str = Query(...), db: Session = Depends(get_session)) -> SkillRead:
    row = _get_skill(db, tenant_id, skill_id)
    return skill_read(row)


@router.put("/{skill_id}", response_model=SkillRead)
def update_skill(skill_id: str, request: SkillUpdateRequest, db: Session = Depends(get_session)) -> SkillRead:
    if request.content.skill_id != skill_id:
        raise HTTPException(status_code=400, detail="Path skill_id must match content.skill_id")
    row = _get_skill(db, request.tenant_id, skill_id)
    row.version = request.content.version
    row.name = request.content.name
    row.business_domain = request.content.business_domain
    row.description = request.content.description
    row.content_json = request.content.model_dump()
    if request.status:
        row.status = request.status
    row.updated_at = utc_now()
    db.add(row)
    db.commit()
    db.refresh(row)
    return skill_read(row)


@router.post("/{skill_id}/publish", response_model=SkillRead)
def publish_skill(skill_id: str, tenant_id: str = Query(...), db: Session = Depends(get_session)) -> SkillRead:
    row = _get_skill(db, tenant_id, skill_id)
    row.status = "published"
    row.updated_at = utc_now()
    db.add(row)
    db.commit()
    db.refresh(row)
    return skill_read(row)


@router.post("/{skill_id}/archive", response_model=SkillRead)
def archive_skill(skill_id: str, tenant_id: str = Query(...), db: Session = Depends(get_session)) -> SkillRead:
    row = _get_skill(db, tenant_id, skill_id)
    row.status = "archived"
    row.updated_at = utc_now()
    db.add(row)
    db.commit()
    db.refresh(row)
    return skill_read(row)


@router.post("/distill", response_model=SkillDistillResponse)
def distill_skill(request: SkillDistillRequest, db: Session = Depends(get_session)) -> SkillDistillResponse:
    ensure_tenant(db, request.tenant_id)
    model_config = _get_default_model(db, request.tenant_id)
    request = _with_available_tools(db, request)
    try:
        return SkillDistiller().distill(request, model_config)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/distill/stream")
def distill_skill_stream(request: SkillDistillRequest) -> StreamingResponse:
    def stream_events() -> Iterator[str]:
        with Session(get_session_engine()) as db:
            ensure_tenant(db, request.tenant_id)
            model_config = _get_default_model(db, request.tenant_id)
            enriched_request = _with_available_tools(db, request)
            yield _sse("status", {"text": "正在改写技能"})
            for item in SkillDistiller().stream_text(enriched_request, model_config):
                yield _sse(item["event"], item["data"])

    return StreamingResponse(stream_events(), media_type="text/event-stream")


def get_session_engine():
    from app.db import engine

    return engine


def _get_default_model(db: Session, tenant_id: str) -> ModelConfig:
    model_config = db.exec(
        select(ModelConfig).where(
            ModelConfig.tenant_id == tenant_id,
            ModelConfig.is_default == True,  # noqa: E712
            ModelConfig.enabled == True,  # noqa: E712
        )
    ).first()
    if not model_config:
        raise HTTPException(status_code=400, detail="No enabled default model config")
    return model_config


def _with_available_tools(db: Session, request: SkillDistillRequest) -> SkillDistillRequest:
    tools = db.exec(
        select(Tool).where(Tool.tenant_id == request.tenant_id, Tool.enabled == True)  # noqa: E712
    ).all()
    available_tools = [
        *request.available_tools,
        *[
            {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
            for tool in tools
        ],
    ]
    return request.model_copy(update={"available_tools": available_tools})


def _sse(event: object, data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _get_skill(db: Session, tenant_id: str, skill_id: str) -> Skill:
    ensure_tenant(db, tenant_id)
    row = db.exec(
        select(Skill).where(Skill.tenant_id == tenant_id, Skill.skill_id == skill_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Skill not found")
    return row
