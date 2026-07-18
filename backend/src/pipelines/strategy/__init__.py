"""
Strategy pipelines — LangGraph-compatible career strategy nodes.

Phase 4C: career strategy, learning roadmap, opportunity strategy,
portfolio growth, and AI engineering readiness pipelines.
"""
from .career_strategy_pipeline import CareerStrategyPipeline

__all__ = [
    "CareerStrategyPipeline",
    "career_strategy_pipeline",
    "learning_roadmap_pipeline",
    "opportunity_strategy_pipeline",
    "portfolio_growth_pipeline",
    "ai_engineering_readiness_pipeline",
]

def __getattr__(name: str):
    if name == "career_strategy_pipeline":
        from .career_strategy_pipeline import get_career_strategy_pipeline; return get_career_strategy_pipeline()
    if name == "learning_roadmap_pipeline":
        from .strategy_extra_pipelines import get_learning_roadmap_pipeline; return get_learning_roadmap_pipeline()
    if name == "opportunity_strategy_pipeline":
        from .strategy_extra_pipelines import get_opportunity_strategy_pipeline; return get_opportunity_strategy_pipeline()
    if name == "portfolio_growth_pipeline":
        from .strategy_extra_pipelines import get_portfolio_growth_pipeline; return get_portfolio_growth_pipeline()
    if name == "ai_engineering_readiness_pipeline":
        from .strategy_extra_pipelines import get_ai_engineering_readiness_pipeline; return get_ai_engineering_readiness_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
