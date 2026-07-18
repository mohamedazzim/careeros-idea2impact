"""
Evaluation benchmark worker task.

Runs retrieval benchmark regression in the ARQ worker and persists the
final benchmark state back to PostgreSQL.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.db.session import async_session
from src.db.repositories.domain_repositories import EvaluationRunRepository

logger = logging.getLogger(__name__)


def _metric_from_eval_result(eval_result: Dict[str, Any]) -> Dict[str, Any]:
    metrics = eval_result.get("metrics", {}) if isinstance(eval_result, dict) else {}
    return {
        "recall_at_k": metrics.get("recall_at_k", {}),
        "hit_at_k": metrics.get("hit_at_k", {}),
        "precision_at_k": metrics.get("precision_at_k", {}),
        "mrr": metrics.get("mrr", 0.0),
        "ndcg_at_k": metrics.get("ndcg_at_k", {}),
        "retrieval_consistency": metrics.get("retrieval_consistency", 0.0),
        "hallucination_risk": metrics.get("hallucination_risk", 0.0),
        "retrieval_drift": metrics.get("retrieval_drift", 0.0),
        "dense_only_metrics": eval_result.get("dense_only_metrics", {}),
        "hybrid_metrics": eval_result.get("hybrid_metrics", {}),
        "hybrid_recall_gain": eval_result.get("hybrid_recall_gain", 0.0),
        "latency_breakdown": eval_result.get("latency_breakdown", {}),
    }


async def run_evaluation_benchmark_task(
    ctx: Dict[str, Any],
    run_uid: str,
    user_id: Optional[str] = None,
    benchmark_name: str = "retrieval_evaluation",
    config: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    config = config or {}
    logger.info(
        "Starting evaluation benchmark task",
        extra={
            "run_uid": run_uid,
            "user_id": user_id,
            "benchmark_name": benchmark_name,
        },
    )

    async with async_session() as db:
        repo = EvaluationRunRepository(db)
        run = await repo.get_by_uid(run_uid)
        if not run:
            logger.error("Evaluation run %s not found", run_uid)
            return {"status": "not_found", "run_uid": run_uid}

        await repo.update(
            run.id,
            status="in_progress",
            progress_pct=5.0,
            updated_by=user_id,
            trace_id=run_uid,
            metrics={
                "benchmark_name": benchmark_name,
                "stage": "starting",
            },
            results={},
        )

        from src.services.retrieval.retrieval_drift_monitor import get_drift_monitor
        from src.services.retrieval.retrieval_evaluation_service import get_retrieval_evaluation_service
        from src.services.retrieval.hybrid_retrieval_service import get_hybrid_retrieval_service

        monitor = get_drift_monitor()
        evaluation_service = get_retrieval_evaluation_service()
        retrieval_service = get_hybrid_retrieval_service()
        golden_queries = list(monitor._load_golden_queries())  # intentional: persisted benchmark set
        if not golden_queries:
            golden_queries = [{"query": "CareerOS benchmark", "relevant_ids": []}]

        top_k = int(config.get("top_k", 10) or 10)
        query_limit = int(config.get("query_limit", len(golden_queries)) or len(golden_queries))
        golden_queries = golden_queries[: max(query_limit, 1)]

        per_query_results: List[Dict[str, Any]] = []
        aggregate: Dict[str, List[float]] = {
            "recall_at_10": [],
            "recall_at_5": [],
            "mrr": [],
            "ndcg_at_10": [],
            "precision_at_10": [],
            "consistency": [],
            "latency_ms": [],
        }
        errors: List[str] = []

        async def _retrieve(query: str):
            result = await retrieval_service.retrieve(
                query=query,
                collection=config.get("collection", "careeros_resumes"),
                top_k=top_k,
                top_n=min(10, top_k),
                use_hybrid=True,
                use_sparse=True,
                use_reranker=True,
            )
            return result.reranked_chunks or result.dense_results

        total = len(golden_queries)
        for index, gq in enumerate(golden_queries, start=1):
            query = gq.get("query", "")
            relevant_ids = gq.get("relevant_ids", []) or []
            try:
                retrieved = await _retrieve(query)
                eval_result = evaluation_service.evaluate(
                    query=query,
                    results=retrieved,
                    relevant_ids=relevant_ids,
                    metric_ks=[1, 3, 5, 10],
                )
                await monitor.record_retrieval_metrics(eval_result)
                eval_payload = eval_result.model_dump()
                metrics = eval_payload["metrics"]
                aggregate["recall_at_10"].append(metrics.get("recall_at_k", {}).get(10, 0.0))
                aggregate["recall_at_5"].append(metrics.get("recall_at_k", {}).get(5, 0.0))
                aggregate["mrr"].append(metrics.get("mrr", 0.0))
                aggregate["ndcg_at_10"].append(metrics.get("ndcg_at_k", {}).get(10, 0.0))
                aggregate["precision_at_10"].append(metrics.get("precision_at_k", {}).get(10, 0.0))
                aggregate["consistency"].append(metrics.get("retrieval_consistency", 0.0))
                aggregate["latency_ms"].append(eval_payload.get("latency_breakdown", {}).get("total_latency_ms", 0.0))
                per_query_results.append(
                    {
                        "query": query,
                        "relevant_ids": relevant_ids,
                        "retrieved_count": len(retrieved),
                        "metrics": eval_payload,
                    }
                )
                logger.info(
                    "Evaluation query complete",
                    extra={
                        "run_uid": run_uid,
                        "query_index": index,
                        "query_total": total,
                        "retrieved_count": len(retrieved),
                        "recall_at_10": metrics.get("recall_at_k", {}).get(10, 0.0),
                    },
                )
            except Exception as exc:
                error_msg = f"{query[:80]}: {exc}"
                logger.exception("Evaluation query failed")
                errors.append(error_msg)
                per_query_results.append(
                    {
                        "query": query,
                        "relevant_ids": relevant_ids,
                        "status": "failed",
                        "error": str(exc),
                    }
                )
            progress = 5.0 + (index / max(total, 1)) * 85.0
            await repo.update(
                run.id,
                progress_pct=min(progress, 95.0),
                updated_by=user_id,
                metrics={
                    "benchmark_name": benchmark_name,
                    "stage": "running",
                    "queries_completed": index,
                    "queries_total": total,
                },
                results={
                    "queries": per_query_results,
                },
                errors=errors or None,
            )

        n = len(aggregate["recall_at_10"]) or 1
        summary = {
            "benchmark_name": benchmark_name,
            "queries_evaluated": len(per_query_results),
            "recall@10_avg": round(sum(aggregate["recall_at_10"]) / n, 4),
            "recall@5_avg": round(sum(aggregate["recall_at_5"]) / n, 4),
            "mrr_avg": round(sum(aggregate["mrr"]) / n, 4),
            "ndcg@10_avg": round(sum(aggregate["ndcg_at_10"]) / n, 4),
            "precision@10_avg": round(sum(aggregate["precision_at_10"]) / n, 4),
            "consistency_avg": round(sum(aggregate["consistency"]) / n, 4),
            "latency_ms_avg": round(sum(aggregate["latency_ms"]) / n, 4),
            "error_count": len(errors),
        }

        await repo.update(
            run.id,
            status="completed" if not errors or len(errors) < len(per_query_results) else "failed",
            progress_pct=100.0,
            metrics=summary,
            results={
                "queries": per_query_results,
                "summary": summary,
            },
            errors=errors or None,
            completed_at=datetime.utcnow(),
            updated_by=user_id,
        )

        logger.info(
            "Evaluation benchmark finished",
            extra={
                "run_uid": run_uid,
                "status": "completed" if not errors or len(errors) < len(per_query_results) else "failed",
                "queries_evaluated": len(per_query_results),
                "error_count": len(errors),
            },
        )

        return {
            "run_uid": run_uid,
            "status": "completed" if not errors or len(errors) < len(per_query_results) else "failed",
            "summary": summary,
        }
