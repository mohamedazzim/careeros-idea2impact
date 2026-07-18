"""Milestone planning service — measurable career checkpoint generation."""
import json
import logging
from typing import Any, Optional
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse
logger = logging.getLogger(__name__)

class MilestonePlanningService:
    async def generate(self, roadmap: Any="", learning_path: Any="", context: str="") -> StructuredResponse:
        return await get_reasoning_pipeline().reason(query="milestones", category="strategy", prompt_id="roadmap_generation",
            template_vars={"trajectory": json.dumps(roadmap, default=str), "learning_path": json.dumps(learning_path, default=str),
                "opportunities": "", "hiring_probability": "", "context": context})

_svc: Optional[MilestonePlanningService] = None
def get_milestone_planning_service(): global _svc; _svc = _svc or MilestonePlanningService(); return _svc
def __getattr__(n):
    if n == "milestone_planning_service": return get_milestone_planning_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
