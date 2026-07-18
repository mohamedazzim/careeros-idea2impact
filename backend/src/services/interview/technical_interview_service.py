"""
Technical interview service — adaptive technical questioning engine.

Generates grounded technical questions across 10 engineering domains:
backend, frontend, cloud, DevOps, AI, distributed systems, architecture,
databases, observability, orchestration.

Each question is retrieval-grounded against candidate evidence.
Phase 4D: Adaptive technical interview intelligence.
"""
import json
import logging
from typing import Dict, Any, List

from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)

TECHNICAL_DOMAINS = [
    "backend_engineering", "frontend_engineering", "cloud_engineering",
    "devops", "ai_engineering", "distributed_systems", "system_architecture",
    "database_engineering", "observability", "orchestration",
]


class TechnicalInterviewService:
    async def generate_question(
        self,
        resume_text: str = "",
        difficulty: str = "intermediate",
        domain: str = "backend_engineering",
        question_history: List[Dict[str, Any]] = None,
        context: str = "",
    ) -> StructuredResponse:
        from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
        return await get_reasoning_pipeline().reason(
            query=f"technical interview question {domain} {difficulty}",
            category="interview",
            prompt_id="technical_interview",
            template_vars={
                "resume_text": resume_text,
                "difficulty": difficulty,
                "domain_focus": domain,
                "question_history": json.dumps(question_history or [], default=str),
                "context": context,
            },
        )

    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        difficulty: str,
        domain: str,
        rubric_context: str = "",
        candidate_context: str = "",
    ) -> StructuredResponse:
        from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
        return await get_reasoning_pipeline().reason(
            query=f"evaluate technical answer {domain} {difficulty}",
            category="interview",
            prompt_id="technical_evaluation",
            template_vars={
                "question": question,
                "answer": answer,
                "difficulty": difficulty,
                "domain_focus": domain,
                "rubric_context": rubric_context,
                "candidate_context": candidate_context,
            },
        )


_svc: TechnicalInterviewService | None = None
def get_technical_interview_service() -> TechnicalInterviewService:
    global _svc
    if _svc is None: _svc = TechnicalInterviewService()
    return _svc
def __getattr__(n):
    if n == "technical_interview_service": return get_technical_interview_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
