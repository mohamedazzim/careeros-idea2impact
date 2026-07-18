"""Phase 5 — Agentic Orchestration Models.

Seven tables: OrchestrationSession, OrchestrationEvent, AutonomousAction,
NotificationHistory, OpportunityScore, GovernanceDecision, MCPExecutionLog.

All models use Async SQLAlchemy with JSONB for structured payloads.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
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


# ── Orchestration Session ─────────────────────────────────────────────

class OrchestrationSession(Base):
    """An end-to-end orchestration run (one LangGraph execution)."""

    __tablename__ = "orchestration_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    graph_name: Mapped[str] = mapped_column(
        String(128), nullable=False, default="opportunity_graph"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
    current_node: Mapped[Optional[str]] = mapped_column(String(128))
    completion_pct: Mapped[float] = mapped_column(Float, default=0.0)
    errors: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata", JSON, nullable=True
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    events: Mapped[List["OrchestrationEvent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_orch_sessions_user_status", "user_id", "status"),
    )


# ── Orchestration Event ───────────────────────────────────────────────

class OrchestrationEvent(Base):
    """One event emitted during an orchestration run."""

    __tablename__ = "orchestration_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orchestration_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    node_name: Mapped[Optional[str]] = mapped_column(String(128))
    agent_name: Mapped[Optional[str]] = mapped_column(String(128))
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    session: Mapped["OrchestrationSession"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_orch_events_session_type", "session_id", "event_type"),
    )


# ── Autonomous Action ─────────────────────────────────────────────────

class AutonomousAction(Base):
    """An action the orchestration decided to take autonomously."""

    __tablename__ = "autonomous_actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    action_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("orchestration_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning_chain: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    evidence_chain: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    governance_verdict: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    suppressed: Mapped[bool] = mapped_column(default=False)
    suppression_reason: Mapped[Optional[str]] = mapped_column(String(256))
    mcp_tool_used: Mapped[Optional[str]] = mapped_column(String(128))
    mcp_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    trace_id: Mapped[Optional[str]] = mapped_column(String(128))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        Index("ix_autonomous_actions_session_status", "session_id", "status"),
        Index("ix_autonomous_actions_user_type", "user_id", "action_type"),
    )


# ── Notification History ──────────────────────────────────────────────

class NotificationHistory(Base):
    """History of all notifications (voice, email, SMS, push)."""

    __tablename__ = "notification_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    notification_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    opportunity_id: Mapped[Optional[str]] = mapped_column(
        String(128), index=True
    )
    channel: Mapped[str] = mapped_column(
        String(32), nullable=False, default="voice", index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", index=True
    )
    voice_script: Mapped[Optional[str]] = mapped_column(Text)
    elevenlabs_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    twilio_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    call_sid: Mapped[Optional[str]] = mapped_column(String(128))
    call_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    urgency_score: Mapped[Optional[float]] = mapped_column(Float)
    suppressed: Mapped[bool] = mapped_column(default=False)
    suppression_reason: Mapped[Optional[str]] = mapped_column(String(256))
    trace_id: Mapped[Optional[str]] = mapped_column(String(128))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        Index("ix_notification_history_opp_status", "opportunity_id", "status"),
    )


# ── Opportunity Score ─────────────────────────────────────────────────

class OpportunityScore(Base):
    """Multi-dimensional opportunity fit score."""

    __tablename__ = "opportunity_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    session_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("orchestration_sessions.id", ondelete="SET NULL"),
        nullable=True
    )
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    dimension_scores: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    dimension_weights: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    evidence_citations: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    reasoning: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    priority_rank: Mapped[Optional[int]] = mapped_column(Integer)
    urgency_score: Mapped[Optional[float]] = mapped_column(Float)
    generated_by: Mapped[Optional[str]] = mapped_column(String(64))
    trace_id: Mapped[Optional[str]] = mapped_column(String(128))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        UniqueConstraint("opportunity_id", "user_id", "session_id"),
        Index("ix_opportunity_scores_user_rank", "user_id", "priority_rank"),
    )


# ── Governance Decision ───────────────────────────────────────────────

class GovernanceDecision(Base):
    """A governance decision made during orchestration."""

    __tablename__ = "governance_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("orchestration_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    action_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("autonomous_actions.id", ondelete="SET NULL"),
        nullable=True
    )
    decision_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    verdict: Mapped[str] = mapped_column(
        String(32), nullable=False, default="passed", index=True
    )
    rule_violated: Mapped[Optional[str]] = mapped_column(String(256))
    confidence_before: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_after: Mapped[float] = mapped_column(Float, default=0.0)
    penalty_applied: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        Index("ix_governance_decisions_session_verdict", "session_id", "verdict"),
    )


# ── MCP Execution Log ─────────────────────────────────────────────────

class MCPExecutionLog(Base):
    """Log of every MCP tool invocation."""

    __tablename__ = "mcp_execution_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    execution_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("orchestration_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    action_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("autonomous_actions.id", ondelete="SET NULL"),
        nullable=True
    )
    tool_name: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    server_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="unknown"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    request_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    response_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    duration_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    trace_id: Mapped[Optional[str]] = mapped_column(String(128))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        Index("ix_mcp_execution_logs_session_tool", "session_id", "tool_name"),
        Index("ix_mcp_execution_logs_status", "status", "created_at"),
    )
