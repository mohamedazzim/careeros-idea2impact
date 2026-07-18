"""
Interview confidence engine — confidence calibration for interview evaluations.

Calibrates per-question, per-session, and per-domain confidence based on:
- Evidence grounding strength
- Contradiction pressure
- Answer consistency across questions
- Difficulty alignment

Phase 4D: Interactive interview confidence governance.
"""
import logging
from typing import Dict, Any, Optional

from src.observability.metrics import (
    INTERVIEW_RUBRIC_CONFIDENCE,
    CONTRADICTION_PENALTY,
)

logger = logging.getLogger(__name__)

DEFAULT_INTERVIEW_CONFIDENCE_BASE = 0.5
CONSISTENCY_WEIGHT = 0.3
DIFFICULTY_WEIGHT = 0.2
EVIDENCE_WEIGHT = 0.5


class InterviewConfidenceEngine:
    def calibrate(
        self,
        evaluation_outputs: Dict[str, Any],
        base_confidence: Optional[float] = None,
        contradictions: Optional[Dict[str, Any]] = None,
        answer_history: Optional[list] = None,
    ) -> Dict[str, Any]:
        base = base_confidence if base_confidence is not None else DEFAULT_INTERVIEW_CONFIDENCE_BASE

        evidence_score = self._compute_evidence_score(evaluation_outputs)
        consistency_score = self._compute_consistency_score(answer_history or [])
        difficulty_alignment = self._compute_difficulty_alignment(evaluation_outputs)

        weighted = (
            evidence_score * EVIDENCE_WEIGHT
            + consistency_score * CONSISTENCY_WEIGHT
            + difficulty_alignment * DIFFICULTY_WEIGHT
        )
        adjusted = base * 0.3 + weighted * 0.7

        con_penalty = 0.0
        if contradictions and contradictions.get("contradictions_detected"):
            severity = contradictions.get("severity", "none")
            sev_map = {"none": 0.0, "medium": 0.08, "high": 0.18, "critical": 0.30}
            con_penalty = sev_map.get(severity, 0.0)
            adjusted = max(0.05, adjusted - con_penalty)
            CONTRADICTION_PENALTY.observe(con_penalty)

        adjusted = round(adjusted, 4)
        INTERVIEW_RUBRIC_CONFIDENCE.labels(rubric_type="overall").observe(adjusted)

        return {
            "overall": adjusted,
            "base_confidence": round(base, 4),
            "evidence_score": round(evidence_score, 4),
            "consistency_score": round(consistency_score, 4),
            "difficulty_alignment": round(difficulty_alignment, 4),
            "contradiction_penalty": round(con_penalty, 4),
            "per_question": evaluation_outputs.get("per_question_confidence", {}),
        }

    def _compute_evidence_score(self, outputs: Dict[str, Any]) -> float:
        citations = outputs.get("citations", [])
        claims = outputs.get("claims", [])
        if not claims:
            return 0.3
        cited = sum(1 for c in claims if c.get("evidence_citations"))
        return min(1.0, cited / max(len(claims), 1))

    def _compute_consistency_score(self, answer_history: list) -> float:
        if len(answer_history) < 2:
            return 0.7
        scores = [a.get("confidence", 0.5) for a in answer_history if isinstance(a, dict)]
        if len(scores) < 2:
            return 0.7
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        return max(0.1, 1.0 - variance)

    def _compute_difficulty_alignment(self, outputs: Dict[str, Any]) -> float:
        difficulty = outputs.get("difficulty_level", "intermediate")
        level_map = {"beginner": 0.2, "intermediate": 0.4, "advanced": 0.6, "senior": 0.8, "staff": 1.0}
        score = outputs.get("score", 50)
        norm_score = score / 100.0
        expected = level_map.get(difficulty, 0.5)
        return 1.0 - abs(norm_score - expected)


_svc: InterviewConfidenceEngine | None = None


def get_interview_confidence_engine() -> InterviewConfidenceEngine:
    global _svc
    if _svc is None:
        _svc = InterviewConfidenceEngine()
    return _svc


def reset_interview_confidence_engine() -> None:
    global _svc
    _svc = None


def __getattr__(name: str):
    if name == "interview_confidence_engine":
        return get_interview_confidence_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
