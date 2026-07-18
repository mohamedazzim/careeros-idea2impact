"""
Hardened strategic confidence engine.

Phase 4C Hardening: config-driven weights, base_confidence default, per-stage
quality scoring, contradiction penalty integration, completeness depth checks.

Stateless, async-safe, observable.
"""
import logging
from typing import Dict, Any, Optional

from src.observability.metrics import (
    STRATEGY_CONFIDENCE,
    CONTRADICTION_PENALTY,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_CONFIDENCE = 0.5
DEFAULT_COMPLETENESS_BASE = 0.25
DEFAULT_COMPLETENESS_FACTOR = 0.75


class StrategicConfidenceEngine:
    """Calibrates confidence for career strategy outputs.

    Factors:
    - Completeness: what fraction of strategy stages produced results
    - Depth: quality of results (StructuredResponse confidence where available)
    - Contradiction: penalty for detected contradictions
    """

    def calibrate(
        self,
        strategy_outputs: Dict[str, Any],
        base_confidence: Optional[float] = None,
        contradictions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        base = (
            base_confidence if base_confidence is not None
            else DEFAULT_BASE_CONFIDENCE
        )

        # Stage completeness
        stages = ["trajectory", "learning_path", "ai_readiness", "hiring_probability"]
        completed = 0
        per_stage_confidence: Dict[str, float] = {}

        for stage in stages:
            result = strategy_outputs.get(stage)
            if result is not None:
                completed += 1
                if hasattr(result, "metadata") and hasattr(result.metadata, "confidence_overall"):
                    per_stage_confidence[stage] = result.metadata.confidence_overall
                else:
                    per_stage_confidence[stage] = base

        factor_present = completed / max(len(stages), 1)
        adjusted = base * (
            DEFAULT_COMPLETENESS_BASE + DEFAULT_COMPLETENESS_FACTOR * factor_present
        )

        # Contradiction penalty
        con_penalty = 0.0
        if contradictions and contradictions.get("contradictions_detected"):
            severity = contradictions.get("severity", "none")
            sev_map = {"none": 0.0, "medium": 0.08, "high": 0.18, "critical": 0.30}
            con_penalty = sev_map.get(severity, 0.0)
            adjusted = max(0.05, adjusted - con_penalty)
            CONTRADICTION_PENALTY.observe(con_penalty)

        adjusted = round(adjusted, 4)

        STRATEGY_CONFIDENCE.labels(strategy_type="overall").observe(adjusted)
        for stage, conf in per_stage_confidence.items():
            STRATEGY_CONFIDENCE.labels(strategy_type=stage).observe(conf)

        return {
            "overall": adjusted,
            "base_confidence": round(base, 4),
            "completeness_factor": round(factor_present, 2),
            "contradiction_penalty": round(con_penalty, 4),
            "per_stage": per_stage_confidence,
            "stages_completed": completed,
            "total_stages": len(stages),
        }


_svc: StrategicConfidenceEngine | None = None


def get_strategic_confidence_engine() -> StrategicConfidenceEngine:
    global _svc
    if _svc is None:
        _svc = StrategicConfidenceEngine()
    return _svc


def reset_strategic_confidence_engine() -> None:
    global _svc
    _svc = None


def __getattr__(name: str):
    if name == "strategic_confidence_engine":
        return get_strategic_confidence_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
