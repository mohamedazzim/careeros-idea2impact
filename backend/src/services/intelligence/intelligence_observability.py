"""
Intelligence observability: track Claude metrics, prompt metrics, and governance data.

Centralized observability for the Claude intelligence layer.
Emits all Phase 4A metrics and provides runtime aggregation.

Stateless, async-safe, observable. Worker-safe.
"""
import logging
from typing import Dict, Any, Optional

from src.observability.metrics import (
    CLAUDE_CALLS,
    CLAUDE_LATENCY,
    CLAUDE_COST_ESTIMATE,
    LLM_TOKEN_USAGE,
    LLM_LATENCY_HIST,
    PROMPT_VERSION_CALLS,
    GROUNDING_SCORE,
    HALLUCINATION_RISK_SCORE,
    CONFIDENCE_DISTRIBUTION,
    CONFIDENCE_BREAKDOWN,
)

logger = logging.getLogger(__name__)


class IntelligenceObservability:
    """Centralized observability for Claude intelligence layer."""

    def record_claude_call(
        self,
        model: str,
        status: str,
        latency_ms: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        CLAUDE_CALLS.labels(model=model, status=status).inc()
        CLAUDE_LATENCY.labels(model=model, operation="reason").observe(
            latency_ms / 1000
        )
        if cost_usd > 0:
            CLAUDE_COST_ESTIMATE.observe(cost_usd)
        if tokens_in > 0:
            LLM_TOKEN_USAGE.labels(model=model, token_type="input").inc(tokens_in)
        if tokens_out > 0:
            LLM_TOKEN_USAGE.labels(model=model, token_type="output").inc(tokens_out)
        LLM_LATENCY_HIST.labels(model=model, operation="reason").observe(
            latency_ms / 1000
        )

    def record_prompt_usage(self, prompt_id: str, version: str) -> None:
        PROMPT_VERSION_CALLS.labels(prompt_id=prompt_id, version=version).inc()

    def record_grounding(self, score: float) -> None:
        GROUNDING_SCORE.observe(score)

    def record_hallucination(self, score: float) -> None:
        HALLUCINATION_RISK_SCORE.observe(score)

    def record_confidence(
        self, overall: float, breakdown: Optional[Dict[str, float]] = None
    ) -> None:
        CONFIDENCE_DISTRIBUTION.observe(overall)
        if breakdown:
            for factor, value in breakdown.items():
                CONFIDENCE_BREAKDOWN.labels(factor=factor).observe(value)

    def build_response_metadata(
        self,
        claude_result: Dict[str, Any],
        grounding_score: float = 0.0,
        hallucination_score: float = 0.0,
        confidence: float = 0.0,
        validation_passed: bool = True,
    ) -> Dict[str, Any]:
        tokens = claude_result.get("tokens", {})
        return {
            "prompt_version": "1.0.0",
            "model": claude_result.get("model", "claude-sonnet-4-20250514"),
            "grounding_score": round(grounding_score, 4),
            "hallucination_score": round(hallucination_score, 4),
            "confidence_overall": round(confidence, 4),
            "prompt_tokens": tokens.get("input", 0),
            "completion_tokens": tokens.get("output", 0),
            "estimated_cost_usd": claude_result.get("cost", 0.0),
            "total_latency_ms": claude_result.get("latency_ms", 0.0),
            "validation_passed": validation_passed,
        }


_obs: Optional[IntelligenceObservability] = None


def get_intelligence_observability() -> IntelligenceObservability:
    global _obs
    if _obs is None:
        _obs = IntelligenceObservability()
    return _obs


def reset_intelligence_observability() -> None:
    global _obs
    _obs = None


def __getattr__(name: str):
    if name == "intelligence_observability":
        return get_intelligence_observability()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
