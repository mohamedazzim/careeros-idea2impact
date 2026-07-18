"""
Hardened strategic reasoning service — multi-service career strategy orchestrator.

Phase 4C Hardening: wired concurrency/stage-latency/timeout metrics, fixed
Phase 2 tuple destructuring, removed _elapsed_ms, per-stage observability hooks.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import asyncio
import logging
import time
from typing import Dict, Any

from src.core.config import settings
from src.observability.metrics import (
    INTELLIGENCE_STAGE_TIMEOUT,
    INTELLIGENCE_STAGE_LATENCY,
    INTELLIGENCE_CONCURRENCY_PRESSURE,
)
from src.services.strategy.strategy_observability import get_strategy_observability

logger = logging.getLogger(__name__)


class StrategicReasoningService:
    """Orchestrates multiple strategy services into a coherent career strategy.

    Phase 1 (parallel): trajectory, learning_path, ai_readiness, hiring_probability
    Phase 2 (sequential): opportunity prioritization
    
    All stages bounded by STRATEGY_MAX_CONCURRENT semaphore with per-stage
    timeout, latency tracking, and concurrency pressure monitoring.
    """

    async def reason(
        self,
        resume_text: str = "",
        ats_evaluation=None,
        semantic_fit=None,
        skill_gaps=None,
        recruiter_review=None,
        contradictions=None,
        achievements=None,
    ) -> Dict[str, Any]:
        from src.services.strategy.career_trajectory_service import get_career_trajectory_service
        from src.services.strategy.learning_path_service import get_learning_path_service
        from src.services.strategy.ai_readiness_service import get_ai_readiness_service
        from src.services.strategy.hiring_probability_service import get_hiring_probability_service
        from src.services.strategy.opportunity_prioritization_service import get_opportunity_prioritization_service

        overall_start = time.monotonic()
        results: Dict[str, Any] = {}
        failures: Dict[str, str] = {}
        sem = asyncio.Semaphore(settings.STRATEGY_MAX_CONCURRENT)
        obs = get_strategy_observability()

        async def _run(name: str, coro):
            stage_start = time.monotonic()
            INTELLIGENCE_CONCURRENCY_PRESSURE.observe(
                settings.STRATEGY_MAX_CONCURRENT - sem._value
            )
            async with sem:
                try:
                    result = await asyncio.wait_for(
                        coro, timeout=settings.STRATEGY_STAGE_TIMEOUT
                    )
                    elapsed = (time.monotonic() - stage_start) * 1000
                    INTELLIGENCE_STAGE_LATENCY.labels(stage=name).observe(
                        elapsed / 1000
                    )
                    return name, result, elapsed
                except asyncio.TimeoutError:
                    INTELLIGENCE_STAGE_TIMEOUT.labels(stage=name).inc()
                    logger.warning(
                        f"Strategy stage '{name}' timed out after "
                        f"{settings.STRATEGY_STAGE_TIMEOUT}s"
                    )
                    return name, None, 0
                except Exception as e:
                    logger.error(f"Strategy stage '{name}' failed: {e}")
                    return name, None, 0

        # ── Phase 1: Parallel independent stages ─────────────────────
        gathered = await asyncio.gather(
            _run("trajectory", get_career_trajectory_service().analyze(
                resume_text, ats_evaluation, semantic_fit, contradictions
            )),
            _run("learning_path", get_learning_path_service().analyze(
                skill_gaps, ats_evaluation, recruiter_review, contradictions
            )),
            _run("ai_readiness", get_ai_readiness_service().analyze(
                resume_text, ats_evaluation, skill_gaps, semantic_fit
            )),
            _run("hiring_probability", get_hiring_probability_service().analyze(
                ats_evaluation, recruiter_review, skill_gaps
            )),
            return_exceptions=True,
        )

        for item in gathered:
            if isinstance(item, Exception):
                logger.error(f"Strategy gather crashed: {item}")
                continue
            if isinstance(item, tuple) and len(item) == 3:
                name, result, elapsed = item
                if result is not None:
                    results[name] = result
                    obs.record_stage_success(name, elapsed)
                else:
                    failures[name] = "timeout_or_error"

        # ── Phase 2: Dependent stages ───────────────────────────────
        if "trajectory" in results and "learning_path" in results:
            name, opp_result, _ = await _run(
                "opportunities",
                get_opportunity_prioritization_service().analyze(
                    results["trajectory"].data if hasattr(results["trajectory"], "data") else results["trajectory"],
                    results["learning_path"].data if hasattr(results["learning_path"], "data") else results["learning_path"],
                    results.get("ai_readiness", getattr(results.get("ai_readiness", {}), "data", {})),
                    results.get("hiring_probability", getattr(results.get("hiring_probability", {}), "data", {})),
                    contradictions,
                ),
            )
            if opp_result is not None:
                results["opportunities"] = opp_result
            else:
                failures["opportunities"] = "timeout_or_error"

        total_elapsed = round((time.monotonic() - overall_start) * 1000, 2)
        results["_meta"] = {
            "elapsed_ms": total_elapsed,
            "stages_completed": list(results.keys() - {"_meta"}),
            "stages_failed": failures,
        }

        obs.record_strategy_complete(total_elapsed, len(results), len(failures))
        return results


_svc: StrategicReasoningService | None = None


def get_strategic_reasoning_service() -> StrategicReasoningService:
    global _svc
    if _svc is None:
        _svc = StrategicReasoningService()
    return _svc


def reset_strategic_reasoning_service() -> None:
    global _svc
    _svc = None


def __getattr__(name: str):
    if name == "strategic_reasoning_service":
        return get_strategic_reasoning_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
