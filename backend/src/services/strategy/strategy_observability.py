"""
Hardened strategy observability — centralized metrics for career strategy.

Phase 4C Hardening: all 8 record methods now wired, stage tracking added,
strategy-level completion tracking.

Stateless, async-safe.
"""
import logging

from src.observability.metrics import (
    STRATEGY_ROADMAP_LATENCY,
    STRATEGY_CONFIDENCE,
    STRATEGY_RECOMMENDATION_SUPPRESSION,
    STRATEGY_HALLUCINATION,
    STRATEGY_TRAJECTORY_CONSISTENCY,
    STRATEGY_ROADMAP_COMPLEXITY,
    STRATEGY_HIRING_CONFIDENCE,
    STRATEGY_AI_READINESS,
    STRATEGY_OPPORTUNITY_RANK,
    INTELLIGENCE_STAGE_LATENCY,
)

logger = logging.getLogger(__name__)


class StrategyObservability:
    def record_roadmap(self, roadmap_type: str, latency_ms: float, item_count: int) -> None:
        STRATEGY_ROADMAP_LATENCY.labels(roadmap_type=roadmap_type).observe(latency_ms / 1000)
        STRATEGY_ROADMAP_COMPLEXITY.observe(item_count)

    def record_confidence(self, strategy_type: str, score: float) -> None:
        STRATEGY_CONFIDENCE.labels(strategy_type=strategy_type).observe(score)

    def record_hallucination(self, strategy_type: str, severity: str) -> None:
        STRATEGY_HALLUCINATION.labels(strategy_type=strategy_type, severity=severity).inc()

    def record_suppression(self, reason: str) -> None:
        STRATEGY_RECOMMENDATION_SUPPRESSION.labels(reason=reason).inc()

    def record_trajectory(self, consistency: float) -> None:
        STRATEGY_TRAJECTORY_CONSISTENCY.observe(consistency)

    def record_hiring(self, confidence: float) -> None:
        STRATEGY_HIRING_CONFIDENCE.observe(confidence)

    def record_ai_readiness(self, score: float) -> None:
        STRATEGY_AI_READINESS.observe(score)

    def record_opportunity(self, score: float) -> None:
        STRATEGY_OPPORTUNITY_RANK.observe(score)

    def record_stage_success(self, stage: str, latency_ms: float) -> None:
        INTELLIGENCE_STAGE_LATENCY.labels(stage=stage).observe(latency_ms / 1000)

    def record_strategy_complete(
        self, total_ms: float, stages_succeeded: int, stages_failed: int
    ) -> None:
        STRATEGY_CONFIDENCE.labels(
            strategy_type="completion"
        ).observe(
            stages_succeeded / max(stages_succeeded + stages_failed, 1)
        )


_svc: StrategyObservability | None = None


def get_strategy_observability() -> StrategyObservability:
    global _svc
    if _svc is None:
        _svc = StrategyObservability()
    return _svc


def reset_strategy_observability() -> None:
    global _svc
    _svc = None


def __getattr__(name: str):
    if name == "strategy_observability":
        return get_strategy_observability()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
