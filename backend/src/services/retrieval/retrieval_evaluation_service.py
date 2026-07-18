"""
Production-grade retrieval evaluation service.

Implements enterprise retrieval metrics:
- Recall@K, Hit@K, Precision@K
- MRR (Mean Reciprocal Rank)
- NDCG@K (Normalized Discounted Cumulative Gain)
- Retrieval consistency scoring
- Hallucination risk estimation
- Retrieval drift detection
- Benchmark dataset management

Stateless, async-safe, observable. Worker-safe.
"""
import logging
import math
from typing import List, Dict, Any, Optional, Set

from src.schemas.retrieval import (
    RetrievedChunk,
    FusedResult,
    RetrievalMetrics,
    EvaluationResult,
)
from src.observability.metrics import (
    RETRIEVAL_RECALL,
    RETRIEVAL_PRECISION,
    RETRIEVAL_MRR,
    RETRIEVAL_NDCG,
    RETRIEVAL_CONSISTENCY,
    HALLUCINATION_RISK,
)

logger = logging.getLogger(__name__)


class RetrievalEvaluationService:
    """Enterprise-grade retrieval evaluation with standard IR metrics."""

    def evaluate(
        self,
        query: str,
        results: List[RetrievedChunk],
        relevant_ids: List[str],
        metric_ks: List[int] = [1, 3, 5, 10],
        dense_only_results: Optional[List[RetrievedChunk]] = None,
    ) -> EvaluationResult:
        """Compute full suite of retrieval metrics.

        Args:
            query: Original search query
            results: Retrieved chunks (any type)
            relevant_ids: Ground-truth relevant document/chunk IDs
            metric_ks: K values for Recall@K, Precision@K, NDCG@K
            dense_only_results: Dense-only results for hybrid vs dense comparison

        Returns:
            EvaluationResult with all metrics
        """
        result_ids = [self._normalize_id(r) for r in results]
        relevant_set = set(relevant_ids)

        metrics = RetrievalMetrics()

        # Recall@K, Hit@K, Precision@K
        for k in metric_ks:
            top_k_ids = result_ids[:k]
            hits = len(set(top_k_ids) & relevant_set)

            recall = hits / max(len(relevant_set), 1)
            precision = hits / max(k, 1)
            hit = 1.0 if hits > 0 else 0.0

            metrics.recall_at_k[k] = round(recall, 4)
            metrics.precision_at_k[k] = round(precision, 4)
            metrics.hit_at_k[k] = round(hit, 4)

            RETRIEVAL_RECALL.labels(k=str(k)).observe(recall)
            RETRIEVAL_PRECISION.labels(k=str(k)).observe(precision)

        # MRR
        mrr = 0.0
        for i, rid in enumerate(result_ids, start=1):
            if rid in relevant_set:
                mrr = 1.0 / i
                break
        metrics.mrr = round(mrr, 4)
        RETRIEVAL_MRR.observe(mrr)

        # NDCG@K
        for k in metric_ks:
            ndcg = self._compute_ndcg(result_ids[:k], relevant_set, k)
            metrics.ndcg_at_k[k] = round(ndcg, 4)
            RETRIEVAL_NDCG.labels(k=str(k)).observe(ndcg)

        # Retrieval consistency (ratio of relevant results in top-K)
        top10_ids = set(result_ids[:10])
        consistency = len(top10_ids & relevant_set) / max(min(10, len(relevant_set)), 1)
        metrics.retrieval_consistency = round(consistency, 4)
        RETRIEVAL_CONSISTENCY.observe(consistency)

        # Hallucination risk: inversely proportional to relevance density
        hallucination_risk = (1.0 - consistency) * 0.8
        metrics.hallucination_risk = round(hallucination_risk, 4)
        HALLUCINATION_RISK.observe(hallucination_risk)

        # Retrieval drift: 0 if first result is relevant, 1 otherwise
        retrieval_drift = 0.0 if result_ids and result_ids[0] in relevant_set else 1.0
        metrics.retrieval_drift = retrieval_drift

        # Dense-only comparison
        dense_metrics: Dict[str, Any] = {}
        hybrid_recall_gain = 0.0

        if dense_only_results:
            dense_ids = [self._normalize_id(r) for r in dense_only_results[:10]]
            dense_recall = len(set(dense_ids) & relevant_set) / max(len(relevant_set), 1)
            hybrid_recall = metrics.recall_at_k.get(10, 0)
            hybrid_recall_gain = hybrid_recall - dense_recall

            dense_metrics = {
                "dense_recall@10": round(dense_recall, 4),
                "hybrid_recall@10": round(hybrid_recall, 4),
                "recall_gain": round(hybrid_recall_gain, 4),
            }

        return EvaluationResult(
            query=query,
            metrics=metrics,
            dense_only_metrics=dense_metrics,
            hybrid_metrics={
                "recall_at_10": metrics.recall_at_k.get(10, 0),
                "mrr": metrics.mrr,
                "consistency": metrics.retrieval_consistency,
            },
            hybrid_recall_gain=round(hybrid_recall_gain, 4),
            latency_breakdown={},
        )

    def evaluate_hybrid(
        self,
        query: str,
        fused_results: List[FusedResult],
        dense_results: List[RetrievedChunk],
        relevant_ids: List[str],
    ) -> EvaluationResult:
        """Evaluate hybrid retrieval against dense-only baseline."""
        # Build RetrievedChunk-like from FusedResult for evaluation
        fused_as_retrieved = [
            RetrievedChunk(
                id=f.chunk_id,
                text=f.text,
                score=f.rrf_score,
                source=f.source,
                metadata=f.metadata,
            )
            for f in fused_results
        ]

        result = self.evaluate(
            query=query,
            results=fused_as_retrieved,
            relevant_ids=relevant_ids,
            dense_only_results=dense_results,
        )

        return result

    def _compute_ndcg(
        self,
        result_ids: List[str],
        relevant_set: Set[str],
        k: int,
    ) -> float:
        """Compute NDCG@K."""
        if not result_ids or not relevant_set:
            return 0.0

        # Binary relevance: 1 if in relevant_set, 0 otherwise
        dcg = 0.0
        for i, rid in enumerate(result_ids, start=1):
            if rid in relevant_set:
                rel = 1.0
                dcg += rel / math.log2(i + 1)

        # IDCG: ideal ordering (all relevant at top)
        idcg = 0.0
        ideal_count = min(k, len(relevant_set))
        for i in range(1, ideal_count + 1):
            idcg += 1.0 / math.log2(i + 1)

        return dcg / max(idcg, 1e-9)

    def _normalize_id(self, result: Any) -> str:
        """Normalize result ID from any result type."""
        if hasattr(result, "chunk_id") and getattr(result, "chunk_id", None):
            return getattr(result, "chunk_id")
        if hasattr(result, "id") and getattr(result, "id", None):
            return str(getattr(result, "id"))
        return str(hash(getattr(result, "text", ""))) if hasattr(result, "text") else "unknown"

    def benchmark(
        self,
        queries: List[str],
        query_relevant_ids: Dict[str, List[str]],
        run_retrieval_fn,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """Run full evaluation benchmark across multiple queries.

        Args:
            queries: List of test queries
            query_relevant_ids: Mapping of query → list of relevant IDs
            run_retrieval_fn: Async function(query, top_k) → List[RetrievedChunk]
            top_k: Number of results to retrieve per query
        """
        if not queries:
            return {"queries_evaluated": 0}

        aggregate = {
            "recall@10": [],
            "recall@5": [],
            "mrr": [],
            "ndcg@10": [],
            "precision@10": [],
            "consistency": [],
        }

        for query in queries:
            try:
                results = run_retrieval_fn(query=query, top_k=top_k)
                relevant = query_relevant_ids.get(query, [])
                eval_result = self.evaluate(
                    query=query,
                    results=results,
                    relevant_ids=relevant,
                    metric_ks=[5, 10],
                )
                aggregate["recall@10"].append(eval_result.metrics.recall_at_k.get(10, 0))
                aggregate["recall@5"].append(eval_result.metrics.recall_at_k.get(5, 0))
                aggregate["mrr"].append(eval_result.metrics.mrr)
                aggregate["ndcg@10"].append(eval_result.metrics.ndcg_at_k.get(10, 0))
                aggregate["precision@10"].append(eval_result.metrics.precision_at_k.get(10, 0))
                aggregate["consistency"].append(eval_result.metrics.retrieval_consistency)
            except Exception as e:
                logger.error(f"Benchmark failed for query '{query[:50]}...': {e}")

        n = len(aggregate["recall@10"]) or 1
        return {
            "queries_evaluated": len(queries),
            "recall@10_avg": round(sum(aggregate["recall@10"]) / n, 4),
            "recall@5_avg": round(sum(aggregate["recall@5"]) / n, 4),
            "mrr_avg": round(sum(aggregate["mrr"]) / n, 4),
            "ndcg@10_avg": round(sum(aggregate["ndcg@10"]) / n, 4),
            "precision@10_avg": round(sum(aggregate["precision@10"]) / n, 4),
            "consistency_avg": round(sum(aggregate["consistency"]) / n, 4),
        }


# Module-level singleton
_retrieval_evaluation_service: Optional[RetrievalEvaluationService] = None


def get_retrieval_evaluation_service() -> RetrievalEvaluationService:
    global _retrieval_evaluation_service
    if _retrieval_evaluation_service is None:
        _retrieval_evaluation_service = RetrievalEvaluationService()
    return _retrieval_evaluation_service


def reset_retrieval_evaluation_service() -> None:
    global _retrieval_evaluation_service
    _retrieval_evaluation_service = None


def __getattr__(name: str):
    if name == "retrieval_evaluation_service":
        return get_retrieval_evaluation_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
