"""
Interview evaluation service — explainable multi-rubric scoring engine.

Computes weighted rubric scores across all interview types, generates
explainable evaluation reports with evidence citations, and aligns with
the confidence engine for reliable scoring.

Phase 4D: Explainable interview evaluation.
"""
import logging
from typing import Dict, Any, List, Optional

from src.services.interview.interview_rubric_service import (
    get_interview_rubric_service,
)
from src.services.interview.interview_confidence_engine import get_interview_confidence_engine
from src.services.interview.interview_observability import get_interview_observability

logger = logging.getLogger(__name__)


class InterviewEvaluationService:
    async def evaluate(
        self,
        interview_type: str,
        question: str,
        answer: str,
        difficulty: str,
        claude_evaluation: Dict[str, Any],
        answer_history: List[Dict[str, Any]] = None,
        contradictions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        rubric_svc = get_interview_rubric_service()
        obs = get_interview_observability()

        rubric_map = {
            "technical": rubric_svc.get_technical_rubric,
            "coding": rubric_svc.get_coding_rubric,
            "system_design": rubric_svc.get_system_design_rubric,
            "ai_engineering": rubric_svc.get_ai_engineering_rubric,
            "behavioral": rubric_svc.get_behavioral_rubric,
        }

        getter = rubric_map.get(interview_type, rubric_svc.get_technical_rubric)
        rubrics = getter()

        dimension_scores: Dict[str, float] = {}
        dimension_details: Dict[str, Any] = {}
        for dim in rubrics:
            result = rubric_svc.score_dimension(dim, claude_evaluation)
            dimension_scores[dim.name] = result["score"]
            dimension_details[dim.name] = result

        weighted = rubric_svc.compute_weighted_score(rubrics, dimension_scores)

        confidence_engine = get_interview_confidence_engine()
        confidence = confidence_engine.calibrate(
            evaluation_outputs={
                "score": weighted["overall_score"],
                "difficulty_level": difficulty,
                "per_question_confidence": {question[:30]: weighted["overall_score"] / 100},
                "citations": claude_evaluation.get("citations", []),
                "claims": claude_evaluation.get("claims", []),
            },
            base_confidence=claude_evaluation.get("confidence", 0.5),
            contradictions=contradictions,
            answer_history=answer_history,
        )

        obs.record_rubric_confidence(interview_type, weighted["overall_score"] / 100)

        return {
            "overall_score": weighted["overall_score"],
            "dimension_scores": dimension_details,
            "weighted_breakdown": weighted["per_dimension"],
            "confidence": confidence,
            "difficulty": difficulty,
            "interview_type": interview_type,
            "question": question,
            "answer_summary": answer[:200],
            "strengths": claude_evaluation.get("strengths", []),
            "weaknesses": claude_evaluation.get("weaknesses", []),
            "improvement_suggestions": claude_evaluation.get("improvements", []),
            "citations": claude_evaluation.get("citations", []),
            "evidence_sufficient": all(
                d["evidence_sufficient"] for d in dimension_details.values()
            ),
        }


_svc: InterviewEvaluationService | None = None
def get_interview_evaluation_service() -> InterviewEvaluationService:
    global _svc
    if _svc is None: _svc = InterviewEvaluationService()
    return _svc
def __getattr__(n):
    if n == "interview_evaluation_service": return get_interview_evaluation_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
