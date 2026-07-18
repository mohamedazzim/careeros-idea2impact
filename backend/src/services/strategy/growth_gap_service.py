"""Growth gap service — identifies missing experiences and acceleration constraints."""
import json
import logging
from typing import Any, Optional
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse
logger = logging.getLogger(__name__)

class GrowthGapService:
    async def analyze(self, trajectory: Any="", ats_evaluation: Any="", skill_gaps: Any="", context: str="") -> StructuredResponse:
        return await get_reasoning_pipeline().reason(query="growth gaps", category="strategy", prompt_id="career_trajectory",
            template_vars={"resume_text": "", "ats_evaluation": json.dumps(ats_evaluation, default=str),
                "semantic_fit": "", "contradictions": json.dumps(skill_gaps, default=str), "context": context})

_svc: Optional[GrowthGapService] = None
def get_growth_gap_service(): global _svc; _svc = _svc or GrowthGapService(); return _svc
def __getattr__(n):
    if n == "growth_gap_service": return get_growth_gap_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
