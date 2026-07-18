"""Opportunity prioritization service — strategic growth opportunity ranking."""
import json
import logging
from typing import Any, Optional
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse
logger = logging.getLogger(__name__)

class OpportunityPrioritizationService:
    async def analyze(self, trajectory: Any="", learning_path: Any="", ai_readiness: Any="", hiring_probability: Any="", contradictions: Any="", context: str="") -> StructuredResponse:
        return await get_reasoning_pipeline().reason(query="opportunities", category="strategy", prompt_id="opportunity_prioritization",
            template_vars={"trajectory": json.dumps(trajectory, default=str), "learning_path": json.dumps(learning_path, default=str),
                "ai_readiness": json.dumps(ai_readiness, default=str), "hiring_probability": json.dumps(hiring_probability, default=str),
                "contradictions": json.dumps(contradictions, default=str), "context": context})

_svc: Optional[OpportunityPrioritizationService] = None
def get_opportunity_prioritization_service(): global _svc; _svc = _svc or OpportunityPrioritizationService(); return _svc
def __getattr__(n):
    if n == "opportunity_prioritization_service": return get_opportunity_prioritization_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
