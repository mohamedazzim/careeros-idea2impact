"""
Interview safety service — runtime safety caps and degradation enforcement.

Implements:
- Session caps (max active sessions)
- Question caps (max per session)
- Adaptive escalation caps
- Token exhaustion mitigation
- Forced graceful degradation

Phase 4D Hardening: Runtime safety enforcement.
"""
import logging
from typing import Dict, Any

from src.core.config import settings
from src.observability.metrics import (
    INTERVIEW_CONCURRENCY_PRESSURE,
    INTERVIEW_DIFFICULTY_ESCALATION,
)

logger = logging.getLogger(__name__)


class InterviewSafetyService:
    def __init__(self):
        self.session_cap = settings.INTERVIEW_SESSION_MAX
        self.question_cap = settings.INTERVIEW_QUESTIONS_MAX
        self.escalation_cap = settings.INTERVIEW_ESCALATION_CAP
        self.token_budget = settings.INTERVIEW_TOKEN_BUDGET

    async def check_session_cap(self, active_count: int) -> Dict[str, Any]:
        utilization = active_count / max(self.session_cap, 1)
        INTERVIEW_CONCURRENCY_PRESSURE.observe(active_count)
        if active_count >= self.session_cap:
            return {
                "allowed": False,
                "reason": f"session_cap_reached: {active_count}/{self.session_cap}",
                "degraded": True,
            }
        if utilization >= 0.8:
            return {
                "allowed": True,
                "warning": "high_session_pressure",
                "utilization": round(utilization, 2),
                "degraded": True if utilization >= 0.95 else False,
            }
        return {"allowed": True, "utilization": round(utilization, 2)}

    def check_question_cap(self, current_count: int) -> Dict[str, Any]:
        if current_count >= self.question_cap:
            return {
                "allowed": False,
                "reason": f"question_cap_reached: {current_count}/{self.question_cap}",
            }
        if current_count >= self.question_cap * 0.9:
            return {
                "allowed": True,
                "warning": "nearing_question_cap",
                "remaining": self.question_cap - current_count,
            }
        return {"allowed": True, "remaining": self.question_cap - current_count}

    def check_escalation_cap(self, adaptation_history: list) -> Dict[str, Any]:
        escalations = sum(
            1 for a in adaptation_history
            if isinstance(a, dict) and a.get("to") != a.get("from")
        )
        INTERVIEW_DIFFICULTY_ESCALATION.labels(
            interview_type="any", level=f"escalations_{escalations}"
        ).inc()
        if escalations >= self.escalation_cap:
            return {
                "allowed": False,
                "reason": f"escalation_cap_reached: {escalations}/{self.escalation_cap}",
            }
        return {"allowed": True, "escalations_used": escalations, "escalations_max": self.escalation_cap}

    def check_token_budget(self, used: int) -> Dict[str, Any]:
        utilization = used / max(self.token_budget, 1)
        if utilization >= 1.0:
            return {
                "allowed": False,
                "reason": "token_budget_exhausted",
                "degraded": True,
            }
        if utilization >= 0.90:
            return {
                "allowed": True,
                "degraded": True,
                "severity": "critical",
                "utilization": round(utilization, 2),
            }
        if utilization >= 0.75:
            return {
                "allowed": True,
                "degraded": True,
                "severity": "high",
                "utilization": round(utilization, 2),
            }
        return {"allowed": True, "utilization": round(utilization, 2)}

    def forced_degradation_mode(self, utilization: float) -> Dict[str, Any]:
        if utilization >= 0.90:
            return {
                "mode": "critical",
                "max_questions": max(1, self.question_cap // 5),
                "skip_feedback": True,
                "skip_critique": True,
                "minimal_traces": True,
            }
        if utilization >= 0.75:
            return {
                "mode": "reduced",
                "max_questions": self.question_cap // 2,
                "skip_feedback": False,
                "skip_critique": False,
                "minimal_traces": False,
            }
        return {"mode": "normal"}


_svc: InterviewSafetyService | None = None
def get_interview_safety_service() -> InterviewSafetyService:
    global _svc
    if _svc is None: _svc = InterviewSafetyService()
    return _svc
def reset_interview_safety_service() -> None:
    global _svc; _svc = None
def __getattr__(name: str):
    if name == "interview_safety_service": return get_interview_safety_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
