"""Phase 17.7 — Generated Package Models.

Tables: generated_packages
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON, DateTime, Integer, String, Text, Index, ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class GeneratedPackage(Base):
    __tablename__ = "generated_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    resume_tailored: Mapped[Optional[str]] = mapped_column(Text)
    cover_letter: Mapped[Optional[str]] = mapped_column(Text)
    outreach_message: Mapped[Optional[str]] = mapped_column(Text)
    interview_guide: Mapped[Optional[str]] = mapped_column(Text)
    readiness_summary: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON)
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_generated_packages_user_status", "user_id", "status"),
    )
