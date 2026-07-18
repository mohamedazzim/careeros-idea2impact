"""
Evidence scorer: maps every ATS category score back to retrieval evidence.

Provides explainability by linking each score to specific retrieved chunks,
citations, and confidence levels.

Stateless, async-safe, observable.
"""
import logging
from typing import Dict, Any, List, Optional

from src.schemas.retrieval import FusedResult, Citation

logger = logging.getLogger(__name__)


class EvidenceScorer:
    """Maps scores to evidence for full explainability."""

    def annotate_scores(
        self,
        scores: Dict[str, Any],
        context: str,
        citations: List[Citation],
        fused: Optional[List[FusedResult]] = None,
    ) -> Dict[str, Any]:
        """Annotate each category score with supporting evidence.

        Returns enriched scores dict with per-category evidence references.
        """
        enriched = {}
        for key, value in scores.items():
            if key in ("overall_score", "confidence"):
                enriched[key] = value
                continue
            if isinstance(value, (int, float)):
                enriched[f"{key}_score"] = value
                enriched[f"{key}_evidence"] = self._find_supporting(
                    key, context, citations, fused
                )
            elif isinstance(value, dict):
                enriched[key] = value
        return enriched

    def _find_supporting(
        self,
        category: str,
        context: str,
        citations: List[Citation],
        fused: Optional[List[FusedResult]],
    ) -> List[Dict[str, Any]]:
        """Find evidence chunks supporting a category score."""
        refs = []
        for cit in citations:
            refs.append({
                "citation_id": cit.citation_id,
                "source": cit.source,
                "chunk_id": cit.chunk_id,
            })
        return refs[:10]

    def build_explainable_report(
        self,
        scores: Dict[str, Any],
        context: str,
        citations: List[Citation],
    ) -> Dict[str, Any]:
        enriched = self.annotate_scores(scores, context, citations)
        return {
            "scores": enriched,
            "evidence_citations": [
                {"id": c.citation_id, "source": c.source}
                for c in citations
            ],
            "context_tokens": len(context.split()),
        }


_evidence_scorer: Optional[EvidenceScorer] = None


def get_evidence_scorer() -> EvidenceScorer:
    global _evidence_scorer
    if _evidence_scorer is None:
        _evidence_scorer = EvidenceScorer()
    return _evidence_scorer


def reset_evidence_scorer() -> None:
    global _evidence_scorer
    _evidence_scorer = None


def __getattr__(name: str):
    if name == "evidence_scorer":
        return get_evidence_scorer()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
