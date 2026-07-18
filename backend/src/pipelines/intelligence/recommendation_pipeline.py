"""
Recommendation pipeline — LangGraph node for career recommendations.
"""
import logging
from typing import Dict, Any
from src.services.intelligence.recommendation_engine import get_recommendation_engine

logger = logging.getLogger(__name__)


class RecommendationPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        ats = state.get("ats_result", {}).get("data", {})
        gaps = state.get("skill_gap_result", {}).get("data", {})
        try:
            rec = get_recommendation_engine()
            result = await rec.generate(
                ats_score=ats.get("overall_score", 0),
                strengths=ats.get("strengths", []),
                weaknesses=ats.get("weaknesses", []),
                skill_gaps=gaps,
            )
            return {"recommendation_result": result.model_dump(), "recommendation_status": "success"}
        except Exception as e:
            return {"recommendation_error": str(e), "recommendation_status": "error"}


_p = None
def get_recommendation_pipeline():
    global _p
    if _p is None: _p = RecommendationPipeline()
    return _p
def __getattr__(n: str):
    if n == "recommendation_pipeline": return get_recommendation_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
