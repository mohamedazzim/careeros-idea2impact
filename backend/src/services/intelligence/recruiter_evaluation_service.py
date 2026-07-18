"""
Recruiter evaluation service — enterprise recruiter-grade candidate review.

Produces recruiter-style evaluation with strengths, concerns,
hiring/risk signals, interview recommendations, and evidence citations.
"""
import logging
from typing import Dict, Any, Optional

from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)


class RecruiterEvaluationService:
    async def evaluate(
        self,
        resume_text: str,
        job_text: str,
        ats_summary: Optional[Dict[str, Any]] = None,
    ) -> StructuredResponse:
        from src.services.retrieval.hybrid_retrieval_service import get_hybrid_retrieval_service
        hybrid = get_hybrid_retrieval_service()
        retrieval = await hybrid.retrieve(
            query=f"recruiter review {resume_text[:200]}",
            top_k=15, top_n=8, use_hybrid=True,
        )
        pipeline = get_reasoning_pipeline()
        return await pipeline.reason(
            query=f"recruiter review for {resume_text[:100]}",
            category="recruiter",
            prompt_id="recruiter_review",
            template_vars={
                "resume_text": resume_text,
                "job_text": job_text,
                "ats_score_summary": str(ats_summary or {}),
                "context": retrieval.context,
            },
        )


_svc: Optional[RecruiterEvaluationService] = None
def get_recruiter_evaluation_service() -> RecruiterEvaluationService:
    global _svc
    if _svc is None: _svc = RecruiterEvaluationService()
    return _svc
def __getattr__(name: str):
    if name == "recruiter_evaluation_service": return get_recruiter_evaluation_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
