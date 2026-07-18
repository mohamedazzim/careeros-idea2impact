"""
Intelligence metrics — Phase 4B observability for ATS, recruiter, and resume intelligence.

Tracks latency, hallucination detections, confidence distributions, and
recommendation quality per intelligence category.

Stateless, async-safe, metric-emitting.
"""
import logging
from typing import Optional

from src.observability.metrics import (
    CLAUDE_LATENCY,
    LLM_TOKEN_USAGE,
    CONFIDENCE_DISTRIBUTION,
    CONFIDENCE_BREAKDOWN,
    HALLUCINATION_DETECTED,
    HALLUCINATION_RISK_SCORE,
    OUTPUT_VALIDATION_FAILURES,
)

logger = logging.getLogger(__name__)


class IntelligenceMetrics:
    """Centralized Phase 4B metrics emission."""

    def record_evaluation(
        self,
        category: str,
        duration_ms: float,
        tokens_in: int,
        tokens_out: int,
        confidence: float,
        grounding: float,
        hallucination: float,
        validation_ok: bool,
    ) -> None:
        CLAUDE_LATENCY.labels(model="claude", operation=category).observe(
            duration_ms / 1000
        )
        LLM_TOKEN_USAGE.labels(model="claude", token_type="input").inc(tokens_in)
        LLM_TOKEN_USAGE.labels(model="claude", token_type="output").inc(tokens_out)
        CONFIDENCE_DISTRIBUTION.observe(confidence)
        CONFIDENCE_BREAKDOWN.labels(factor="grounding").observe(grounding)
        CONFIDENCE_BREAKDOWN.labels(factor="hallucination_inverted").observe(
            1.0 - hallucination
        )
        HALLUCINATION_RISK_SCORE.observe(hallucination)
        if not validation_ok:
            OUTPUT_VALIDATION_FAILURES.labels(reason=category).inc()

    def record_hallucination_detected(self, severity: str, count: int = 1) -> None:
        HALLUCINATION_DETECTED.labels(severity=severity).inc(count)

    def record_recommendation_quality(
        self, accepted: bool, confidence: float
    ) -> None:
        tag = "accepted" if accepted else "rejected"
        CONFIDENCE_BREAKDOWN.labels(factor=f"recommendation_{tag}").observe(confidence)

    def record_semantic_fit(self, score: float) -> None:
        CONFIDENCE_BREAKDOWN.labels(factor="semantic_fit").observe(score)


_metrics: Optional[IntelligenceMetrics] = None


def get_intelligence_metrics() -> IntelligenceMetrics:
    global _metrics
    if _metrics is None: _metrics = IntelligenceMetrics()
    return _metrics


def __getattr__(name: str):
    if name == "intelligence_metrics":
        return get_intelligence_metrics()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
