"""
Federated retrieval hardening layer.

Cross-collection duplicate suppression, score normalization,
collection-priority balancing, and latency optimization.

Stateless, async-safe, observable. Worker-safe.
"""
import hashlib
import logging
from typing import List, Dict, Optional

from src.schemas.retrieval import (
    FusedResult,
    RoutingDecision,
)
from src.core.config import settings
from src.observability.metrics import (
    FEDERATION_DEDUP_REMOVED,
)

logger = logging.getLogger(__name__)


class FederatedResultMerger:
    """Merges and normalizes results from multiple collections."""

    def merge(
        self,
        collection_results: Dict[str, List[FusedResult]],
        routing: RoutingDecision,
        result_limit: Optional[int] = None,
    ) -> List[FusedResult]:
        """Merge federated results with dedup and score normalization.

        Args:
            collection_results: {collection_name: [FusedResult]}
            routing: RoutingDecision with collection weights
            result_limit: Max results to return (from config)

        Returns:
            Merged, deduplicated, normalized results sorted by adjusted score
        """
        if not collection_results:
            return []

        limit = result_limit or settings.FEDERATION_RESULT_LIMIT

        # 1. Cross-collection deduplication
        merged = []
        if settings.FEDERATION_DEDUP_ENABLED:
            merged = self._deduplicate_across_collections(collection_results)
        else:
            for coll, results in collection_results.items():
                for r in results:
                    merged.append(r)

        # 2. Score normalization per collection
        if settings.FEDERATION_SCORE_NORMALIZE:
            merged = self._normalize_scores(merged, routing)

        # 3. Apply collection priority weights
        merged = self._apply_weights(merged, routing)

        # 4. Sort by adjusted score
        merged.sort(key=lambda x: x.rrf_score, reverse=True)

        return merged[:limit]

    def _deduplicate_across_collections(
        self,
        collection_results: Dict[str, List[FusedResult]],
    ) -> List[FusedResult]:
        """Deduplicate chunks that appear in multiple collections.

        Content-hash dedup: keep the highest-scoring instance across
        collections, track which collections it was found in.
        """
        seen: Dict[str, FusedResult] = {}

        for coll, results in collection_results.items():
            for result in results:
                content_hash = hashlib.sha256(
                    result.text.strip().lower().encode("utf-8", errors="ignore")
                ).hexdigest()

                if content_hash in seen:
                    existing = seen[content_hash]
                    if result.rrf_score > existing.rrf_score:
                        duplicate_meta = {
                            "cross_collection_hit": True,
                            "collections_found": list(
                                set(
                                    existing.metadata.get("collections_found", [coll])
                                    + [coll]
                                )
                            ),
                        }
                        result.metadata.update(duplicate_meta)
                        seen[content_hash] = result
                    continue

                result.metadata["collections_found"] = [coll]
                seen[content_hash] = result

        removed = sum(
            len(results) for results in collection_results.values()
        ) - len(seen)
        FEDERATION_DEDUP_REMOVED.inc(removed)

        return list(seen.values())

    def _normalize_scores(
        self,
        results: List[FusedResult],
        routing: RoutingDecision,
    ) -> List[FusedResult]:
        """Per-collection min-max score normalization.

        Since different collections may have different score distributions,
        normalize within each collection before merging.
        """
        # Group by collection
        by_collection: Dict[str, List[FusedResult]] = {}
        for r in results:
            colls = r.metadata.get("collections_found", ["unknown"])
            for coll in colls:
                by_collection.setdefault(coll, []).append(r)

        # Normalize per collection
        normalized_map: Dict[str, float] = {}
        for coll, items in by_collection.items():
            if not items:
                continue
            scores = [item.rrf_score for item in items]
            min_s = min(scores)
            max_s = max(scores)
            if max_s == min_s:
                norm = [0.5] * len(scores)
            else:
                norm = [(s - min_s) / (max_s - min_s) for s in scores]
            for item, n in zip(items, norm):
                normalized_map[item.chunk_id] = n

        # Apply normalized scores
        for r in results:
            if r.chunk_id in normalized_map:
                r.rrf_score = round(normalized_map[r.chunk_id], 6)

        return results

    def _apply_weights(
        self,
        results: List[FusedResult],
        routing: RoutingDecision,
    ) -> List[FusedResult]:
        """Apply collection priority weights to fused scores."""
        weights = routing.collection_weights

        for r in results:
            colls = r.metadata.get("collections_found", ["careeros_resumes"])
            weight = max(
                weights.get(coll, 1.0 / max(len(weights), 1))
                for coll in colls
            )
            r.rrf_score = round(r.rrf_score * weight, 6)

        return results


_federated_merger: Optional[FederatedResultMerger] = None


def get_federated_merger() -> FederatedResultMerger:
    global _federated_merger
    if _federated_merger is None:
        _federated_merger = FederatedResultMerger()
    return _federated_merger


def reset_federated_merger() -> None:
    global _federated_merger
    _federated_merger = None


def __getattr__(name: str):
    if name == "federated_merger":
        return get_federated_merger()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
