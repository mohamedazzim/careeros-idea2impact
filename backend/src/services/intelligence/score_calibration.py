"""
Score calibration: ensures ATS scores are calibrated and within realistic ranges.

Prevents inflated/deflated scores, normalizes across categories,
and validates score distributions.

Stateless, async-safe, observable.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Score boundaries per category (min/max realistic scores)
CALIBRATION_BOUNDS: Dict[str, tuple] = {
    "skill_alignment": (10, 100),
    "semantic_relevance": (5, 100),
    "keyword_relevance": (5, 100),
    "experience_relevance": (5, 100),
    "role_alignment": (5, 100),
    "chronology_quality": (5, 95),
    "achievement_quality": (5, 100),
    "leadership_indicators": (0, 100),
    "architecture_design": (0, 100),
    "production_engineering": (0, 100),
    "ai_ml_stack": (0, 100),
    "resume_completeness": (10, 100),
    "technical_depth": (5, 100),
    "enterprise_readiness": (0, 100),
}


class ScoreCalibration:
    """Validates and calibrates ATS category scores."""

    def calibrate(self, category_scores: Dict[str, Any]) -> Dict[str, Any]:
        """Clamp scores to realistic ranges and rescale if needed."""
        calibrated = {}
        for cat, score in category_scores.items():
            if not isinstance(score, (int, float)):
                calibrated[cat] = score
                continue
            bounds = CALIBRATION_BOUNDS.get(cat, (0, 100))
            clamped = max(bounds[0], min(bounds[1], score))
            calibrated[cat] = round(clamped, 1)
        return calibrated

    def compute_overall(self, calibrated: Dict[str, float]) -> float:
        """Weighted overall ATS score from calibrated categories."""
        numeric = {k: v for k, v in calibrated.items() if isinstance(v, (int, float))}
        if not numeric:
            return 0.0
        return round(sum(numeric.values()) / len(numeric), 1)

    def validate_distribution(self, scores: Dict[str, float]) -> Dict[str, Any]:
        """Check if score distribution is realistic (not all 0s or all 100s)."""
        numeric = [v for v in scores.values() if isinstance(v, (int, float))]
        if not numeric:
            return {"valid": False, "reason": "no numeric scores"}
        avg = sum(numeric) / len(numeric)
        if avg < 5:
            return {"valid": False, "reason": f"average too low ({avg:.1f})"}
        if avg > 95:
            return {"valid": False, "reason": f"average too high ({avg:.1f})"}
        return {"valid": True, "average": round(avg, 1), "count": len(numeric)}


_calibration: Optional[ScoreCalibration] = None


def get_score_calibration() -> ScoreCalibration:
    global _calibration
    if _calibration is None:
        _calibration = ScoreCalibration()
    return _calibration


def reset_score_calibration() -> None:
    global _calibration
    _calibration = None


def __getattr__(name: str):
    if name == "score_calibration":
        return get_score_calibration()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
