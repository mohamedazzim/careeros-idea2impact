"""Learning roadmap + opportunity + portfolio + AI readiness pipelines.

Phase 4C Hardening: standardized get_*() singletons, observability hooks,
structured error returns.
"""
import logging
from typing import Dict, Any

from src.services.strategy.strategy_observability import get_strategy_observability

logger = logging.getLogger(__name__)


class LearningRoadmapPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.strategy.learning_path_service import get_learning_path_service
        eval_results = state.get("evaluation_results", {})
        if not eval_results:
            return {"learning_roadmap_error": "No evaluation results", "learning_roadmap_status": "error"}
        try:
            svc = get_learning_path_service()
            result = await svc.analyze(
                skill_gaps=eval_results.get("skill_gaps", {}),
                ats_evaluation=state.get("ats_result", {}),
                recruiter_review=eval_results.get("recruiter", {}),
                contradictions=eval_results.get("contradictions", {}),
            )
            return {"learning_roadmap_result": result.model_dump(), "learning_roadmap_status": "success"}
        except Exception as e:
            get_strategy_observability().record_suppression("learning_roadmap_error")
            return {"learning_roadmap_error": str(e), "learning_roadmap_status": "error"}


_learning_roadmap_pipeline = None
def get_learning_roadmap_pipeline() -> LearningRoadmapPipeline:
    global _learning_roadmap_pipeline
    if _learning_roadmap_pipeline is None: _learning_roadmap_pipeline = LearningRoadmapPipeline()
    return _learning_roadmap_pipeline


class OpportunityStrategyPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.strategy.opportunity_prioritization_service import get_opportunity_prioritization_service
        strategy = state.get("strategy_result", {})
        try:
            svc = get_opportunity_prioritization_service()
            result = await svc.analyze(
                trajectory=strategy.get("trajectory", {}),
                learning_path=strategy.get("learning_path", {}),
                ai_readiness=strategy.get("ai_readiness", {}),
                hiring_probability=strategy.get("hiring_probability", {}),
                contradictions=state.get("evaluation_results", {}).get("contradictions", {}),
            )
            return {"opportunity_result": result.model_dump(), "opportunity_status": "success"}
        except Exception as e:
            get_strategy_observability().record_suppression("opportunity_strategy_error")
            return {"opportunity_error": str(e), "opportunity_status": "error"}


_opportunity_strategy_pipeline = None
def get_opportunity_strategy_pipeline() -> OpportunityStrategyPipeline:
    global _opportunity_strategy_pipeline
    if _opportunity_strategy_pipeline is None: _opportunity_strategy_pipeline = OpportunityStrategyPipeline()
    return _opportunity_strategy_pipeline


class PortfolioGrowthPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.strategy.roadmap_generation_service import get_roadmap_generation_service
        strategy = state.get("strategy_result", {})
        try:
            svc = get_roadmap_generation_service()
            result = await svc.generate(
                trajectory=strategy.get("trajectory", {}),
                learning_path=strategy.get("learning_path", {}),
                opportunities=state.get("opportunity_result", {}).get("data", {}),
                hiring_probability=strategy.get("hiring_probability", {}),
            )
            return {"roadmap_result": result.model_dump(), "roadmap_status": "success"}
        except Exception as e:
            get_strategy_observability().record_suppression("portfolio_growth_error")
            return {"roadmap_error": str(e), "roadmap_status": "error"}


_portfolio_growth_pipeline = None
def get_portfolio_growth_pipeline() -> PortfolioGrowthPipeline:
    global _portfolio_growth_pipeline
    if _portfolio_growth_pipeline is None: _portfolio_growth_pipeline = PortfolioGrowthPipeline()
    return _portfolio_growth_pipeline


class AIEngineeringReadinessPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.strategy.ai_readiness_service import get_ai_readiness_service
        eval_results = state.get("evaluation_results", {})
        resume = state.get("resume_text") or state.get("resume_data", {}).get("text", "")
        if not resume:
            return {"ai_readiness_error": "No resume", "ai_readiness_status": "error"}
        try:
            svc = get_ai_readiness_service()
            result = await svc.analyze(
                resume_text=resume,
                ats_evaluation=state.get("ats_result", {}),
                skill_gaps=eval_results.get("skill_gaps", {}),
                semantic_fit=eval_results.get("semantic_fit", {}),
            )
            return {"ai_readiness_result": result.model_dump(), "ai_readiness_status": "success"}
        except Exception as e:
            get_strategy_observability().record_suppression("ai_readiness_error")
            return {"ai_readiness_error": str(e), "ai_readiness_status": "error"}


_ai_engineering_readiness_pipeline = None
def get_ai_engineering_readiness_pipeline() -> AIEngineeringReadinessPipeline:
    global _ai_engineering_readiness_pipeline
    if _ai_engineering_readiness_pipeline is None: _ai_engineering_readiness_pipeline = AIEngineeringReadinessPipeline()
    return _ai_engineering_readiness_pipeline


def __getattr__(name: str):
    mapping = {
        "learning_roadmap_pipeline": get_learning_roadmap_pipeline,
        "opportunity_strategy_pipeline": get_opportunity_strategy_pipeline,
        "portfolio_growth_pipeline": get_portfolio_growth_pipeline,
        "ai_engineering_readiness_pipeline": get_ai_engineering_readiness_pipeline,
    }
    if name in mapping: return mapping[name]()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
