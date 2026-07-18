"""
Interview observability — centralized metrics for adaptive interview intelligence.

Phase 4D: Tracks interview latency, adaptive transitions, difficulty escalations,
hallucination detections, critique suppression, contradiction pressure, rubric
confidence, concurrency pressure, and session token pressure.

Stateless, async-safe.
"""
import logging

from src.observability.metrics import (
    INTERVIEW_LATENCY,
    INTERVIEW_ADAPTIVE_TRANSITIONS,
    INTERVIEW_DIFFICULTY_ESCALATION,
    INTERVIEW_HALLUCINATION,
    INTERVIEW_CRITIQUE_SUPPRESSION,
    INTERVIEW_CONTRADICTION_PRESSURE,
    INTERVIEW_RUBRIC_CONFIDENCE,
    INTERVIEW_CONCURRENCY_PRESSURE,
    INTERVIEW_SESSION_TOKEN_PRESSURE,
    INTERVIEW_WEAKNESS_PATTERN,
    DOMAIN_CALL_TOTAL,
)

logger = logging.getLogger(__name__)


class InterviewObservability:
    def record_interview_call(self, interview_type: str, status: str, latency_ms: float) -> None:
        INTERVIEW_LATENCY.labels(interview_type=interview_type, status=status).observe(latency_ms / 1000)
        DOMAIN_CALL_TOTAL.labels(domain="interview", status=status).inc()

    def record_adaptive_transition(
        self, from_level: str, to_level: str, reason: str
    ) -> None:
        INTERVIEW_ADAPTIVE_TRANSITIONS.labels(
            from_level=from_level, to_level=to_level, reason=reason
        ).inc()

    def record_difficulty_escalation(self, interview_type: str, level: str) -> None:
        INTERVIEW_DIFFICULTY_ESCALATION.labels(
            interview_type=interview_type, level=level
        ).inc()

    def record_hallucination(self, interview_type: str, severity: str) -> None:
        INTERVIEW_HALLUCINATION.labels(
            interview_type=interview_type, severity=severity
        ).inc()

    def record_critique_suppression(self, reason: str) -> None:
        INTERVIEW_CRITIQUE_SUPPRESSION.labels(reason=reason).inc()

    def record_contradiction_pressure(self, interview_type: str, severity: str) -> None:
        INTERVIEW_CONTRADICTION_PRESSURE.labels(
            interview_type=interview_type, severity=severity
        ).inc()

    def record_rubric_confidence(self, rubric_type: str, score: float) -> None:
        INTERVIEW_RUBRIC_CONFIDENCE.labels(rubric_type=rubric_type).observe(score)

    def record_concurrency_pressure(self, active_sessions: int) -> None:
        INTERVIEW_CONCURRENCY_PRESSURE.observe(active_sessions)

    def record_session_token_pressure(self, session_id: str, tokens: int) -> None:
        INTERVIEW_SESSION_TOKEN_PRESSURE.labels(session_id=session_id[:8]).observe(tokens)

    def record_weakness_pattern(self, pattern_type: str, count: int) -> None:
        INTERVIEW_WEAKNESS_PATTERN.labels(pattern_type=pattern_type).observe(count)


_svc: InterviewObservability | None = None


def get_interview_observability() -> InterviewObservability:
    global _svc
    if _svc is None:
        _svc = InterviewObservability()
    return _svc


def reset_interview_observability() -> None:
    global _svc
    _svc = None


def __getattr__(name: str):
    if name == "interview_observability":
        return get_interview_observability()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
