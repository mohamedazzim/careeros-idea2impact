"""
Hardened career strategy pipeline — LangGraph-compatible strategy node.

Phase 4C Hardening: passes base_confidence, calls full observability stack,
defensive .get() chains removed in favor of safe access patterns.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import logging
from typing import Dict, Any

from src.services.strategy.strategic_reasoning_service import get_strategic_reasoning_service
from src.services.strategy.strategic_confidence_engine import get_strategic_confidence_engine
from src.services.strategy.strategy_observability import get_strategy_observability

logger = logging.getLogger(__name__)


def _safe_data(obj: Any) -> Any:
    """Safely extract .data from StructuredResponse or return object as-is."""
    if hasattr(obj, "data"):
        return obj.data
    return obj


class CareerStrategyPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume = state.get("resume_text") or state.get("resume_data", {}).get("text", "")
        ats = _safe_data(state.get("ats_result", {}))
        eval_results = state.get("evaluation_results", {})
        if not resume:
            return {"strategy_error": "No resume text", "strategy_status": "error"}

        obs = get_strategy_observability()
        try:
            svc = get_strategic_reasoning_service()
            strategy = await svc.reason(
                resume_text=resume,
                ats_evaluation=ats,
                semantic_fit=_safe_data(eval_results.get("semantic_fit", {})),
                skill_gaps=_safe_data(eval_results.get("skill_gaps", {})),
                recruiter_review=_safe_data(eval_results.get("recruiter", {})),
                contradictions=eval_results.get("contradictions", {}),
                achievements=_safe_data(eval_results.get("achievements", {})),
            )

            ats_score = ats.get("overall_score", 50) if isinstance(ats, dict) else 50
            base_conf = ats_score / 100.0

            conf = get_strategic_confidence_engine().calibrate(
                strategy_outputs=strategy,
                base_confidence=base_conf,
                contradictions=eval_results.get("contradictions", {}),
            )

            # Per-stage observability
            for stype, result in strategy.items():
                if stype in ("_meta", "opportunities"):
                    continue
                c = conf["per_stage"].get(stype, conf["overall"])
                obs.record_confidence(stype, c)

            if "trajectory" in strategy:
                obs.record_trajectory(conf["per_stage"].get("trajectory", 0.5))
            if "hiring_probability" in strategy:
                obs.record_hiring(conf["per_stage"].get("hiring_probability", 0.5))
            if "ai_readiness" in strategy:
                obs.record_ai_readiness(conf["per_stage"].get("ai_readiness", 0.5))

            return {
                "strategy_result": strategy,
                "strategy_confidence": conf,
                "strategy_status": "success",
            }
        except Exception as e:
            obs.record_suppression(f"career_strategy_error:{e}")
            return {"strategy_error": str(e), "strategy_status": "error"}


_pipeline: CareerStrategyPipeline | None = None


def get_career_strategy_pipeline() -> CareerStrategyPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = CareerStrategyPipeline()
    return _pipeline


def reset_career_strategy_pipeline() -> None:
    global _pipeline
    _pipeline = None


def __getattr__(name: str):
    if name == "career_strategy_pipeline":
        return get_career_strategy_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
