"""
Recommendation engine — evidence-grounded career recommendations.

Generates prioritized recommendations across 8 categories with
confidence scoring and impact assessments.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import logging
from typing import Any, Optional

from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)


class RecommendationEngine:
    async def generate(
        self,
        ats_score: Any = "",
        match_score: Any = "",
        strengths: Any = "",
        weaknesses: Any = "",
        skill_gaps: Any = "",
        achievement_analysis: Any = "",
        context: str = "",
    ) -> StructuredResponse:
        pipeline = get_reasoning_pipeline()
        return await pipeline.reason(
            query="generate career recommendations",
            category="recommendation",
            prompt_id="recommendation_advanced",
            template_vars={
                "ats_score": str(ats_score),
                "match_score": str(match_score),
                "strengths": str(strengths),
                "weaknesses": str(weaknesses),
                "skill_gaps": str(skill_gaps),
                "achievement_analysis": str(achievement_analysis),
                "context": context,
            },
        )


_svc: Optional[RecommendationEngine] = None
def get_recommendation_engine() -> RecommendationEngine:
    global _svc
    if _svc is None: _svc = RecommendationEngine()
    return _svc
def __getattr__(name: str):
    if name == "recommendation_engine": return get_recommendation_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
