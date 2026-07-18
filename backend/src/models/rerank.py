"""Rerank run persistence model for enterprise monitoring."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Float, JSON, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class RerankRun(Base):
    __tablename__ = "rerank_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    chunks_submitted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunks_returned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    primary_provider: Mapped[str] = mapped_column(String(64), nullable=False, default="nvidia")
    primary_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    primary_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_strategy: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    fallback_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    circuit_breaker_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    confidence_avg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_distribution: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rank_correlation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rank_inversion_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    boost_skills_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    boost_sections_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    boost_chronology_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    top_chunk_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    top_chunk_scores: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
