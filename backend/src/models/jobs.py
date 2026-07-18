"""Phase 17.5 — Jobs Intelligence Models.

Tables: jobs, job_matches
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON, DateTime, Float, Integer, String, Text, Index, Boolean, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(256))
    location: Mapped[Optional[str]] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64), default="linkedin")
    source_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_job_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    apply_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    posted_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    original_provider_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    freshness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    freshness_bucket: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    provider_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    apply_url_valid: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    opportunity_priority_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(String(32), default="NEW", index=True)
    salary_range: Mapped[Optional[str]] = mapped_column(String(128))
    skills_required: Mapped[Optional[list]] = mapped_column(JSON)
    match_score: Mapped[Optional[float]] = mapped_column(Float)
    match_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # -- India market classification fields --
    location_country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    location_region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_remote: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=False)
    remote_region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_india_eligible: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=False)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eligibility_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ingestion_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # -- Tech-role classification fields --
    is_tech_role: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None)
    tech_role_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tech_role_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    role_classification_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # -- Experience requirement fields --
    experience_min_years: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    experience_max_years: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    seniority_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    experience_filter_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        Index("ix_jobs_source_status", "source", "status"),
        Index("ix_jobs_title_search", "title"),
        Index("ix_jobs_india_eligible", "is_india_eligible", postgresql_where="is_india_eligible = true"),
        Index("ix_jobs_provider_active", "source", "status", postgresql_where="status = 'active'"),
    )


class JobMatch(Base):
    __tablename__ = "job_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_job_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    skill_match: Mapped[float] = mapped_column(Float, default=0.0)
    experience_match: Mapped[float] = mapped_column(Float, default=0.0)
    education_match: Mapped[float] = mapped_column(Float, default=0.0)
    gap_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    strengths: Mapped[Optional[list]] = mapped_column(JSON)
    gaps: Mapped[Optional[list]] = mapped_column(JSON)
    match_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    resume_doc_uid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resume_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "source_job_id", "resume_doc_uid", name="uq_job_match_user_source_resume"),
        Index("ix_job_matches_user_job", "user_id", "job_id"),
    )


class OpportunityNotification(Base):
    __tablename__ = "opportunity_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    send_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "channel", name="uq_opportunity_notifications_user_job_channel"),
        Index("ix_opportunity_notifications_user_job", "user_id", "job_id"),
    )


class OpportunityIntelligenceReport(Base):
    __tablename__ = "opportunity_intelligence_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_doc_uid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    skill_gap_score: Mapped[float] = mapped_column(Float, default=0.0)
    learning_effort_score: Mapped[float] = mapped_column(Float, default=0.0)
    application_urgency: Mapped[float] = mapped_column(Float, default=0.0)
    competition_risk: Mapped[float] = mapped_column(Float, default=0.0)
    domain_alignment: Mapped[float] = mapped_column(Float, default=0.0)
    career_growth_potential: Mapped[float] = mapped_column(Float, default=0.0)
    salary_potential: Mapped[float] = mapped_column(Float, default=0.0)
    remote_compatibility: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_rank_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    recommended_priority: Mapped[str] = mapped_column(String(32), default="DASHBOARD_ONLY", index=True)
    report: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "resume_doc_uid", name="uq_opp_intel_user_job_resume"),
        Index("ix_opp_intel_user_rank", "user_id", "opportunity_rank_score"),
    )


class SalaryIntelligence(Base):
    __tablename__ = "salary_intelligence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    salary_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(16), default="USD")
    salary_period: Mapped[str] = mapped_column(String(16), default="year")
    monthly_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monthly_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yearly_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yearly_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(64), default="description_extraction")
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InterviewPreparationPlan(Base):
    __tablename__ = "interview_preparation_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_doc_uid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    technical_questions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    hr_questions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    system_design_questions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    coding_topics: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    preparation_plan: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "resume_doc_uid", name="uq_interview_prep_user_job_resume"),
    )


class ApplicationTimelineEvent(Base):
    __tablename__ = "application_timeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="STATUS_CHANGE")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_application_timeline_user_job", "user_id", "job_id"),
    )


class CareerMemory(Base):
    __tablename__ = "career_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    source_table: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_career_memory_user_time", "user_id", "created_at"),
    )


class AlertDecisionAudit(Base):
    __tablename__ = "alert_decision_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="NONE")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    scores: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    decision_factors: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    decision_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class CommunicationRequest(Base):
    __tablename__ = "communication_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    opportunity_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    communication_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    communication_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    communication_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_factors: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    decision_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pipedream_request: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    pipedream_response: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    webhook_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_comm_requests_user_status", "user_id", "communication_status"),
        Index("ix_comm_requests_job_channel", "job_id", "channel"),
    )


class VoiceSession(Base):
    __tablename__ = "voice_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    communication_request_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("communication_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created", index=True)
    voice_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    voice_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VoiceConversation(Base):
    __tablename__ = "voice_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    voice_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("voice_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="agent")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intelligence_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class VoiceOutcome(Base):
    __tablename__ = "voice_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    voice_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("voice_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    call_sid: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OpportunityConversationContext(Base):
    __tablename__ = "opportunity_conversation_contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    context_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_context: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    context_sources: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    context_confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OpportunityOutcomeEvent(Base):
    __tablename__ = "opportunity_outcome_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    communication_request_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("communication_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    channel: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OpportunityOutcomeMetric(Base):
    __tablename__ = "opportunity_outcome_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    dimensions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OpportunityConversionMetric(Base):
    __tablename__ = "opportunity_conversion_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    notified_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    applied_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interview_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    offer_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OpportunityLifecycleRun(Base):
    __tablename__ = "opportunity_lifecycle_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed", index=True)
    monitored_counts: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    triggered_actions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    errors: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
