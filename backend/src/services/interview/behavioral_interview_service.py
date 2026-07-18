"""
Behavioral interview service — STAR-method behavioral question intelligence.

Generates evidence-grounded behavioral questions leveraging:
- Recruiter-review signals for weakness alignment
- Strategy intelligence for career-stage calibration
- Contradiction analysis for pressure questions
- ATS intelligence for work-history context

Phase 4D: Behavioral interview intelligence.
"""
import json
import logging
from typing import Dict, Any, List

from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)

BEHAVIORAL_CATEGORIES = [
    "leadership", "conflict_resolution", "collaboration",
    "failure_response", "growth_mindset", "stakeholder_management",
    "initiative", "ambiguity_navigation", "feedback_response",
    "prioritization",
]


class BehavioralInterviewService:
    async def generate_question(
        self,
        resume_text: str = "",
        difficulty: str = "intermediate",
        category: str = "leadership",
        recruiter_signals: str = "",
        question_history: List[Dict[str, Any]] = None,
        context: str = "",
    ) -> StructuredResponse:
        from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
        return await get_reasoning_pipeline().reason(
            query=f"behavioral interview question {category} {difficulty}",
            category="interview",
            prompt_id="behavioral_interview",
            template_vars={
                "resume_text": resume_text,
                "difficulty": difficulty,
                "category_focus": category,
                "recruiter_signals": recruiter_signals,
                "question_history": json.dumps(question_history or [], default=str),
                "context": context,
            },
        )

    async def evaluate_response(
        self,
        question: str,
        answer: str,
        difficulty: str,
        category: str,
        rubric_context: str = "",
        candidate_context: str = "",
    ) -> StructuredResponse:
        from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
        return await get_reasoning_pipeline().reason(
            query=f"evaluate behavioral response {category} {difficulty}",
            category="interview",
            prompt_id="behavioral_evaluation",
            template_vars={
                "question": question,
                "answer": answer,
                "difficulty": difficulty,
                "category_focus": category,
                "rubric_context": rubric_context,
                "candidate_context": candidate_context,
            },
        )


_svc: BehavioralInterviewService | None = None
def get_behavioral_interview_service() -> BehavioralInterviewService:
    global _svc
    if _svc is None: _svc = BehavioralInterviewService()
    return _svc
def __getattr__(n):
    if n == "behavioral_interview_service": return get_behavioral_interview_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
