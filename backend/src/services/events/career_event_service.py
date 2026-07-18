"""Reusable service for persistable CareerOS event audit rows."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import async_session
from src.models.career_events import CareerEvent

logger = logging.getLogger(__name__)

_SECRET_KEY_RE = re.compile(r"(pass(word)?|secret|token|api[_-]?key|authorization|cookie|session)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"(?<![\w.-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")


def _now_utc() -> datetime:
    current = datetime.utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(tzinfo=None)


class CareerEventService:
    """Writes sanitized audit rows without changing primary business behavior."""

    @staticmethod
    def sanitize_payload(payload: Any, *, depth: int = 0, max_depth: int = 5) -> Any:
        if payload is None:
            return None
        if depth >= max_depth:
            return "[TRUNCATED]"
        if isinstance(payload, dict):
            safe: dict[str, Any] = {}
            for key, value in payload.items():
                key_text = str(key)
                if _SECRET_KEY_RE.search(key_text):
                    safe[key_text] = "[REDACTED]"
                    continue
                safe[key_text] = CareerEventService.sanitize_payload(value, depth=depth + 1, max_depth=max_depth)
            return safe
        if isinstance(payload, list):
            return [CareerEventService.sanitize_payload(item, depth=depth + 1, max_depth=max_depth) for item in payload[:50]]
        if isinstance(payload, str):
            text = _EMAIL_RE.sub("[REDACTED_EMAIL]", payload)
            text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
            if len(text) > 2000:
                return text[:2000] + "..."
            return text
        if isinstance(payload, (int, float, bool)):
            return payload
        if isinstance(payload, datetime):
            if payload.tzinfo is None:
                return payload.replace(tzinfo=timezone.utc).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            return payload.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return str(payload)

    @staticmethod
    def build_evidence_ref(
        *,
        table: str,
        source_id: str | int | None,
        kind: str = "db_record",
        note: str | None = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        evidence = {
            "type": kind,
            "table": table,
            "id": str(source_id) if source_id is not None else None,
        }
        if note:
            evidence["note"] = note
        if extra:
            evidence["extra"] = CareerEventService.sanitize_payload(extra)
        return evidence

    async def emit_event(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        entity_type: str,
        source_service: str,
        user_id: str | None = None,
        entity_id: str | None = None,
        source_table: str | None = None,
        source_id: str | int | None = None,
        payload: Any = None,
        evidence: Optional[list[dict[str, Any]]] = None,
        confidence: str = "medium",
        trace_id: str | None = None,
        request_id: str | None = None,
        provider: str | None = None,
        status: str = "success",
        schema_version: str = "v1",
        event_time: datetime | None = None,
        event_uid: str | None = None,
        commit: bool = True,
    ) -> Optional[CareerEvent]:
        try:
            async with async_session() as event_db:
                if event_uid:
                    existing = await event_db.execute(
                        select(CareerEvent).where(CareerEvent.event_uid == event_uid)
                    )
                    found = existing.scalar_one_or_none()
                    if found:
                        return found

                event = CareerEvent(
                    event_uid=event_uid or str(uuid.uuid4()),
                    event_type=event_type,
                    user_id=user_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    source_service=source_service,
                    source_table=source_table,
                    source_id=str(source_id) if source_id is not None else None,
                    event_time=(event_time or _now_utc()),
                    payload_json=self.sanitize_payload(payload),
                    evidence_json=self.sanitize_payload(evidence or []),
                    confidence=confidence,
                    trace_id=trace_id,
                    request_id=request_id,
                    provider=provider,
                    status=status,
                    schema_version=schema_version,
                )
                event_db.add(event)
                await event_db.flush()
                if commit:
                    await event_db.commit()
                await event_db.refresh(event)
                return event
        except Exception as exc:
            logger.warning(
                "career event emit failed",
                extra={
                    "event_type": event_type,
                    "entity_type": entity_type,
                    "source_service": source_service,
                    "status": status,
                    "error": str(exc),
                },
            )
            return None

    async def emit_insufficient_data_event(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        entity_type: str,
        source_service: str,
        user_id: str | None = None,
        entity_id: str | None = None,
        source_table: str | None = None,
        source_id: str | int | None = None,
        payload: Any = None,
        evidence: Optional[list[dict[str, Any]]] = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        provider: str | None = None,
        commit: bool = True,
    ) -> Optional[CareerEvent]:
        return await self.emit_event(
            db,
            event_type=event_type,
            entity_type=entity_type,
            source_service=source_service,
            user_id=user_id,
            entity_id=entity_id,
            source_table=source_table,
            source_id=source_id,
            payload=payload,
            evidence=evidence,
            confidence="low",
            trace_id=trace_id,
            request_id=request_id,
            provider=provider,
            status="insufficient_data",
            commit=commit,
        )

    async def list_events(
        self,
        db: AsyncSession,
        *,
        user_id: str | None,
        event_type: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        source_service: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CareerEvent], int]:
        conditions = []
        if user_id is not None:
            conditions.append(CareerEvent.user_id == user_id)
        if event_type:
            conditions.append(CareerEvent.event_type == event_type)
        if entity_type:
            conditions.append(CareerEvent.entity_type == entity_type)
        if entity_id:
            conditions.append(CareerEvent.entity_id == entity_id)
        if source_service:
            conditions.append(CareerEvent.source_service == source_service)

        count_q = select(func.count()).select_from(CareerEvent)
        data_q = select(CareerEvent)
        for condition in conditions:
            count_q = count_q.where(condition)
            data_q = data_q.where(condition)
        count_result = await db.execute(count_q)
        total = int(count_result.scalar() or 0)
        data_result = await db.execute(
            data_q.order_by(CareerEvent.event_time.desc(), CareerEvent.id.desc()).offset(offset).limit(limit)
        )
        return list(data_result.scalars().all()), total

    async def get_event_by_uid(
        self,
        db: AsyncSession,
        *,
        event_uid: str,
        user_id: str | None,
    ) -> Optional[CareerEvent]:
        conditions = [CareerEvent.event_uid == event_uid]
        if user_id is not None:
            conditions.append(CareerEvent.user_id == user_id)
        result = await db.execute(select(CareerEvent).where(*conditions))
        return result.scalar_one_or_none()


_SERVICE: Optional[CareerEventService] = None


def get_career_event_service() -> CareerEventService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = CareerEventService()
    return _SERVICE
