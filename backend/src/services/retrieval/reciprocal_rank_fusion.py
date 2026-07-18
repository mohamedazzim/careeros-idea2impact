"""
Reciprocal Rank Fusion (RRF) for hybrid retrieval.

Combines dense, sparse, and metadata-based rankings into a single fused result set.
RRF score = Σ (1 / (k + rank_i)) across all ranking sources.

Preserves recall, prevents semantic or sparse domination, normalizes scores.

Stateless, async-safe, observable.
"""
import logging
import time
from typing import List, Dict, Any, Optional

from src.schemas.retrieval import (
    RetrievedChunk,
    SparseRetrievalResult,
    FusedResult,
    FusionMethod,
)
from src.observability.metrics import (
    RRF_FUSION_LATENCY,
    RRF_FUSION_COUNT,
    RRF_K_PARAM,
)

logger = logging.getLogger(__name__)

# Default RRF smoothing parameter
DEFAULT_RRF_K = 60


def _rrf_score(rank: int, k: int = DEFAULT_RRF_K) -> float:
    """Compute RRF score for a given rank and smoothing parameter k."""
    return 1.0 / (k + rank)


def _normalize_scores(
    items: List[Any],
    score_attr: str = "score",
) -> List[float]:
    """Min-max normalize scores to [0, 1] range."""
    if not items:
        return []
    scores = [getattr(item, score_attr, 0.0) for item in items]
    min_s = min(scores) if scores else 0
    max_s = max(scores) if scores else 1
    if max_s == min_s:
        return [0.5] * len(scores) if max_s == 0 else [1.0] * len(scores)
    return [(s - min_s) / (max_s - min_s) for s in scores]


async def fuse_rrf(
    dense_results: List[RetrievedChunk],
    sparse_results: List[SparseRetrievalResult],
    metadata_results: Optional[List[RetrievedChunk]] = None,
    k: int = DEFAULT_RRF_K,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.4,
    metadata_weight: float = 0.1,
) -> List[FusedResult]:
    """
    Fuse dense, sparse, and metadata rankings using Reciprocal Rank Fusion.

    Args:
        dense_results: Dense vector search results (ranked by cosine similarity)
        sparse_results: BM25 sparse search results (ranked by BM25 score)
        metadata_results: Optional metadata-filtered results
        k: RRF smoothing parameter (default 60)
        dense_weight: Weight multiplier for dense ranking contribution
        sparse_weight: Weight multiplier for sparse ranking contribution
        metadata_weight: Weight multiplier for metadata ranking contribution

    Returns:
        Fused results sorted by combined RRF score
    """
    start = time.monotonic()

    RRF_FUSION_COUNT.inc()
    RRF_K_PARAM.observe(k)

    metadata_results = metadata_results or []

    # Build chunk_id → RRF accumulator
    rrf_scores: Dict[str, float] = {}
    rrf_details: Dict[str, Dict[str, Any]] = {}

    # ── Dense contributions ─────────────────────────────────────────
    for rank, chunk in enumerate(dense_results, start=1):
        chunk_id = chunk.id
        rrf = _rrf_score(rank, k) * dense_weight
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + rrf
        rrf_details[chunk_id] = {
            "dense_rank": rank,
            "dense_score": chunk.score,
            "text": chunk.text,
            "source": chunk.source,
            "metadata": chunk.metadata,
        }

    # ── Sparse contributions ────────────────────────────────────────
    for rank, result in enumerate(sparse_results, start=1):
        chunk_id = result.chunk_id
        rrf = _rrf_score(rank, k) * sparse_weight
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + rrf
        existing = rrf_details.get(chunk_id, {})
        existing.update({
            "sparse_rank": rank,
            "sparse_score": result.score,
        })
        if "text" not in existing:
            existing["text"] = result.text
            existing["source"] = result.source
        rrf_details[chunk_id] = existing

    # ── Metadata contributions ──────────────────────────────────────
    for rank, chunk in enumerate(metadata_results, start=1):
        chunk_id = chunk.id
        rrf = _rrf_score(rank, k) * metadata_weight
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + rrf
        existing = rrf_details.get(chunk_id, {})
        existing["metadata_rank"] = rank
        existing["metadata_score"] = chunk.score
        rrf_details[chunk_id] = existing

    # ── Build fused results ─────────────────────────────────────────
    fused = []
    for chunk_id, rrf_score in sorted(
        rrf_scores.items(), key=lambda x: x[1], reverse=True
    ):
        details = rrf_details.get(chunk_id, {})
        fused.append(
            FusedResult(
                chunk_id=chunk_id,
                text=details.get("text", ""),
                rrf_score=round(rrf_score, 6),
                dense_rank=details.get("dense_rank"),
                dense_score=details.get("dense_score"),
                sparse_rank=details.get("sparse_rank"),
                sparse_score=details.get("sparse_score"),
                metadata_rank=details.get("metadata_rank"),
                metadata_score=details.get("metadata_score"),
                fusion_method=FusionMethod.RRF.value,
                source=details.get("source"),
                metadata=details.get("metadata", {}),
            )
        )

    elapsed = (time.monotonic() - start) * 1000
    RRF_FUSION_LATENCY.observe(elapsed / 1000)

    logger.debug(
        f"RRF fused {len(fused)} unique chunks from "
        f"dense({len(dense_results)}) + sparse({len(sparse_results)})"
        f"+ metadata({len(metadata_results)}) in {elapsed:.1f}ms"
    )

    return fused


