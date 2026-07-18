"""
Interview persistence models — PostgreSQL-backed interview session history.

Phase 4D Hardening: Production-safe persistence with session recovery,
question-level evaluation storage, and longitudinal weakness tracking.

Tables:
- interview_sessions: Active and completed interview sessions
- interview_questions: Per-question records with evaluations
- interview_weakness_history: Longitudinal weakness tracking across sessions

Stateless ORM models, async-safe.
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, ForeignKey, Text
from sqlalchemy.sql import func
from .base import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_uid = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(String(256), index=True, nullable=True)
    interview_type = Column(String(32), nullable=False)
    status = Column(String(32), default="active", index=True, nullable=False)
    difficulty_level = Column(String(16), default="intermediate", nullable=False)
    current_question_index = Column(Integer, default=0, nullable=False)
    total_score = Column(Float, default=0.0, nullable=False)
    adaptation_history = Column(JSON, default=list, nullable=False)
    confidence_progression = Column(JSON, default=list, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict, nullable=False)
    created_by = Column(String(128), nullable=True)
    updated_by = Column(String(128), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    question_index = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, default="", nullable=False)
    difficulty_level = Column(String(16), default="intermediate", nullable=False)
    score = Column(Float, default=0.0, nullable=False)
    confidence = Column(Float, default=0.5, nullable=False)
    rubric_scores = Column(JSON, default=dict, nullable=False)
    contradictions_detected = Column(Integer, default=0, nullable=False)
    strengths = Column(JSON, default=list, nullable=False)
    weaknesses = Column(JSON, default=list, nullable=False)
    improvement_suggestions = Column(JSON, default=list, nullable=False)
    critique = Column(JSON, default=dict, nullable=False)
    citations = Column(JSON, default=list, nullable=False)
    governance_flags = Column(JSON, default=dict, nullable=False)
    trace = Column(JSON, default=dict, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InterviewWeaknessHistory(Base):
    __tablename__ = "interview_weakness_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(256), index=True, nullable=True)
    weakness_type = Column(String(128), index=True, nullable=False)
    session_uid = Column(String(64), nullable=False)
    occurrences = Column(Integer, default=0, nullable=False)
    severity = Column(String(16), default="low", nullable=False)
    pattern_classification = Column(String(64), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
