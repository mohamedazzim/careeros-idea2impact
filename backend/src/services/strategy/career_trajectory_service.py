"""
Career trajectory service — engineering maturity and role-transition readiness.

Analyzes current engineering maturity, predicts readiness for future roles,
identifies trajectory gaps and acceleration opportunities.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import json
import logging
from typing import Any, Optional
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)


class CareerTrajectoryService:
    """Career trajectory analysis with readiness prediction."""

    async def analyze(
        self,
        resume_text: str = "",
        ats_evaluation: Any = "",
        semantic_fit: Any = "",
        contradictions: Any = "",
        context: str = "",
    ) -> StructuredResponse:
        pipeline = get_reasoning_pipeline()
        return await pipeline.reason(
            query=f"career trajectory for {resume_text[:100]}",
            category="strategy",
            prompt_id="career_trajectory",
            template_vars={
                "resume_text": resume_text,
                "ats_evaluation": json.dumps(ats_evaluation, default=str),
                "semantic_fit": json.dumps(semantic_fit, default=str),
                "contradictions": json.dumps(contradictions, default=str),
                "context": context,
            },
        )


_svc: Optional[CareerTrajectoryService] = None
def get_career_trajectory_service() -> CareerTrajectoryService:
    global _svc
    if _svc is None: _svc = CareerTrajectoryService()
    return _svc
def __getattr__(name: str):
    if name == "career_trajectory_service": return get_career_trajectory_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
