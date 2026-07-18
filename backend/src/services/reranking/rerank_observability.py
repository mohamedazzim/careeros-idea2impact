"""
Reranking calibration and observability.

Tracks confidence distributions, rank stability, and
quality indicators for production reranking monitoring.

Stateless, async-safe, observable.
"""
import logging
from typing import List, Optional

from src.schemas.retrieval import RerankedChunk, RerankingObservation
from src.observability.metrics import (
    RERANK_CONFIDENCE,
    RERANK_SCORE_DISTRIBUTION,
    RERANK_RANK_INVERSION,
)

logger = logging.getLogger(__name__)


class RerankObservability:
    """Observability layer for reranking quality monitoring."""

    async def observe(
        self,
        chunks: List[RerankedChunk],
        original_order_ids: Optional[List[str]] = None,
    ) -> RerankingObservation:
        """Generate ranking quality metrics."""
        if not chunks:
            return RerankingObservation(
                rerank_latency_ms=0,
                rerank_confidence_avg=0,
                rank_correlation=0,
                rank_inversion_rate=0,
            )

        scores = [c.rerank_score for c in chunks]
        for s in scores:
            RERANK_CONFIDENCE.observe(s)
            RERANK_SCORE_DISTRIBUTION.observe(s)

        confidence_avg = sum(scores) / len(scores) if scores else 0

        score_bins = {
            "low": sum(1 for s in scores if s < 0.3),
            "medium": sum(1 for s in scores if 0.3 <= s < 0.7),
            "high": sum(1 for s in scores if s >= 0.7),
        }

        n = len(chunks)
        inversions = 0
        if original_order_ids:
            orig_rank_map = {cid: i for i, cid in enumerate(original_order_ids)}
            for i, chunk in enumerate(chunks):
                if chunk.id in orig_rank_map:
                    if abs(i - orig_rank_map[chunk.id]) > max(n * 0.2, 2):
                        inversions += 1

        rank_correlation = (
            1.0 - (6 * inversions) / (n * (n * n - 1)) if n > 1 else 0
        )
        inversion_rate = inversions / max(n, 1)

        RERANK_RANK_INVERSION.observe(inversion_rate)

        return RerankingObservation(
            rerank_latency_ms=0,
            rerank_confidence_avg=round(confidence_avg, 4),
            score_distribution={
                k: round(v / max(n, 1), 3) if v > 0 else 0
                for k, v in score_bins.items()
            },
            rank_correlation=round(rank_correlation, 4),
            rank_inversion_rate=round(inversion_rate, 4),
        )
