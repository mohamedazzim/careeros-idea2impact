"""
Architecture maturity service — system-design, distributed-systems, cloud, DevOps maturity analysis.
"""
import json
import logging
from typing import Any, Optional
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse
logger = logging.getLogger(__name__)

class ArchitectureMaturityService:
    async def analyze(self, resume_text: str="", ats_evaluation: Any="", context: str="") -> StructuredResponse:
        return await get_reasoning_pipeline().reason(query="architecture maturity", category="strategy", prompt_id="career_trajectory",
            template_vars={"resume_text": resume_text, "ats_evaluation": json.dumps(ats_evaluation, default=str),
                "semantic_fit": "", "contradictions": "", "context": context})

_svc: Optional[ArchitectureMaturityService] = None
def get_architecture_maturity_service(): global _svc; _svc = _svc or ArchitectureMaturityService(); return _svc
def __getattr__(n):
    if n == "architecture_maturity_service": return get_architecture_maturity_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
