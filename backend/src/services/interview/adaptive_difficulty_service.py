"""
Adaptive difficulty service — real-time interview difficulty adaptation.

Adapts question difficulty based on:
- Prior answer quality (rubric scores)
- Confidence signals from AI readiness analysis
- ATS intelligence context
- Architecture maturity signals
- Contradiction pressure from prior answers
- Recruiter-review signals

Phase 4D: Adaptive interview intelligence.
"""
import logging
from typing import Dict, Any, List, Optional

from src.services.interview.interview_observability import get_interview_observability

logger = logging.getLogger(__name__)

DIFFICULTY_LEVELS = ["beginner", "intermediate", "advanced", "senior", "staff"]
LEVEL_INDICES = {lvl: i for i, lvl in enumerate(DIFFICULTY_LEVELS)}


class AdaptiveDifficultyService:
    def __init__(self):
        self.default_level = "intermediate"
        self.escalation_threshold = 75
        self.demotion_threshold = 40
        self.consecutive_threshold = 2

    def compute_initial_level(
        self,
        ats_data: Optional[Dict[str, Any]] = None,
        ai_readiness: Optional[Dict[str, Any]] = None,
        architecture_maturity: Optional[Dict[str, Any]] = None,
        strategy_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        signals = []

        if ats_data:
            overall = ats_data.get("overall_score", 50) if isinstance(ats_data, dict) else 50
            if overall >= 85:
                signals.append("staff")
            elif overall >= 70:
                signals.append("senior")
            elif overall >= 55:
                signals.append("advanced")
            elif overall >= 40:
                signals.append("intermediate")
            else:
                signals.append("beginner")

        if ai_readiness:
            score = self._extract_score(ai_readiness)
            if score >= 80:
                signals.append("senior")
            elif score >= 60:
                signals.append("advanced")
            elif score >= 40:
                signals.append("intermediate")
            else:
                signals.append("beginner")

        if architecture_maturity:
            score = self._extract_score(architecture_maturity)
            if score >= 75:
                signals.append("senior")
            elif score >= 50:
                signals.append("advanced")
            elif score >= 30:
                signals.append("intermediate")
            else:
                signals.append("beginner")

        if not signals:
            return self.default_level

        indices = [LEVEL_INDICES.get(s, 2) for s in signals]
        avg_idx = round(sum(indices) / len(indices))
        return DIFFICULTY_LEVELS[min(avg_idx, len(DIFFICULTY_LEVELS) - 1)]

    def adapt(
        self,
        current_level: str,
        question_history: List[Dict[str, Any]],
        ats_data: Optional[Dict[str, Any]] = None,
        ai_readiness: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        obs = get_interview_observability()
        curr_idx = LEVEL_INDICES.get(current_level, 2)

        if not question_history:
            return {"level": current_level, "changed": False, "reason": "no_history"}

        recent = question_history[-self.consecutive_threshold:]
        scores = [q.get("score", 50) for q in recent if isinstance(q, dict) and "score" in q]

        if len(scores) >= self.consecutive_threshold:
            avg_score = sum(scores) / len(scores)
            if avg_score >= self.escalation_threshold and curr_idx < len(DIFFICULTY_LEVELS) - 1:
                new_level = DIFFICULTY_LEVELS[curr_idx + 1]
                obs.record_adaptive_transition(current_level, new_level, "high_performance")
                return {"level": new_level, "changed": True, "reason": "high_performance", "avg_recent_score": round(avg_score, 1)}
            elif avg_score <= self.demotion_threshold and curr_idx > 0:
                new_level = DIFFICULTY_LEVELS[curr_idx - 1]
                obs.record_adaptive_transition(current_level, new_level, "low_performance")
                return {"level": new_level, "changed": True, "reason": "low_performance", "avg_recent_score": round(avg_score, 1)}

        # Contradiction-driven escalation
        contradictions = sum(1 for q in question_history if q.get("contradiction_detected"))
        if contradictions >= 2:
            new_level = DIFFICULTY_LEVELS[min(curr_idx + 1, len(DIFFICULTY_LEVELS) - 1)]
            if new_level != current_level:
                obs.record_adaptive_transition(current_level, new_level, "contradiction_pressure")
                return {"level": new_level, "changed": True, "reason": "contradiction_pressure", "contradictions_detected": contradictions}

        return {"level": current_level, "changed": False, "reason": "stable"}

    def _extract_score(self, data: Any) -> float:
        if hasattr(data, "metadata") and hasattr(data.metadata, "confidence_overall"):
            return data.metadata.confidence_overall * 100
        if isinstance(data, dict):
            return data.get("overall_score", data.get("score", 50))
        return 50


_svc: AdaptiveDifficultyService | None = None


def get_adaptive_difficulty_service() -> AdaptiveDifficultyService:
    global _svc
    if _svc is None:
        _svc = AdaptiveDifficultyService()
    return _svc


def __getattr__(name: str):
    if name == "adaptive_difficulty_service":
        return get_adaptive_difficulty_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
