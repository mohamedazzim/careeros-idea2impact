"""
Market alignment service — dedicated market intelligence for career positioning.

Phase 4C Hardening: dedicated market_alignment prompt (no longer reuses
hiring_probability). Analyzes hiring trends, stack demand, and AI engineering
market signals.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import json
import logging
from typing import Any

from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)


class MarketAlignmentService:
    async def analyze(
        self,
        resume_text: str = "",
        hiring_probability: Any = "",
        ai_readiness: Any = "",
        context: str = "",
    ) -> StructuredResponse:
        return await get_reasoning_pipeline().reason(
            query="market alignment",
            category="strategy",
            prompt_id="market_alignment",
            template_vars={
                "resume_text": resume_text,
                "hiring_signals": json.dumps(hiring_probability, default=str),
                "ai_readiness_signals": json.dumps(ai_readiness, default=str),
                "context": context,
            },
        )


_svc: MarketAlignmentService | None = None


def get_market_alignment_service() -> MarketAlignmentService:
    global _svc
    if _svc is None:
        _svc = MarketAlignmentService()
    return _svc


def __getattr__(name: str):
    if name == "market_alignment_service":
        return get_market_alignment_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
