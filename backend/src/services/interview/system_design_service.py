"""
System design interview service — architecture reasoning evaluation.

Evaluates scalability reasoning, architecture decomposition, fault tolerance,
observability design, async orchestration, AI infrastructure, governance,
deployment strategy, tradeoff reasoning, and production realism.

Phase 4D: System design interview intelligence.
"""
import logging

from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)

SYSTEM_DESIGN_SCENARIOS = [
    "url_shortener", "chat_system", "notification_service",
    "search_engine", "file_storage", "rate_limiter",
    "real_time_analytics", "ml_inference_platform",
    "distributed_job_scheduler", "api_gateway",
]


class SystemDesignService:
    async def generate_scenario(
        self,
        resume_text: str = "",
        difficulty: str = "intermediate",
        scenario: str = "chat_system",
        architecture_maturity: str = "",
        context: str = "",
    ) -> StructuredResponse:
        return await get_reasoning_pipeline().reason(
            query=f"system design interview {scenario} {difficulty}",
            category="interview",
            prompt_id="system_design_interview",
            template_vars={
                "resume_text": resume_text,
                "difficulty": difficulty,
                "scenario": scenario,
                "architecture_maturity": architecture_maturity,
                "context": context,
            },
        )

    async def evaluate_design(
        self,
        scenario: str,
        design_response: str,
        difficulty: str,
        rubric_context: str = "",
        candidate_context: str = "",
    ) -> StructuredResponse:
        return await get_reasoning_pipeline().reason(
            query=f"evaluate system design {scenario} {difficulty}",
            category="interview",
            prompt_id="system_design_evaluation",
            template_vars={
                "scenario": scenario,
                "design_response": design_response,
                "difficulty": difficulty,
                "rubric_context": rubric_context,
                "candidate_context": candidate_context,
            },
        )


_svc: SystemDesignService | None = None
def get_system_design_service() -> SystemDesignService:
    global _svc
    if _svc is None: _svc = SystemDesignService()
    return _svc
def __getattr__(n):
    if n == "system_design_service": return get_system_design_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
