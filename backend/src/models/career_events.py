"""CareerOS event audit foundation models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class CareerEvent(Base):
    """Unified, additive audit row for real product events."""

    __tablename__ = "career_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_uid: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_service: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_table: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    payload_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    evidence_json: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="medium", index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success", index=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_career_events_user_time", "user_id", "event_time"),
        Index("ix_career_events_type_time", "event_type", "event_time"),
        Index("ix_career_events_entity", "entity_type", "entity_id"),
        Index("ix_career_events_source_time", "source_service", "event_time"),
        Index("ix_career_events_trace", "trace_id"),
    )
