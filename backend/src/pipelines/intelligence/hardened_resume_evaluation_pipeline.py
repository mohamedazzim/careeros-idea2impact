"""
Hardened resume evaluation pipeline — parallelized with bounded concurrency,
timeout-safe orchestration, and partial intelligence recovery.

Runs independent stages (skill_gap, semantic_fit, achievement_analysis)
in parallel, then dependent stages (recruiter, recommendations) sequentially.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import asyncio
import logging
import time
from typing import Dict, Any

from src.services.intelligence.skill_gap_service import get_skill_gap_service
from src.services.intelligence.semantic_fit_service import get_semantic_fit_service
from src.services.intelligence.achievement_analysis_service import get_achievement_analysis_service
from src.services.intelligence.recruiter_evaluation_service import get_recruiter_evaluation_service
from src.services.intelligence.resume_analysis_service import get_resume_analysis_service
from src.services.intelligence.contradiction_analysis_service import get_contradiction_analyzer
from src.services.intelligence.hardened_recommendation_engine import get_hardened_recommendation_engine
from src.services.intelligence.confidence_engine import get_confidence_engine
from src.services.intelligence.reasoning_trace_builder import get_reasoning_trace_builder
from src.observability.metrics import (
    INTELLIGENCE_CONCURRENCY_PRESSURE,
    INTELLIGENCE_STAGE_TIMEOUT,
)

logger = logging.getLogger(__name__)

STAGE_TIMEOUT = 45.0  # seconds per intelligence stage
MAX_CONCURRENT = 3


class HardenedResumeEvaluationPipeline:
    """Parallelized resume evaluation with timeout and partial recovery."""

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume = state.get("resume_text") or state.get("resume_data", {}).get("text", "")
        job = state.get("job_text") or state.get("job_data", {}).get("description", "")
        ats_result = state.get("ats_result", {})

        if not resume:
            return {"evaluation_error": "No resume text", "evaluation_status": "error"}

        overall_start = time.monotonic()
        results = {}
        failures = {}
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def run_with_timeout(name: str, coro):
            async with semaphore:
                try:
                    INTELLIGENCE_CONCURRENCY_PRESSURE.observe(
                        MAX_CONCURRENT - semaphore._value
                    )
                    return name, await asyncio.wait_for(coro, timeout=STAGE_TIMEOUT)
                except asyncio.TimeoutError:
                    INTELLIGENCE_STAGE_TIMEOUT.labels(stage=name).inc()
                    logger.warning(f"Stage '{name}' timed out after {STAGE_TIMEOUT}s")
                    return name, None
                except Exception as e:
                    logger.error(f"Stage '{name}' failed: {e}")
                    return name, None

        # ── Phase 1: Parallel independent stages ─────────────────────
        gap_svc = get_skill_gap_service()
        fit_svc = get_semantic_fit_service()
        achieve_svc = get_achievement_analysis_service()
        resume_svc = get_resume_analysis_service()

        parallel_tasks = [
            run_with_timeout("skill_gaps", gap_svc.analyze(resume, job)),
            run_with_timeout("semantic_fit", fit_svc.analyze(resume, job)),
            run_with_timeout("achievements", achieve_svc.analyze(resume)),
            run_with_timeout("resume_analysis", resume_svc.analyze(resume, enable_claude=False)),
        ]

        gathered = await asyncio.gather(*parallel_tasks, return_exceptions=True)
        for item in gathered:
            if isinstance(item, Exception):
                logger.error(f"Parallel stage crashed: {item}")
                continue
            if isinstance(item, tuple) and len(item) == 2:
                name, result = item
                if result is not None:
                    results[name] = result
                else:
                    failures[name] = "timeout_or_error"

        # ── Phase 2: Contradiction analysis (depends on Phase 1) ────
        ats_data = ats_result.get("data", {}) if isinstance(ats_result, dict) else {}
        contradictions = get_contradiction_analyzer().analyze(
            resume_text=resume,
            job_text=job,
            ats_data=ats_data,
            skill_gaps=results.get("skill_gaps", {}).get("data", None)
                if isinstance(results.get("skill_gaps"), dict) else None,
        )
        results["contradictions"] = contradictions

        # ── Phase 3: Recruiter review (depends on ATS + Phase 1) ────
        recruiter = get_recruiter_evaluation_service()
        try:
            results["recruiter"] = await asyncio.wait_for(
                recruiter.evaluate(resume, job, ats_data),
                timeout=STAGE_TIMEOUT,
            )
        except (asyncio.TimeoutError, Exception) as e:
            failures["recruiter"] = str(e)

        # ── Phase 4: Recommendations (best-effort) ───────────────────
        try:
            rec_engine = get_hardened_recommendation_engine()
            results["recommendations"] = await rec_engine.generate(
                ats_score=ats_data.get("overall_score", 0),
                strengths=ats_data.get("strengths", []),
                weaknesses=ats_data.get("weaknesses", []),
                skill_gaps=results.get("skill_gaps", {}),
                achievement_analysis=results.get("achievements", {}),
                contradictions=contradictions,
            )
        except Exception as e:
            failures["recommendations"] = str(e)

        # ── Confidence calibration ───────────────────────────────────
        confidence = get_confidence_engine()
        confidence_breakdown = confidence.score(
            contradiction_report=contradictions,
        )
        results["confidence"] = confidence_breakdown.model_dump()

        # ── Reasoning trace ──────────────────────────────────────────
        trace = get_reasoning_trace_builder()
        reasoning = trace.build_trace(
            query=f"resume evaluation for {resume[:100]}",
            context="",
            citations=[],
            fused=[],
            claude_output=results,
            confidence=confidence_breakdown.overall,
        )
        results["reasoning_trace"] = reasoning

        elapsed = (time.monotonic() - overall_start) * 1000
        status = "partial" if failures else "success"

        return {
            "evaluation_results": results,
            "evaluation_failures": failures,
            "evaluation_status": status,
            "evaluation_error": None if not failures else str(failures),
            "evaluation_latency_ms": round(elapsed, 2),
            "evaluation_confidence": confidence_breakdown.overall,
        }


_pipeline: HardenedResumeEvaluationPipeline | None = None


def get_hardened_resume_evaluation_pipeline() -> HardenedResumeEvaluationPipeline:
    global _pipeline
    if _pipeline is None: _pipeline = HardenedResumeEvaluationPipeline()
    return _pipeline


def __getattr__(name: str):
    if name == "hardened_resume_evaluation_pipeline":
        return get_hardened_resume_evaluation_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
