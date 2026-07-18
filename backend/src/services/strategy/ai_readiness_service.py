"""AI readiness service — LLM, RAG, orchestration, agentic, MLOps, AI production maturity."""
import json
import logging
from typing import Any, Optional
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse
logger = logging.getLogger(__name__)

class AIReadinessService:
    async def analyze(self, resume_text: str="", ats_evaluation: Any="", skill_gaps: Any="", semantic_fit: Any="", context: str="") -> StructuredResponse:
        return await get_reasoning_pipeline().reason(query="AI readiness", category="strategy", prompt_id="ai_readiness",
            template_vars={"resume_text": resume_text, "ats_evaluation": json.dumps(ats_evaluation, default=str),
                "skill_gaps": json.dumps(skill_gaps, default=str), "semantic_fit": json.dumps(semantic_fit, default=str), "context": context})

_svc: Optional[AIReadinessService] = None
def get_ai_readiness_service(): global _svc; _svc = _svc or AIReadinessService(); return _svc
def __getattr__(n):
    if n == "ai_readiness_service": return get_ai_readiness_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
