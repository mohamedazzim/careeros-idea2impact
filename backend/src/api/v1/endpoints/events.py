"""Authenticated readback for unified CareerOS audit events."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.session import get_db
from src.services.events import get_career_event_service

router = APIRouter(prefix="/events", tags=["Events"])


class CareerEventResponse(BaseModel):
    event_uid: str
    event_type: str
    user_id: Optional[str] = None
    entity_type: str
    entity_id: Optional[str] = None
    source_service: str
    source_table: Optional[str] = None
    source_id: Optional[str] = None
    event_time: str
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: str
    trace_id: Optional[str] = None
    request_id: Optional[str] = None
    provider: Optional[str] = None
    status: str
    schema_version: str
    created_at: str


class CareerEventsListResponse(BaseModel):
    status: str
    total: int
    limit: int
    offset: int
    events: list[CareerEventResponse] = Field(default_factory=list)


def _serialize_event(event) -> CareerEventResponse:
    return CareerEventResponse(
        event_uid=event.event_uid,
        event_type=event.event_type,
        user_id=event.user_id,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        source_service=event.source_service,
        source_table=event.source_table,
        source_id=event.source_id,
        event_time=event.event_time.isoformat() if event.event_time else "",
        payload=event.payload_json or {},
        evidence=event.evidence_json or [],
        confidence=event.confidence,
        trace_id=event.trace_id,
        request_id=event.request_id,
        provider=event.provider,
        status=event.status,
        schema_version=event.schema_version,
        created_at=event.created_at.isoformat() if event.created_at else "",
    )


@router.get("", response_model=CareerEventsListResponse)
async def list_events(
    event_type: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[str] = Query(default=None),
    source_service: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id and user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    service = get_career_event_service()
    events, total = await service.list_events(
        db,
        user_id=user_id or user["sub"],
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        source_service=source_service,
        limit=limit,
        offset=offset,
    )
    return CareerEventsListResponse(
        status="ok",
        total=total,
        limit=limit,
        offset=offset,
        events=[_serialize_event(event) for event in events],
    )


@router.get("/{event_uid}", response_model=CareerEventResponse)
async def get_event(
    event_uid: str,
    user_id: Optional[str] = Query(default=None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id and user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    service = get_career_event_service()
    event = await service.get_event_by_uid(db, event_uid=event_uid, user_id=user_id or user["sub"])
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _serialize_event(event)
