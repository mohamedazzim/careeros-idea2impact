"""
Multi-factor confidence engine for Claude intelligence outputs.

Scores overall confidence by combining retrieval quality, rerank quality,
citation coverage, evidence density, hallucination risk inversion,
output validation score, and retrieval drift signals.

Stateless, async-safe, observable. Worker-safe.
"""
import logging
from typing import Dict, Any, Optional, List

from src.schemas.intelligence import ConfidenceBreakdown
from src.schemas.retrieval import FusedResult, Citation
from src.observability.metrics import (
    CONFIDENCE_DISTRIBUTION,
    CONFIDENCE_BREAKDOWN,
)

logger = logging.getLogger(__name__)

# Factor weights for overall confidence
DEFAULT_WEIGHTS = {
    "retrieval_quality": 0.18,
    "rerank_quality": 0.12,
    "citation_coverage": 0.18,
    "evidence_density": 0.12,
    "evidence_consistency": 0.08,
    "contradiction_penalty": 0.10,
    "context_overlap_quality": 0.04,
    "hallucination_risk_inverted": 0.10,
    "output_validation_score": 0.04,
    "retrieval_drift_inverted": 0.04,
}


class ConfidenceEngine:
    """Multi-factor confidence scoring for Claude responses."""

    def score(
        self,
        retrieval_metrics: Optional[Dict[str, Any]] = None,
        fused_results: Optional[List[FusedResult]] = None,
        citations: Optional[List[Citation]] = None,
        context: str = "",
        hallucination_score: float = 0.0,
        validation_score: float = 1.0,
        drift_status: Optional[Dict[str, Any]] = None,
        contradiction_report: Optional[Dict[str, Any]] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> ConfidenceBreakdown:
        """Compute multi-factor confidence breakdown.

        Returns per-factor scores and weighted overall confidence.
        """
        w = weights or DEFAULT_WEIGHTS
        rm = retrieval_metrics or {}

        # 1. Retrieval quality factor (from hybrid retrieval metrics)
        retrieval_quality = self._factor_retrieval(rm, fused_results)

        # 2. Rerank quality factor
        rerank_quality = self._factor_rerank(rm, fused_results)

        # 3. Citation coverage factor
        citation_coverage = self._factor_citation_coverage(
            citations, fused_results, context
        )

        # 4. Evidence density factor
        evidence_density = self._factor_evidence_density(context, fused_results)

        # 5. Evidence consistency factor — checks for contradictions
        evidence_consistency = self._factor_evidence_consistency(
            fused_results, contradiction_report
        )

        # 6. Contradiction penalty factor
        contradiction_penalty = self._factor_contradiction(contradiction_report)

        # 7. Context overlap quality
        context_overlap = self._factor_overlap_quality(fused_results)

        # 8. Hallucination risk inverted
        hallucination_inverted = max(0.0, 1.0 - hallucination_score)

        # 9. Output validation score
        output_validation = min(1.0, max(0.0, validation_score))

        # 10. Retrieval drift inverted
        drift_inverted = self._factor_drift(drift_status)

        overall = (
            retrieval_quality * w["retrieval_quality"]
            + rerank_quality * w["rerank_quality"]
            + citation_coverage * w["citation_coverage"]
            + evidence_density * w["evidence_density"]
            + evidence_consistency * w["evidence_consistency"]
            + contradiction_penalty * w["contradiction_penalty"]
            + context_overlap * w["context_overlap_quality"]
            + hallucination_inverted * w["hallucination_risk_inverted"]
            + output_validation * w["output_validation_score"]
            + drift_inverted * w["retrieval_drift_inverted"]
        )

        overall = round(min(1.0, max(0.0, overall)), 4)

        CONFIDENCE_DISTRIBUTION.observe(overall)
        for factor_name, value in [
            ("retrieval_quality", retrieval_quality),
            ("rerank_quality", rerank_quality),
            ("citation_coverage", citation_coverage),
            ("evidence_density", evidence_density),
            ("evidence_consistency", evidence_consistency),
            ("contradiction_penalty", contradiction_penalty),
            ("overlap_quality", context_overlap),
            ("hallucination_inverted", hallucination_inverted),
            ("validation", output_validation),
            ("drift_inverted", drift_inverted),
        ]:
            CONFIDENCE_BREAKDOWN.labels(factor=factor_name).observe(value)

        return ConfidenceBreakdown(
            retrieval_quality=round(retrieval_quality, 4),
            rerank_quality=round(rerank_quality, 4),
            citation_coverage=round(citation_coverage, 4),
            evidence_density=round(evidence_density, 4),
            context_overlap_quality=round(context_overlap, 4),
            hallucination_risk_inverted=round(hallucination_inverted, 4),
            output_validation_score=round(output_validation, 4),
            retrieval_drift_inverted=round(drift_inverted, 4),
            overall=overall,
        )

    def _factor_retrieval(self, rm: Dict, fused: Optional[List]) -> float:
        recall = rm.get("recall_gain", 0.5)
        return min(1.0, max(0.1, recall * 1.5)) if fused else 0.5

    def _factor_rerank(self, rm: Dict, fused: Optional[List]) -> float:
        if fused and len(fused) > 0:
            scores = [f.rrf_score for f in fused]
            avg = sum(scores) / len(scores)
            return min(1.0, max(0.1, avg))
        return 0.5

    def _factor_citation_coverage(
        self, citations: Optional[List], fused: Optional[List], context: str
    ) -> float:
        if not fused or not citations:
            return 0.3
        coverage = len(citations) / max(len(fused), 1)
        return min(1.0, max(0.1, coverage))

    def _factor_evidence_density(
        self, context: str, fused: Optional[List]
    ) -> float:
        if not context or not fused:
            return 0.2
        density = len(context.split()) / max(len(fused), 1)
        return min(1.0, max(0.1, density / 500))

    def _factor_overlap_quality(self, fused: Optional[List]) -> float:
        if not fused or len(fused) < 2:
            return 1.0
        return 0.9

    def _factor_drift(self, drift: Optional[Dict]) -> float:
        if not drift:
            return 1.0
        detected = drift.get("drift_detected", False)
        return 0.6 if detected else 1.0

    def _factor_evidence_consistency(
        self,
        fused: Optional[List[FusedResult]],
        contradiction_report: Optional[Dict[str, Any]],
    ) -> float:
        """Evidence consistency: checks for contradictions across fusion signals."""
        if not contradiction_report or not fused:
            return 0.7
        con_signal_count = sum(
            len(cat.get("signals", []))
            for cat in contradiction_report.get("contradictions", [])
        )
        return max(0.1, 1.0 - (con_signal_count * 0.12))

    def _factor_contradiction(
        self,
        contradiction_report: Optional[Dict[str, Any]],
    ) -> float:
        """Contradiction penalty: reduces confidence proportionally to detected contradictions."""
        if not contradiction_report:
            return 1.0
        total = contradiction_report.get("total_signals", 0)
        severity = contradiction_report.get("severity", "none")
        severity_penalty = {"none": 0.0, "medium": 0.15, "high": 0.35, "critical": 0.55}
        return max(0.1, 1.0 - severity_penalty.get(severity, 0.0) - (total * 0.03))


_confidence_engine: Optional[ConfidenceEngine] = None


def get_confidence_engine() -> ConfidenceEngine:
    global _confidence_engine
    if _confidence_engine is None:
        _confidence_engine = ConfidenceEngine()
    return _confidence_engine


def reset_confidence_engine() -> None:
    global _confidence_engine
    _confidence_engine = None


def __getattr__(name: str):
    if name == "confidence_engine":
        return get_confidence_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
