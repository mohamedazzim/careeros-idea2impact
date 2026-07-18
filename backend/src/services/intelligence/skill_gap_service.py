"""
Skill gap analysis service — enterprise skill intelligence.

Detects missing hard skills, enterprise experience, architecture exposure,
cloud/devops exposure, AI/ML capabilities, leadership indicators,
project depth, and production-scale experience.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import logging
from typing import Optional

from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)


class SkillGapService:
    async def analyze(
        self,
        resume_text: str,
        job_text: str,
        context: str = "",
    ) -> StructuredResponse:
        from src.services.retrieval.hybrid_retrieval_service import get_hybrid_retrieval_service
        hybrid = get_hybrid_retrieval_service()
        retrieval = await hybrid.retrieve(
            query=f"skill gaps {resume_text[:200]}",
            top_k=15, top_n=8, use_hybrid=True,
        )

        pipeline = get_reasoning_pipeline()
        return await pipeline.reason(
            query=f"skill gap analysis for {resume_text[:100]}",
            category="scoring",
            prompt_id="skill_gap_advanced",
            template_vars={
                "resume_text": resume_text,
                "job_text": job_text,
                "context": retrieval.context or context,
            },
        )


_svc: Optional[SkillGapService] = None
def get_skill_gap_service() -> SkillGapService:
    global _svc
    if _svc is None: _svc = SkillGapService()
    return _svc
def __getattr__(name: str):
    if name == "skill_gap_service": return get_skill_gap_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
