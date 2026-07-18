"""
Retrieval drift monitoring service.

Time-series drift detection, golden-query benchmark regression,
threshold-based alert triggering, and embedding drift preparation.

Stateless, async-safe, observable. Worker-safe.
"""
import json
import logging
import os
import time
from typing import List, Dict, Any, Callable, Optional

from src.core.config import settings
from src.schemas.retrieval import EvaluationResult
from src.observability.metrics import DRIFT_ALERT_TRIGGERED, RETRIEVAL_DRIFT_SCORE, GOLDEN_QUERY_REGRESSION

logger = logging.getLogger(__name__)


class DriftState:
    """Sliding-window drift tracker with baseline comparison."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.baseline: Dict[str, float] = {}
        self.samples: List[Dict[str, float]] = []
        self.alert_count: int = 0

    def set_baseline(self, metrics: Dict[str, float]) -> None:
        self.baseline = dict(metrics)

    def add_sample(self, metrics: Dict[str, float]) -> None:
        self.samples.append(dict(metrics))
        if len(self.samples) > self.window_size:
            self.samples.pop(0)

    def check_drift(self) -> Dict[str, Any]:
        """Check if current window deviates from baseline beyond thresholds."""
        if not self.baseline or not self.samples:
            return {"drift_detected": False, "drifts": {}}

        window_avg: Dict[str, float] = {}
        for sample in self.samples:
            for metric, value in sample.items():
                window_avg[metric] = window_avg.get(metric, 0.0) + value
        for metric in window_avg:
            window_avg[metric] /= len(self.samples)

        thresholds = {
            "recall_at_10": settings.DRIFT_THRESHOLD_RECALL,
            "mrr": settings.DRIFT_THRESHOLD_MRR,
            "consistency": settings.DRIFT_THRESHOLD_CONSISTENCY,
        }

        drifts = {}
        drift_detected = False

        for metric, threshold in thresholds.items():
            baseline_val = self.baseline.get(metric, 0)
            current_val = window_avg.get(metric, 0)
            if baseline_val > 0:
                drop = (baseline_val - current_val) / baseline_val
                if drop > threshold:
                    drifts[metric] = round(drop, 4)
                    drift_detected = True
                    logger.warning(
                        f"DRIFT ALERT: {metric} dropped {drop:.2%} "
                        f"(baseline={baseline_val:.4f}, current={current_val:.4f}, "
                        f"threshold={threshold:.2%})"
                    )

        if drift_detected:
            self.alert_count += 1

        return {
            "drift_detected": drift_detected,
            "drifts": drifts,
            "alert_count": self.alert_count,
            "window_size": len(self.samples),
            "baseline": self.baseline,
            "current_window": window_avg,
        }


class RetrievalDriftMonitor:
    """Production-grade retrieval drift monitoring.

    Tracks retrieval quality drift via golden-query benchmarks
    and time-series metrics comparison against established baselines.
    """

    def __init__(self):
        self._state = DriftState(window_size=settings.DRIFT_CHECK_WINDOW)
        self._golden_queries: List[Dict[str, Any]] = []
        self._golden_loaded = False

    def _load_golden_queries(self) -> List[Dict[str, Any]]:
        """Load golden query set for benchmark regression."""
        if self._golden_loaded and self._golden_queries:
            has_relevant = any(
                len(q.get("relevant_ids", [])) > 0
                for q in self._golden_queries
            )
            if has_relevant:
                return self._golden_queries
            self._golden_loaded = False

        path = settings.GOLDEN_QUERIES_PATH
        if not os.path.isabs(path):
            app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            path = os.path.join(app_root, path)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "queries" in data:
                    self._golden_queries = data["queries"]
                elif isinstance(data, list):
                    self._golden_queries = data
                else:
                    self._golden_queries = [data] if isinstance(data, dict) else []
                logger.info(
                    f"Loaded {len(self._golden_queries)} golden queries from {path}"
                )
            except Exception as e:
                logger.warning(f"Failed to load golden queries: {e}")
        if not self._golden_queries:
            self._golden_queries = self._default_golden_queries()
            logger.info(
                f"Using {len(self._golden_queries)} default golden queries "
                f"(save to {path} to customize)"
            )
        self._golden_loaded = True
        return self._golden_queries

    def _default_golden_queries(self) -> List[Dict[str, Any]]:
        """Default golden query set for baseline regression testing."""
        return [
            {"query": "Senior React engineer with AWS experience", "relevant_ids": []},
            {"query": "Full stack developer TypeScript Node.js PostgreSQL", "relevant_ids": []},
            {"query": "Machine Learning Engineer Python PyTorch", "relevant_ids": []},
            {"query": "DevOps engineer Kubernetes Docker Terraform CI/CD", "relevant_ids": []},
            {"query": "Engineering manager agile team leadership", "relevant_ids": []},
            {"query": "Backend engineer FastAPI microservices", "relevant_ids": []},
            {"query": "Data scientist SQL Python pandas", "relevant_ids": []},
            {"query": "Frontend developer React TypeScript CSS", "relevant_ids": []},
            {"query": "Platform engineer AWS EKS Terraform", "relevant_ids": []},
            {"query": "AI engineer LangGraph LLM RAG", "relevant_ids": []},
        ]

    async def run_benchmark_regression(
        self,
        run_retrieval_fn: Callable,
        evaluation_fn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Run golden query benchmark against current retrieval.

        Args:
            run_retrieval_fn: Async (query, top_k) → List[RetrievedChunk]
            evaluation_fn: Optional custom evaluator

        Returns:
            Benchmark results with per-metric averages and drift status
        """
        golden = self._load_golden_queries()
        if not golden:
            return {"error": "No golden queries available", "queries_run": 0}

        aggregate: Dict[str, List[float]] = {
            "latency_ms": [],
        }
        results: List[Dict[str, Any]] = []

        for gq in golden:
            query = gq["query"]
            relevant_ids = gq.get("relevant_ids", [])
            t0 = time.monotonic()

            try:
                retrieved = await run_retrieval_fn(query=query, top_k=10)
            except Exception as e:
                logger.error(f"Golden query '{query[:50]}...' failed: {e}")
                continue

            elapsed = (time.monotonic() - t0) * 1000
            aggregate["latency_ms"].append(elapsed)

            result_ids = []
            for r in retrieved:
                if hasattr(r, "chunk_id") and r.chunk_id:
                    result_ids.append(r.chunk_id)
                elif hasattr(r, "id"):
                    result_ids.append(str(r.id))

            if relevant_ids:
                hits = len(set(result_ids[:10]) & set(relevant_ids))
                recall = hits / max(len(relevant_ids), 1)
                aggregate.setdefault("recall_at_10", []).append(recall)

            results.append({
                "query": query,
                "result_count": len(result_ids),
                "latency_ms": round(elapsed, 2),
            })

        n = len(results) or 1
        summary = {
            "queries_run": len(results),
            "avg_latency_ms": round(
                sum(aggregate["latency_ms"]) / n, 2
            ),
        }

        for metric in ["recall_at_10"]:
            if metric in aggregate:
                summary[f"avg_{metric}"] = round(
                    sum(aggregate[metric]) / len(aggregate[metric]), 4
                )

        # Update drift state
        drift_sample = {
            "recall_at_10": summary.get("avg_recall_at_10", 0),
            "latency_ms": summary["avg_latency_ms"],
        }
        self._state.add_sample(drift_sample)

        # Set baseline if not established
        if not self._state.baseline:
            self._state.set_baseline(drift_sample)
            logger.info("Drift baseline established from first benchmark run")

        drift = self._state.check_drift()

        return {
            **summary,
            "drift": drift,
            "baseline": self._state.baseline,
        }

    async def record_retrieval_metrics(
        self,
        eval_result: EvaluationResult,
    ) -> Optional[Dict[str, Any]]:
        """Record metrics from a retrieval evaluation for drift tracking."""
        if not settings.DRIFT_CHECK_ENABLED:
            return None

        sample = {
            "recall_at_10": eval_result.metrics.recall_at_k.get(10, 0),
            "mrr": eval_result.metrics.mrr,
            "consistency": eval_result.metrics.retrieval_consistency,
            "hallucination_risk": eval_result.metrics.hallucination_risk,
        }

        self._state.add_sample(sample)

        if not self._state.baseline:
            self._state.set_baseline(sample)
            return None

        drift = self._state.check_drift()
        if drift.get("drift_detected") and settings.DRIFT_ALERT_ENABLED:
            DRIFT_ALERT_TRIGGERED.inc()
            for metric, drop in drift.get("drifts", {}).items():
                RETRIEVAL_DRIFT_SCORE.labels(metric=metric).observe(drop)
                GOLDEN_QUERY_REGRESSION.labels(metric=metric).observe(drop)

        return drift

    async def record_retrieval_query(
        self,
        query: str,
        result_count: int,
        latency_ms: float,
    ) -> None:
        """Record lightweight per-query telemetry for trend tracking."""
        if not settings.DRIFT_CHECK_ENABLED:
            return
        sample = {
            "latency_ms": latency_ms,
            "result_count": float(result_count),
        }
        self._state.add_sample(sample)
        if not self._state.baseline:
            self._state.set_baseline(sample)

    def get_drift_state(self) -> Dict[str, Any]:
        return self._state.check_drift()

    def reset_baseline(self) -> None:
        self._state = DriftState(window_size=settings.DRIFT_CHECK_WINDOW)


_drift_monitor: Optional[RetrievalDriftMonitor] = None


def get_drift_monitor() -> RetrievalDriftMonitor:
    global _drift_monitor
    if _drift_monitor is None:
        _drift_monitor = RetrievalDriftMonitor()
    return _drift_monitor


def reset_drift_monitor() -> None:
    global _drift_monitor
    _drift_monitor = None


def __getattr__(name: str):
    if name == "drift_monitor":
        return get_drift_monitor()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
