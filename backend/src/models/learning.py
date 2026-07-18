"""Learning path models for verified skill-gap resources."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    channel_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_free: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    language: Mapped[str] = mapped_column(String(32), default="en")
    trust_score: Mapped[float] = mapped_column(Float, default=0.75)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.75)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.5)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    path_items: Mapped[list["LearningPathItem"]] = relationship("LearningPathItem", back_populates="resource")
    provenance_records: Mapped[list["ResourceProvenanceRecord"]] = relationship(
        "ResourceProvenanceRecord",
        back_populates="resource",
    )
    learning_sessions: Mapped[list["LearningSession"]] = relationship("LearningSession", back_populates="resource")
    resource_feedback: Mapped[list["ResourceFeedback"]] = relationship("ResourceFeedback", back_populates="resource")
    resource_outcomes: Mapped[list["ResourceOutcome"]] = relationship("ResourceOutcome", back_populates="resource")
    activity_events: Mapped[list["LearningActivityEvent"]] = relationship("LearningActivityEvent", back_populates="resource")

    __table_args__ = (
        UniqueConstraint("skill_slug", "source_url", name="uq_learning_resources_skill_source"),
        Index("ix_learning_resources_skill_verified", "skill_slug", "last_verified_at"),
    )


class UserSkillLearningPath(Base):
    __tablename__ = "user_skill_learning_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    skill_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    job_match_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_matches.id", ondelete="SET NULL"), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    estimated_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resource_status: Mapped[str] = mapped_column(String(32), nullable=False, default="available")
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["LearningPathItem"]] = relationship(
        "LearningPathItem",
        back_populates="learning_path",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "skill_slug", name="uq_learning_paths_user_skill"),
        Index("ix_learning_paths_user_priority", "user_id", "priority"),
    )


class LearningPathItem(Base):
    __tablename__ = "learning_path_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learning_path_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_skill_learning_paths.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    practice_project: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    learning_path: Mapped["UserSkillLearningPath"] = relationship(back_populates="items")
    resource: Mapped[Optional["LearningResource"]] = relationship(back_populates="path_items")


class ResourceDiscoveryRun(Base):
    __tablename__ = "learning_resource_discovery_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    skill_slug: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    skill_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    candidate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stored_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    request_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column("request_payload", JSON, nullable=True)
    response_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column("response_payload", JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    provenance_records: Mapped[list["ResourceProvenanceRecord"]] = relationship(
        "ResourceProvenanceRecord",
        back_populates="discovery_run",
    )

    __table_args__ = (
        Index("ix_learning_resource_discovery_runs_skill_status", "skill_slug", "status"),
    )


class ResourceProvenanceRecord(Base):
    __tablename__ = "learning_resource_provenance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provenance_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    discovery_run_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("learning_resource_discovery_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    skill_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    provenance_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    source_table: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_pk: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    trust_score: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.0)
    score_total: Mapped[float] = mapped_column(Float, default=0.0)
    score_formula: Mapped[str] = mapped_column(String(256), default="trust*0.45 + relevance*0.35 + freshness*0.20")
    score_breakdown: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resource: Mapped[Optional["LearningResource"]] = relationship(back_populates="provenance_records")
    discovery_run: Mapped[Optional["ResourceDiscoveryRun"]] = relationship(back_populates="provenance_records")


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provenance_uid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    path_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("user_skill_learning_paths.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    path_item_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("learning_path_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    skill_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="opened", index=True)
    source_ui: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    external_resource_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resource: Mapped[Optional["LearningResource"]] = relationship(back_populates="learning_sessions")
    feedback: Mapped[list["ResourceFeedback"]] = relationship("ResourceFeedback", back_populates="session")

    __table_args__ = (
        Index("ix_learning_sessions_user_resource_status", "user_id", "resource_id", "status"),
    )


class ResourceFeedback(Base):
    __tablename__ = "resource_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feedback_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provenance_uid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    session_uid: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("learning_sessions.session_uid", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    skill_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    difficulty: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    would_recommend: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    helpfulness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    outcome_tag: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resource: Mapped[Optional["LearningResource"]] = relationship(back_populates="resource_feedback")
    session: Mapped[Optional["LearningSession"]] = relationship(back_populates="feedback")

    __table_args__ = (
        Index("ix_resource_feedback_user_resource", "user_id", "resource_id"),
    )


class ResourceOutcome(Base):
    __tablename__ = "resource_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    provenance_uid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    skill_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    completion_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    feedback_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completion_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    drop_off_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recommendation_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    average_completion_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    average_duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_calculated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="insufficient_data", index=True)
    calculation_metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resource: Mapped[Optional["LearningResource"]] = relationship(back_populates="resource_outcomes")


class LearningActivityEvent(Base):
    __tablename__ = "learning_activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provenance_uid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    session_uid: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("learning_sessions.session_uid", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    path_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("user_skill_learning_paths.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    path_item_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("learning_path_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    skill_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    payload_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    resource: Mapped[Optional["LearningResource"]] = relationship(back_populates="activity_events")
