"""
Coding interview service — adaptive coding interview intelligence.

Generates algorithmic and applied coding questions tailored to candidate
skill level based on ATS + AI readiness signals. Evaluates code quality,
edge case handling, testing approach, and optimization reasoning.

Phase 4D: Coding interview intelligence.
"""
import json
import logging
from typing import Dict, Any, List

from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)

CODING_DOMAINS = [
    "algorithms", "data_structures", "system_programming",
    "web_backend", "frontend_components", "database_queries",
    "api_design", "concurrency", "testing_design",
]


class CodingInterviewService:
    async def generate_question(
        self,
        resume_text: str = "",
        difficulty: str = "intermediate",
        domain: str = "algorithms",
        question_history: List[Dict[str, Any]] = None,
        context: str = "",
    ) -> StructuredResponse:
        return await get_reasoning_pipeline().reason(
            query=f"coding interview question {domain} {difficulty}",
            category="interview",
            prompt_id="coding_interview",
            template_vars={
                "resume_text": resume_text,
                "difficulty": difficulty,
                "domain_focus": domain,
                "question_history": json.dumps(question_history or [], default=str),
                "context": context,
            },
        )

    async def evaluate_solution(
        self,
        question: str,
        solution: str,
        difficulty: str,
        domain: str,
        rubric_context: str = "",
        candidate_context: str = "",
    ) -> StructuredResponse:
        from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
        return await get_reasoning_pipeline().reason(
            query=f"evaluate coding solution {domain} {difficulty}",
            category="interview",
            prompt_id="coding_evaluation",
            template_vars={
                "question": question,
                "solution": solution,
                "difficulty": difficulty,
                "domain_focus": domain,
                "rubric_context": rubric_context,
                "candidate_context": candidate_context,
            },
        )


_svc: CodingInterviewService | None = None
def get_coding_interview_service() -> CodingInterviewService:
    global _svc
    if _svc is None: _svc = CodingInterviewService()
    return _svc
def __getattr__(n):
    if n == "coding_interview_service": return get_coding_interview_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
