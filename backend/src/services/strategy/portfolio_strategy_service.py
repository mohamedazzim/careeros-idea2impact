"""Portfolio strategy service — project maturity and evolution intelligence."""
import logging
from typing import Any, Optional
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse
logger = logging.getLogger(__name__)

class PortfolioStrategyService:
    async def analyze(self, resume_text: str="", achievements: Any="", recruiter_review: Any="", context: str="") -> StructuredResponse:
        return await get_reasoning_pipeline().reason(query="portfolio strategy", category="strategy", prompt_id="opportunity_prioritization",
            template_vars={"trajectory": "", "learning_path": "", "ai_readiness": "", "hiring_probability": "", "contradictions": "", "context": context})

_svc: Optional[PortfolioStrategyService] = None
def get_portfolio_strategy_service(): global _svc; _svc = _svc or PortfolioStrategyService(); return _svc
def __getattr__(n):
    if n == "portfolio_strategy_service": return get_portfolio_strategy_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
