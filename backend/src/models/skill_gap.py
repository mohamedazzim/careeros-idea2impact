"""Evidence-backed skill gap analysis models for CareerOS M5."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class SkillGapAnalysisRun(Base):
    __tablename__ = "skill_gap_analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    target_role_slug: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="job", index=True)
    source_service: Mapped[str] = mapped_column(String(128), nullable=False, default="services.skill_gap.skill_gap_engine")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    required_skill_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_skill_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidenced_skill_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    learning_skill_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validated_skill_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    insufficient_data_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="low", index=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_skill_gap_analysis_runs_user_scope", "user_id", "source_scope"),
        Index("ix_skill_gap_analysis_runs_user_job", "user_id", "job_id"),
        Index("ix_skill_gap_analysis_runs_scope_status", "source_scope", "status"),
    )


class SkillGapFinding(Base):
    __tablename__ = "skill_gap_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    run_uid: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("skill_gap_analysis_runs.run_uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    skill_node_uid: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    skill_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(256), nullable=False)
    required_by_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    required_by_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    gap_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_evidence_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    reason_summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    calculation_metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_skill_gap_findings_user_skill", "user_id", "skill_slug"),
        Index("ix_skill_gap_findings_run_status", "run_uid", "gap_status"),
        UniqueConstraint("run_uid", "skill_slug", "required_by_type", "required_by_id", name="uq_skill_gap_findings_run_skill_source"),
    )


class SkillGapFindingEvidence(Base):
    __tablename__ = "skill_gap_finding_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    finding_uid: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("skill_gap_findings.finding_uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    skill_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_table: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    evidence_strength: Mapped[str] = mapped_column(String(16), nullable=False, default="weak", index=True)
    supports_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    quote_or_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="low", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_skill_gap_finding_evidence_user_skill", "user_id", "skill_slug"),
        Index("ix_skill_gap_finding_evidence_type", "evidence_type", "supports_status"),
    )


class UserSkillGapSnapshot(Base):
    __tablename__ = "user_skill_gap_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_role_slug: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    run_uid: Mapped[str] = mapped_column(String(64), ForeignKey("skill_gap_analysis_runs.run_uid", ondelete="CASCADE"), nullable=False, index=True)
    summary_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    learning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidenced_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    insufficient_data_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_user_skill_gap_snapshots_user_job", "user_id", "job_id"),
        Index("ix_user_skill_gap_snapshots_user_role", "user_id", "target_role_slug"),
    )
