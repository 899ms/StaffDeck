from __future__ import annotations

import re
from typing import Any

from sqlmodel import Session, select

from app.db.models import ChatSession, MemoryRecord, Tool, User, utc_now
from app.session.session_schema import ChatTurnRequest, StepAgentResult
from app.tools.tool_schema import ToolResult


class MemoryService:
    def __init__(self, db: Session):
        self.db = db

    def recall(self, tenant_id: str, user_id: str, query: str, limit: int = 5) -> list[MemoryRecord]:
        rows = list(
            self.db.exec(
                select(MemoryRecord)
                .where(
                    MemoryRecord.tenant_id == tenant_id,
                    MemoryRecord.user_id == user_id,
                    MemoryRecord.kind != "conversation",
                )
                .order_by(MemoryRecord.updated_at.desc())
                .limit(80)
            ).all()
        )
        query_terms = _terms(query)
        scored = sorted(
            rows,
            key=lambda row: (_score(row.content, query_terms), row.importance, row.updated_at),
            reverse=True,
        )
        return [row for row in scored if _score(row.content, query_terms) > 0][:limit] or rows[: min(3, len(rows))]

    def capture_turn(
        self,
        request: ChatTurnRequest,
        session: ChatSession,
        reply: str,
        step_result: StepAgentResult,
        tool_result: ToolResult | None,
    ) -> list[MemoryRecord]:
        user = self.db.get(User, request.user_id)
        username = user.username if user else request.user_id
        records: list[MemoryRecord] = []

        profile = _extract_profile_memory(request.message)
        if profile:
            records.append(
                self._add_memory(
                    tenant_id=request.tenant_id,
                    user_id=request.user_id,
                    username=username,
                    session_id=session.id,
                    kind="profile",
                    content=profile,
                    importance=0.95,
                    metadata={"source": "profile_extractor"},
                )
            )

        summary = _turn_summary(request.message, reply, step_result, tool_result)
        if summary:
            records.append(
                self._upsert_summary(
                    tenant_id=request.tenant_id,
                    user_id=request.user_id,
                    username=username,
                    session_id=session.id,
                    turn_note=summary,
                    metadata={
                        "active_skill_id": session.active_skill_id,
                        "active_step_id": session.active_step_id,
                        "tool_name": tool_result.tool_name if tool_result else None,
                    },
                )
            )
        return records

    def _add_memory(
        self,
        tenant_id: str,
        user_id: str,
        username: str | None,
        session_id: str,
        kind: str,
        content: str,
        importance: float,
        metadata: dict[str, Any],
    ) -> MemoryRecord:
        existing = self.db.exec(
            select(MemoryRecord).where(
                MemoryRecord.tenant_id == tenant_id,
                MemoryRecord.user_id == user_id,
                MemoryRecord.kind == kind,
                MemoryRecord.content == content,
            )
        ).first()
        if existing:
            existing.updated_at = utc_now()
            existing.session_id = session_id
            existing.metadata_json = {**(existing.metadata_json or {}), **metadata}
            self.db.add(existing)
            return existing
        record = MemoryRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            username=username,
            session_id=session_id,
            kind=kind,
            content=content[:1200],
            importance=importance,
            metadata_json=metadata,
        )
        self.db.add(record)
        return record

    def _upsert_summary(
        self,
        tenant_id: str,
        user_id: str,
        username: str | None,
        session_id: str,
        turn_note: str,
        metadata: dict[str, Any],
    ) -> MemoryRecord:
        existing = self.db.exec(
            select(MemoryRecord).where(
                MemoryRecord.tenant_id == tenant_id,
                MemoryRecord.user_id == user_id,
                MemoryRecord.kind == "summary",
            )
        ).first()
        now = utc_now()
        if existing:
            existing.content = _merge_summary(existing.content, turn_note)
            existing.username = username
            existing.session_id = session_id
            existing.importance = 0.8
            existing.updated_at = now
            existing.metadata_json = {
                **(existing.metadata_json or {}),
                **metadata,
                "turn_count": int((existing.metadata_json or {}).get("turn_count", 0)) + 1,
            }
            self.db.add(existing)
            return existing
        record = MemoryRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            username=username,
            session_id=session_id,
            kind="summary",
            content=_merge_summary("", turn_note),
            importance=0.8,
            metadata_json={**metadata, "turn_count": 1},
        )
        self.db.add(record)
        return record


def memory_read(record: MemoryRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "user_id": record.user_id,
        "username": record.username,
        "session_id": record.session_id,
        "kind": record.kind,
        "content": record.content,
        "importance": record.importance,
        "metadata": record.metadata_json or {},
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def tool_read_for_activity(tool: Tool | None, result: ToolResult | None = None) -> dict[str, Any]:
    return {
        "name": result.tool_name if result else tool.name if tool else "",
        "display_name": tool.display_name if tool else None,
        "description": tool.description if tool else None,
        "success": result.success if result else None,
    }


def _turn_summary(
    message: str,
    reply: str,
    step_result: StepAgentResult,
    tool_result: ToolResult | None,
) -> str:
    parts = []
    message_text = message.strip()
    reply_text = reply.strip()
    if message_text:
        parts.append(f"用户本轮诉求：{message_text[:220]}")
    if reply_text:
        parts.append(f"最近处理结果：{reply_text[:220]}")
    if step_result.slot_updates:
        parts.append(f"已记录槽位：{step_result.slot_updates}")
    if tool_result:
        parts.append(f"工具 {tool_result.tool_name}：{'成功' if tool_result.success else '失败'}")
    text = "\n".join(part for part in parts if part)
    return text[:700]


def _merge_summary(existing: str, turn_note: str) -> str:
    header = "用户长期摘要"
    existing_lines = [
        line.removeprefix("- ").strip()
        for line in existing.splitlines()
        if line.strip() and line.strip() != header and not line.strip().startswith("更新时间")
    ]
    note = turn_note.replace("\n", "；").strip()
    lines: list[str] = []
    for line in existing_lines + [note]:
        compact = re.sub(r"\s+", " ", line).strip("； ")
        if compact and compact not in lines:
            lines.append(compact[:260])
    lines = lines[-8:]
    return "\n".join([header, *[f"- {line}" for line in lines]])


def _extract_profile_memory(message: str) -> str | None:
    normalized = message.strip()
    patterns = [
        r"(?:我叫|我是|我的名字是)\s*([\u4e00-\u9fa5A-Za-z0-9_\-]{2,24})",
        r"(?:叫我)\s*([\u4e00-\u9fa5A-Za-z0-9_\-]{2,24})",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return f"用户姓名/称呼：{match.group(1)}"
    if any(keyword in normalized for keyword in ("我喜欢", "我偏好", "我希望", "以后")):
        return f"用户偏好：{normalized[:300]}"
    return None


def _terms(text: str) -> set[str]:
    words = set(re.findall(r"[A-Za-z0-9_]{2,}", text.lower()))
    words.update(char for char in text if "\u4e00" <= char <= "\u9fff")
    return words


def _score(content: str, query_terms: set[str]) -> int:
    if not query_terms:
        return 1
    lower = content.lower()
    return sum(1 for term in query_terms if term in lower)
