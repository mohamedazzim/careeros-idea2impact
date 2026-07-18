"""
Score fusion service for combining retrieval and reranking signals.

Fuses dense similarity, BM25 lexical, section priority, and
cross-encoder rerank scores into a unified confidence metric.

Stateless, async-safe, observable.
"""
from typing import Dict, Optional


class ScoreFusionService:
    """Score fusion across retrieval and reranking signals."""

    DEFAULT_WEIGHTS = {"dense": 0.3, "sparse": 0.2, "rerank": 0.5}

    def fuse(
        self,
        dense_score: float,
        sparse_score: float,
        rerank_score: float,
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Fuse dense, sparse, and rerank scores into unified confidence."""
        w = weights or self.DEFAULT_WEIGHTS
        return round(
            dense_score * w.get("dense", 0.3)
            + sparse_score * w.get("sparse", 0.2)
            + rerank_score * w.get("rerank", 0.5),
            6,
        )

    def weighted_ensemble(
        self,
        scores: Dict[str, float],
        weights: Dict[str, float],
    ) -> float:
        """Generic weighted ensemble of score sources."""
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0
        normalized = {k: v / total_weight for k, v in weights.items()}
        return round(sum(scores.get(k, 0) * w for k, w in normalized.items()), 6)
