"""Hiring probability service — evidence-grounded hiring competitiveness analysis."""
import json
import logging
from typing import Any, Optional
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse
logger = logging.getLogger(__name__)

class HiringProbabilityService:
    async def analyze(self, ats_score: Any="", recruiter_review: Any="", skill_gaps: Any="", portfolio_strength: Any="", context: str="") -> StructuredResponse:
        return await get_reasoning_pipeline().reason(query="hiring probability", category="strategy", prompt_id="hiring_probability",
            template_vars={"ats_score": json.dumps(ats_score, default=str), "recruiter_review": json.dumps(recruiter_review, default=str),
                "skill_gaps": json.dumps(skill_gaps, default=str), "portfolio_strength": json.dumps(portfolio_strength, default=str), "context": context})

_svc: Optional[HiringProbabilityService] = None
def get_hiring_probability_service(): global _svc; _svc = _svc or HiringProbabilityService(); return _svc
def __getattr__(n):
    if n == "hiring_probability_service": return get_hiring_probability_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
