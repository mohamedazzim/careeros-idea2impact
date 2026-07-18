"""Persisted decisions produced by the public Opportunity Alert Agent."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class OpportunityAlert(Base):
    __tablename__ = "opportunity_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str] = mapped_column(String(256), nullable=False)
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    hours_since_posted: Mapped[float] = mapped_column(Float, nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    called: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    call_sid: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    webhook_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    provider_response: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
