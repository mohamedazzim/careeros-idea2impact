"""
Semantic job-fit analysis — enterprise semantic matching intelligence.

Analyzes 10 dimensions of semantic job fit beyond keyword matching.
"""
import logging
from typing import Optional

from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)


class SemanticFitService:
    async def analyze(
        self,
        resume_text: str,
        job_text: str,
    ) -> StructuredResponse:
        from src.services.retrieval.hybrid_retrieval_service import get_hybrid_retrieval_service
        hybrid = get_hybrid_retrieval_service()
        retrieval = await hybrid.retrieve(
            query=f"job fit {resume_text[:200]}",
            top_k=15, top_n=8, use_hybrid=True,
        )
        pipeline = get_reasoning_pipeline()
        return await pipeline.reason(
            query=f"semantic job fit for {resume_text[:100]}",
            category="semantic_fit",
            prompt_id="semantic_fit",
            template_vars={
                "resume_text": resume_text,
                "job_text": job_text,
                "context": retrieval.context,
            },
        )


_svc: Optional[SemanticFitService] = None
def get_semantic_fit_service() -> SemanticFitService:
    global _svc
    if _svc is None: _svc = SemanticFitService()
    return _svc
def __getattr__(name: str):
    if name == "semantic_fit_service": return get_semantic_fit_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
