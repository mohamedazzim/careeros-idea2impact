"""
Learning path service — personalized engineering skill roadmaps.

Generates dependency-ordered learning paths across 8 categories,
prioritized by impact with difficulty and time estimates.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import json
import logging
from typing import Any, Optional
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse
logger = logging.getLogger(__name__)

class LearningPathService:
    async def analyze(self, skill_gaps: Any="", ats_evaluation: Any="", recruiter_review: Any="", contradictions: Any="", context: str="") -> StructuredResponse:
        return await get_reasoning_pipeline().reason(query="learning path", category="strategy", prompt_id="learning_path",
            template_vars={"skill_gaps": json.dumps(skill_gaps, default=str), "ats_evaluation": json.dumps(ats_evaluation, default=str),
                "recruiter_review": json.dumps(recruiter_review, default=str), "contradictions": json.dumps(contradictions, default=str), "context": context})

_svc: Optional[LearningPathService] = None
def get_learning_path_service() -> LearningPathService:
    global _svc; _svc = _svc or LearningPathService(); return _svc
def __getattr__(n: str):
    if n == "learning_path_service": return get_learning_path_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