async def fuse_weighted_sum(
    dense_results: List[RetrievedChunk],
    sparse_results: List[SparseRetrievalResult],
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
    top_k: int = 50,
) -> List[FusedResult]:
    """
    Fuse using weighted sum of normalized scores.
    Alternative to RRF for score-based combination.
    """
    start = time.monotonic()

    dense_norm = _normalize_scores(dense_results, "score")
    sparse_norm = _normalize_scores(sparse_results, "score")

    fusion_map: Dict[str, Dict[str, Any]] = {}

    for i, chunk in enumerate(dense_results):
        chunk_id = chunk.id
        norm_score = dense_norm[i] * dense_weight if i < len(dense_norm) else 0.0
        fusion_map[chunk_id] = {
            "rrf_score": norm_score,
            "dense_rank": i + 1,
            "dense_score": chunk.score,
            "text": chunk.text,
            "source": chunk.source,
            "metadata": chunk.metadata,
            "fusion_method": FusionMethod.WEIGHTED_SUM.value,
        }

    for i, result in enumerate(sparse_results):
        chunk_id = result.chunk_id
        norm_score = sparse_norm[i] * sparse_weight if i < len(sparse_norm) else 0.0
        if chunk_id in fusion_map:
            fusion_map[chunk_id]["rrf_score"] += norm_score
            fusion_map[chunk_id]["sparse_rank"] = i + 1
            fusion_map[chunk_id]["sparse_score"] = result.score
        else:
            fusion_map[chunk_id] = {
                "rrf_score": norm_score,
                "sparse_rank": i + 1,
                "sparse_score": result.score,
                "text": result.text,
                "source": result.source,
                "metadata": result.metadata,
                "fusion_method": FusionMethod.WEIGHTED_SUM.value,
            }

    fused = [
        FusedResult(
            chunk_id=cid,
            text=info.get("text", ""),
            rrf_score=round(info["rrf_score"], 6),
            dense_rank=info.get("dense_rank"),
            dense_score=info.get("dense_score"),
            sparse_rank=info.get("sparse_rank"),
            sparse_score=info.get("sparse_score"),
            fusion_method=info.get("fusion_method", FusionMethod.WEIGHTED_SUM.value),
            source=info.get("source"),
            metadata=info.get("metadata", {}),
        )
        for cid, info in sorted(
            fusion_map.items(), key=lambda x: x[1]["rrf_score"], reverse=True
        )[:top_k]
    ]

    elapsed = (time.monotonic() - start) * 1000
    RRF_FUSION_LATENCY.observe(elapsed / 1000)
    RRF_FUSION_COUNT.inc()

    return fused
