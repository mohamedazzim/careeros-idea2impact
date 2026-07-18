"""
Real-time feedback service — live interview critique with evidence grounding.

Analyzes answer depth, technical correctness, architecture maturity,
communication clarity, tradeoff awareness, production realism,
contradiction pressure, and confidence consistency.

Every critique must cite evidence. Generates immediate feedback with
strengths, weaknesses, improvement suggestions, confidence scores,
citations, and evidence mapping.

Phase 4D: Real-time interview critique intelligence.
"""
import json
import logging
from typing import Dict, Any, List

from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)

FEEDBACK_DIMENSIONS = [
    "answer_depth", "technical_correctness", "architecture_maturity",
    "communication_clarity", "tradeoff_awareness", "production_realism",
    "contradiction_pressure", "confidence_consistency",
]


class RealtimeFeedbackService:
    async def critique(
        self,
        question: str,
        answer: str,
        interview_type: str,
        difficulty: str,
        rubric_context: str = "",
        candidate_context: str = "",
        prior_contr: str = "",
    ) -> StructuredResponse:
        return await get_reasoning_pipeline().reason(
            query=f"critique {interview_type} answer {difficulty}",
            category="interview",
            prompt_id="interview_critique",
            template_vars={
                "question": question,
                "answer": answer,
                "interview_type": interview_type,
                "difficulty": difficulty,
                "rubric_context": rubric_context,
                "candidate_context": candidate_context,
                "prior_contradictions": prior_contr,
            },
        )

    async def generate_feedback_summary(
        self,
        session_questions: List[Dict[str, Any]],
        interview_type: str,
        context: str = "",
    ) -> StructuredResponse:
        return await get_reasoning_pipeline().reason(
            query=f"feedback summary {interview_type}",
            category="interview",
            prompt_id="feedback_summary",
            template_vars={
                "session_questions": json.dumps(session_questions, default=str),
                "interview_type": interview_type,
                "context": context,
            },
        )


_svc: RealtimeFeedbackService | None = None
def get_realtime_feedback_service() -> RealtimeFeedbackService:
    global _svc
    if _svc is None: _svc = RealtimeFeedbackService()
    return _svc
def __getattr__(n):
    if n == "realtime_feedback_service": return get_realtime_feedback_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
