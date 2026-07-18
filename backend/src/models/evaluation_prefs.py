"""Phase 17.5 — Evaluation & Preferences Models.

Tables: evaluation_runs, user_preferences
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON, DateTime, Float, Integer, String, Text, Index, Boolean, ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    benchmark_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    results: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    errors: Mapped[Optional[list]] = mapped_column(JSON)
    trace_id: Mapped[Optional[str]] = mapped_column(String(128))
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_eval_runs_benchmark_status", "benchmark_name", "status"),
    )


class HallucinationAudit(Base):
    __tablename__ = "hallucination_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("evaluation_runs.id", ondelete="SET NULL"), index=True)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_hallucination: Mapped[Optional[bool]] = mapped_column(Boolean)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    keywords_detected: Mapped[Optional[list]] = mapped_column(JSON)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    notification_email: Mapped[Optional[str]] = mapped_column(String(320))
    alert_threshold: Mapped[int] = mapped_column(Integer, default=75, nullable=False)
    quiet_hours_start: Mapped[Optional[str]] = mapped_column(String(8))  # HH:MM
    quiet_hours_end: Mapped[Optional[str]] = mapped_column(String(8))
    theme: Mapped[str] = mapped_column(String(32), default="system", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    extra: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
