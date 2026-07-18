"""
Achievement analysis service — impact and quality evaluation of resume achievements.

Classifies each achievement as strong/adequate/weak, detects vague bullets,
and suggests specific improvements.
"""
import logging
from typing import Optional

from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)


class AchievementAnalysisService:
    async def analyze(self, resume_text: str) -> StructuredResponse:
        from src.services.retrieval.hybrid_retrieval_service import get_hybrid_retrieval_service
        hybrid = get_hybrid_retrieval_service()
        retrieval = await hybrid.retrieve(
            query=f"achievements {resume_text[:200]}",
            top_k=10, top_n=5, use_hybrid=True,
        )
        pipeline = get_reasoning_pipeline()
        return await pipeline.reason(
            query=f"achievement analysis for {resume_text[:100]}",
            category="resume",
            prompt_id="achievement_analysis",
            template_vars={
                "resume_text": resume_text,
                "context": retrieval.context,
            },
        )


_svc: Optional[AchievementAnalysisService] = None
def get_achievement_analysis_service() -> AchievementAnalysisService:
    global _svc
    if _svc is None: _svc = AchievementAnalysisService()
    return _svc
def __getattr__(name: str):
    if name == "achievement_analysis_service": return get_achievement_analysis_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
