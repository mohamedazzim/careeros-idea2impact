"""Roadmap generation service — time-phased career roadmap generation."""
import json
import logging
from typing import Any, Optional
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse
logger = logging.getLogger(__name__)

class RoadmapGenerationService:
    async def generate(self, trajectory: Any="", learning_path: Any="", opportunities: Any="", hiring_probability: Any="", context: str="") -> StructuredResponse:
        return await get_reasoning_pipeline().reason(query="career roadmap", category="strategy", prompt_id="roadmap_generation",
            template_vars={"trajectory": json.dumps(trajectory, default=str), "learning_path": json.dumps(learning_path, default=str),
                "opportunities": json.dumps(opportunities, default=str), "hiring_probability": json.dumps(hiring_probability, default=str), "context": context})

_svc: Optional[RoadmapGenerationService] = None
def get_roadmap_generation_service(): global _svc; _svc = _svc or RoadmapGenerationService(); return _svc
def __getattr__(n):
    if n == "roadmap_generation_service": return get_roadmap_generation_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
