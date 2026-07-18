"""
Unified enterprise reranking orchestration service.

Wires the advanced RerankPipeline (skill/section/chronology boosts),
ScoreFusionService, and RerankObservability into all retrieval paths.

Every rerank call is persisted to the rerank_runs table for analytics.

Replaces the dead-code situation where RerankPipeline + ScoreFusionService +
RerankObservability were fully implemented but never called.
"""

import logging
import time
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from langsmith import traceable

from src.schemas.retrieval import (
    RetrievedChunk,
    RerankedChunk,
    RerankingObservation,
)
from src.services.reranking.rerank_pipeline import RerankPipeline
from src.services.reranking.score_fusion_service import ScoreFusionService
from src.services.reranking.rerank_observability import RerankObservability
from src.observability.metrics import (
    RERANK_LATENCY_HIST,
    RETRIEVAL_RERANK_FAILURES,
)

logger = logging.getLogger(__name__)

_enterprise_reranker: Optional["EnterpriseReranker"] = None


class EnterpriseReranker:
    """Production-grade reranking orchestrator with full observability and persistence."""

    def __init__(self):
        from src.services.retrieval.reranker import get_reranker_service
        self._pipeline = RerankPipeline()
        self._fusion = ScoreFusionService()
        self._observability = RerankObservability()
        self._core = get_reranker_service()

    @traceable(name="enterprise_rerank")
    async def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_n: int = 10,
        user_id: Optional[str] = None,
        use_boosts: bool = True,
        persist: bool = True,
    ) -> Dict[str, Any]:
        t0 = time.monotonic()
        run_id = str(uuid.uuid4())
        chunks_submitted = len(chunks)

        if not chunks:
            return {
                "reranked_chunks": [],
                "observation": RerankingObservation(
                    rerank_latency_ms=0,
                    rerank_confidence_avg=0,
                ),
                "run_id": run_id,
                "primary_success": True,
                "fallback_used": False,
            }

        primary_success = False
        fallback_used = False
        fallback_strategy = None
        fallback_reason = None
        cb_open = False
        retry_count = 0
        error_message = None
        reranked: List[RerankedChunk] = []

        try:
            if use_boosts:
                reranked = await self._pipeline.rerank_with_boosts(
                    query=query,
                    chunks=chunks,
                    top_n=top_n,
                    use_skill_priority=True,
                    use_section_priority=True,
                    use_chronology=True,
                    use_experience_boost=True,
                )
                primary_success = True
            else:
                reranked = await self._core.rerank(query, chunks, top_n=top_n)
                primary_success = True

        except Exception as e:
            logger.warning(f"Enterprise reranker primary path failed: {e}")
            RETRIEVAL_RERANK_FAILURES.inc()
            fallback_used = True
            fallback_reason = str(e)[:256]
            fallback_strategy = self._core.fallback_strategy

            if getattr(self._core._circuit, "open", False):
                cb_open = True

            try:
                reranked = await self._core.rerank(query, chunks, top_n=top_n)
            except Exception as fb_e:
                error_message = str(fb_e)[:1024]
                logger.error(f"Enterprise reranker fallback also failed: {fb_e}")
                reranked = self._core._mock_rerank(chunks, top_n)
                fallback_strategy = "emergency_mock"

        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        RERANK_LATENCY_HIST.observe(latency_ms / 1000)

        original_ids = [c.id for c in chunks] if chunks else []
        observation = await self._observability.observe(reranked, original_order_ids=original_ids)
        observation.rerank_latency_ms = latency_ms

        run_data = {
            "id": uuid.UUID(run_id) if len(run_id) == 36 else None,
            "user_id": user_id,
            "query": query,
            "chunks_submitted": chunks_submitted,
            "chunks_returned": len(reranked),
            "primary_provider": "nvidia",
            "primary_success": primary_success,
            "primary_latency_ms": latency_ms if primary_success else None,
            "fallback_used": fallback_used,
            "fallback_strategy": fallback_strategy,
            "fallback_reason": fallback_reason,
            "circuit_breaker_open": cb_open,
            "retry_count": retry_count,
            "confidence_avg": observation.rerank_confidence_avg,
            "score_distribution": observation.score_distribution,
            "rank_correlation": observation.rank_correlation,
            "rank_inversion_rate": observation.rank_inversion_rate,
            "boost_skills_applied": use_boosts,
            "boost_sections_applied": use_boosts,
            "boost_chronology_applied": use_boosts,
            "top_chunk_ids": [c.id for c in reranked[:5]] if reranked else [],
            "top_chunk_scores": [c.rerank_score for c in reranked[:5]] if reranked else [],
            "error_message": error_message,
            "created_at": datetime.utcnow(),
        }

        if persist:
            try:
                from src.db.session import async_session
                from src.db.repositories.rerank_repository import RerankRepository
                async with async_session() as db:
                    repo = RerankRepository(db)
                    await repo.create(**{k: v for k, v in run_data.items() if k != "created_at"})
            except Exception as e:
                logger.warning(f"Failed to persist rerank run {run_id}: {e}")

        return {
            "reranked_chunks": reranked,
            "observation": observation,
            "run_id": run_id,
            "primary_success": primary_success,
            "fallback_used": fallback_used,
        }

    def get_stats_sync(self) -> Dict[str, Any]:
        return {
            "circuit_breaker_open": getattr(self._core._circuit, "open", False),
            "fallback_strategy": self._core.fallback_strategy,
            "model": self._core.model_name,
            "max_batch": self._core.max_batch,
            "max_retries": self._core.max_retries,
            "timeout_s": self._core.timeout,
        }


def get_enterprise_reranker() -> EnterpriseReranker:
    global _enterprise_reranker
    if _enterprise_reranker is None:
        _enterprise_reranker = EnterpriseReranker()
    return _enterprise_reranker


def reset_enterprise_reranker() -> None:
    global _enterprise_reranker
    _enterprise_reranker = None


def __getattr__(name: str):
    if name == "enterprise_reranker":
        return get_enterprise_reranker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
