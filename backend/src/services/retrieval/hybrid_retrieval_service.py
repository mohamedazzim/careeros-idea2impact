"""
Production-grade hybrid retrieval service.

Full pipeline: Query Understanding → Routing → Dense + Sparse → RRF Fusion → Rerank → Context

Stateless, async-safe, retry-safe, observable. Worker-safe.
"""
import asyncio
import logging
import time

logger = logging.getLogger(__name__)
from typing import List, Dict, Any, Optional

from src.services.embedding.embedding_service import get_embedding_service
from src.services.vector_store.qdrant_service import get_qdrant_service
from src.services.retrieval.sparse_retriever import get_sparse_retriever
from src.services.retrieval.reciprocal_rank_fusion import fuse_rrf, fuse_weighted_sum
from src.services.retrieval.query_understanding_service import get_query_understanding_service
from src.services.retrieval.retrieval_router import get_retrieval_router
from src.observability.metrics import RETRIEVAL_CACHE_WRITE
from src.services.retrieval.context_builder import get_context_builder
from src.services.retrieval.retrieval_cache import get_retrieval_cache
from src.services.retrieval.federated_hardening import get_federated_merger
from src.services.retrieval.retrieval_drift_monitor import get_drift_monitor
from src.services.context.context_integrity import get_integrity_guard
from src.services.context.context_assembly_service import get_context_assembly_service
from src.core.config import settings
from src.schemas.retrieval import (
    HybridRetrievalResult,
    RetrievedChunk,
    RerankedChunk,
    FusedResult,
    FusionMethod,
)
from src.observability.metrics import (
    HYBRID_RETRIEVAL_CALLS,
    HYBRID_RETRIEVAL_LATENCY,
    HYBRID_RECALL_GAIN,
    RETRIEVAL_CACHE_HIT,
    RETRIEVAL_CACHE_MISS,
    FEDERATION_LATENCY,
    FEDERATION_COLLECTION_COUNT,
    FEDERATION_DEDUP_REMOVED,
)


class HybridRetrievalService:
    """Production-grade hybrid retrieval combining dense, sparse, and metadata search.

    Pipeline:
    1. Query understanding (intent + skills + expansion)
    2. Retrieval routing (which collection(s))
    3. Dense retrieval (NV-Embed-v1 → Qdrant)
    4. Sparse retrieval (BM25 inverted index)
    5. Reciprocal Rank Fusion (RRF)
    6. Reranking (rerank-qa-mistral-4b)
    7. Context assembly (dedup + cite)
    """

    async def retrieve(
        self,
        query: str,
        collection: str = "careeros_resumes",
        filter_kwargs: Optional[Dict[str, Any]] = None,
        top_k: int = 30,
        top_n: int = 10,
        use_hybrid: bool = True,
        use_sparse: bool = True,
        use_reranker: bool = True,
        fusion_method: FusionMethod = FusionMethod.RRF,
        rrf_k: int = 60,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.4,
    ) -> HybridRetrievalResult:
        """Execute full hybrid retrieval pipeline.

        Args:
            query: Natural language query
            collection: Target Qdrant collection
            filter_kwargs: Metadata filters
            top_k: Candidate pool per retrieval method
            top_n: Final result count
            use_hybrid: Enable hybrid (dense+sparse+fusion) pipeline
            use_sparse: Enable BM25 sparse retrieval
            use_reranker: Apply NVIDIA reranker
            fusion_method: RRF or weighted_sum
            rrf_k: RRF smoothing parameter
            dense_weight: Weight for dense retrieval in fusion
            sparse_weight: Weight for sparse retrieval in fusion

        Returns:
            HybridRetrievalResult with all results and metrics
        """
        if not query:
            raise ValueError("Query text is required")

        overall_start = time.monotonic()
        metrics: Dict[str, float] = {}

        try:
            # ── Step 1: Query Understanding ─────────────────────────
            t0 = time.monotonic()
            q_understanding = get_query_understanding_service()
            understanding = await q_understanding.understand(query)
            metrics["query_intent"] = understanding.intent.value
            metrics["query_expansions"] = len(understanding.expanded_queries)
            metrics["extracted_skills"] = len(understanding.extracted_skills)

            # ── Step 2: Routing ─────────────────────────────────────
            router = get_retrieval_router()
            routing = await router.route(query, intent=understanding.intent)

            # Use routed collection if not explicitly specified
            effective_collection = collection or routing.target_collections[0]

            # ── Step 3: Dense Retrieval ─────────────────────────────
            embed_svc = get_embedding_service()
            qdrant = get_qdrant_service()

            t0 = time.monotonic()
            query_vector = await embed_svc.embed_query(query)
            metrics["embed_latency_ms"] = round((time.monotonic() - t0) * 1000, 2)

            t0 = time.monotonic()
            dense_points = await qdrant.search(
                collection_name=effective_collection,
                query_vector=query_vector,
                filter_kwargs=filter_kwargs,
                limit=top_k,
            )
            metrics["dense_latency_ms"] = round((time.monotonic() - t0) * 1000, 2)

            dense_results = _map_to_retrieved_chunks(dense_points)

            # ── Step 4: Sparse Retrieval ────────────────────────────
            sparse_results = []
            if use_sparse and not use_hybrid:
                use_sparse = True  # sparse-only for comparison

            if use_sparse or use_hybrid:
                t0 = time.monotonic()
                sparse_retriever = get_sparse_retriever()
                sparse_response = await sparse_retriever.search(
                    query=query,
                    collection=effective_collection,
                    top_k=top_k,
                )
                sparse_results = sparse_response.results
                metrics["sparse_latency_ms"] = round(
                    (time.monotonic() - t0) * 1000, 2
                )
                metrics["sparse_results"] = len(sparse_results)

            # ── Step 5: Fusion ──────────────────────────────────────
            fused_results: List[FusedResult] = []
            if use_hybrid and dense_results and sparse_results:
                t0 = time.monotonic()
                if fusion_method == FusionMethod.WEIGHTED_SUM:
                    fused_results = await fuse_weighted_sum(
                        dense_results=dense_results,
                        sparse_results=sparse_results,
                        dense_weight=dense_weight,
                        sparse_weight=sparse_weight,
                        top_k=top_n * 3,
                    )
                else:
                    fused_results = await fuse_rrf(
                        dense_results=dense_results,
                        sparse_results=sparse_results,
                        k=rrf_k,
                        dense_weight=dense_weight,
                        sparse_weight=sparse_weight,
                    )
                metrics["fusion_latency_ms"] = round(
                    (time.monotonic() - t0) * 1000, 2
                )
                metrics["fused_count"] = len(fused_results)

            # If no hybrid or insufficient results, use dense-only
            if not fused_results:
                fused_results = _dense_to_fused(dense_results)

            # ── Step 6: Reranking (Enterprise Pipeline) ────────────
            reranked_chunks: List[RerankedChunk] = []
            if use_reranker and fused_results:
                t0 = time.monotonic()
                retrieved_for_rerank = [
                    RetrievedChunk(
                        id=f.chunk_id,
                        text=f.text,
                        score=f.rrf_score,
                        source=f.source,
                        metadata=f.metadata,
                    )
                    for f in fused_results[:top_k]
                ]
                try:
                    from src.services.reranking.enterprise_reranker import get_enterprise_reranker
                    enterprise_reranker = get_enterprise_reranker()
                    result = await enterprise_reranker.rerank(
                        query=query,
                        chunks=retrieved_for_rerank,
                        top_n=top_n,
                        user_id=None,
                        use_boosts=True,
                        persist=True,
                    )
                    reranked_chunks = result["reranked_chunks"]
                    metrics["rerank_latency_ms"] = round((time.monotonic() - t0) * 1000, 2)
                    metrics["rerank_fallback_used"] = result.get("fallback_used", False)
                    metrics["rerank_primary_success"] = result.get("primary_success", False)
                except Exception as e:
                    logger.warning(f"Enterprise reranker failed in hybrid pipeline: {e}")
                    reranked_chunks = [
                        RerankedChunk(
                            id=f.chunk_id,
                            text=f.text,
                            score=f.rrf_score,
                            rerank_score=f.rrf_score,
                            source=f.source,
                            metadata=f.metadata,
                        )
                        for f in fused_results[:top_n]
                    ]
                    metrics["rerank_latency_ms"] = round((time.monotonic() - t0) * 1000, 2)
            else:
                reranked_chunks = [
                    RerankedChunk(
                        id=f.chunk_id,
                        text=f.text,
                        score=f.rrf_score,
                        rerank_score=f.rrf_score,
                        source=f.source,
                        metadata=f.metadata,
                    )
                    for f in fused_results[:top_n]
                ]

            # ── Step 7: Context Assembly ────────────────────────────
            t0 = time.monotonic()
            ctx_builder = get_context_builder()
            context, citations = ctx_builder.assemble(reranked_chunks)
            metrics["assembly_latency_ms"] = round(
                (time.monotonic() - t0) * 1000, 2
            )

            # Total
            metrics["total_latency_ms"] = round(
                (time.monotonic() - overall_start) * 1000, 2
            )

            HYBRID_RETRIEVAL_CALLS.labels(
                collection=effective_collection, status="success"
            ).inc()
            HYBRID_RETRIEVAL_LATENCY.labels(
                collection=effective_collection
            ).observe(metrics["total_latency_ms"] / 1000)

            # Recall gain: fused unique vs dense-only unique
            fused_ids = {f.chunk_id for f in fused_results}
            dense_ids = {c.id for c in dense_results}
            recall_gain = (
                len(fused_ids - dense_ids) / max(len(fused_ids), 1)
            )
            metrics["recall_gain"] = recall_gain
            HYBRID_RECALL_GAIN.labels(k=str(top_n)).observe(recall_gain)

            logger.info(
                f"Hybrid retrieval: '{query[:60]}...' → "
                f"dense({len(dense_results)}) + sparse({len(sparse_results)}) "
                f"= fused({len(fused_results)}) → reranked({len(reranked_chunks)}) "
                f"({metrics['total_latency_ms']}ms, recall_gain={recall_gain:.2%})"
            )

            return HybridRetrievalResult(
                query=query,
                dense_results=dense_results,
                sparse_results=sparse_results,
                fused_results=fused_results,
                reranked_chunks=reranked_chunks,
                context=context,
                citations=citations,
                metrics=metrics,
            )

        except Exception as e:
            HYBRID_RETRIEVAL_CALLS.labels(
                collection=collection, status="error"
            ).inc()
            logger.error(f"Hybrid retrieval failed: {e}")
            return HybridRetrievalResult(
                query=query,
                dense_results=[],
                sparse_results=[],
                fused_results=[],
                reranked_chunks=[],
                context="",
                citations=[],
                metrics={"error": str(e), "total_latency_ms": 0},
            )

    # ── Convenience Methods ──────────────────────────────────────────

    async def retrieve_resumes(
        self,
        query: str,
        user_id: Optional[str] = None,
        resume_id: Optional[int] = None,
        section: Optional[str] = None,
        top_k: int = 30,
        top_n: int = 10,
        use_hybrid: bool = True,
    ) -> HybridRetrievalResult:
        filter_kwargs = {}
        if user_id:
            filter_kwargs["user_id"] = user_id
        if resume_id is not None:
            filter_kwargs["resume_id"] = resume_id
        if section:
            filter_kwargs["section"] = section
        return await self.retrieve(
            query=query,
            collection="careeros_resumes",
            filter_kwargs=filter_kwargs or None,
            top_k=top_k,
            top_n=top_n,
            use_hybrid=use_hybrid,
        )

    async def federated_retrieve(
        self,
        query: str,
        top_k: int = 20,
        top_n_per_collection: int = 5,
    ) -> Dict[str, Any]:
        """Parallel federated retrieval across routed collections.

        Uses asyncio.gather() with bounded concurrency, per-collection
        timeout, partial recovery, and FederatedResultMerger.
        """
        router = get_retrieval_router()
        routing = await router.route(query)

        # Cache check for federated results
        cache = get_retrieval_cache()
        cached = await cache.get_query(query, "__federated__", top_k)
        if cached:
            RETRIEVAL_CACHE_HIT.labels(level="federated").inc()
            return cached
        RETRIEVAL_CACHE_MISS.labels(level="federated").inc()

        overall_start = time.monotonic()
        max_concurrent = settings.FEDERATION_MAX_CONCURRENT
        per_collection_timeout = settings.FEDERATION_TIMEOUT
        semaphore = asyncio.Semaphore(max_concurrent)

        async def retrieve_one(collection: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    weight = routing.collection_weights.get(collection, 0.3)
                    collection_top = max(3, int(top_n_per_collection * weight * 3))
                    result = await asyncio.wait_for(
                        self.retrieve(
                            query=query,
                            collection=collection,
                            top_k=top_k,
                            top_n=collection_top,
                            use_hybrid=True,
                        ),
                        timeout=per_collection_timeout,
                    )
                    return {"collection": collection, "result": result, "error": None}
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Federated timeout for collection '{collection}' "
                        f"({per_collection_timeout}s)"
                    )
                    return {"collection": collection, "result": None,
                            "error": "timeout"}
                except Exception as e:
                    logger.error(
                        f"Federated failure for '{collection}': {e}"
                    )
                    return {"collection": collection, "result": None,
                            "error": str(e)}

        # Parallel execution with partial recovery
        tasks = [
            retrieve_one(coll) for coll in routing.target_collections
        ]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect per-collection results
        collection_results: Dict[str, HybridRetrievalResult] = {}
        federation_errors: Dict[str, str] = {}
        all_fused: List[FusedResult] = []

        for item in gathered:
            if isinstance(item, Exception):
                logger.error(f"Federated task exception: {item}")
                continue
            if not isinstance(item, dict):
                continue
            coll = item["collection"]
            if item["error"]:
                federation_errors[coll] = item["error"]
            if item["result"] is not None:
                collection_results[coll] = item["result"]
                all_fused.extend(item["result"].fused_results)

        # Apply FederatedResultMerger for cross-collection normalization
        merger = get_federated_merger()
        merged_fused = merger.merge(
            collection_results={
                c: r.fused_results for c, r in collection_results.items()
            },
            routing=routing,
        )

        # Build assembled context
        assembly = get_context_assembly_service()
        assembled = await assembly.assemble(
            chunks=merged_fused,
            query=query,
        )

        # Integrity guard
        guard = get_integrity_guard()
        integrity_report = guard.guard(
            blocks=assembled.blocks,
            citations=assembled.citations,
            context=assembled.context,
            max_tokens=settings.CONTEXT_MAX_TOKENS,
        )
        if not integrity_report["integrity_valid"]:
            logger.warning(
                f"Federated context integrity issues: "
                f"citations={integrity_report['citations']['valid']}, "
                f"chronology={integrity_report['chronology']['chronology_valid']}, "
                f"overflow={integrity_report['token_budget']['overflow']}"
            )
            assembled = guard.repair(assembled, integrity_report)

        # Drift monitoring
        if settings.DRIFT_CHECK_ENABLED:
            drift_monitor = get_drift_monitor()
            await drift_monitor.record_retrieval_query(
                query=query,
                result_count=len(merged_fused),
                latency_ms=(time.monotonic() - overall_start) * 1000,
            )

        elapsed = (time.monotonic() - overall_start) * 1000
        FEDERATION_LATENCY.observe(elapsed / 1000)
        FEDERATION_COLLECTION_COUNT.observe(len(collection_results))
        FEDERATION_DEDUP_REMOVED.inc(
            len(all_fused) - len(merged_fused)
        )

        result = {
            "query": query,
            "routing": routing.model_dump(),
            "collections_queried": len(routing.target_collections),
            "collections_succeeded": len(collection_results),
            "federation_errors": federation_errors,
            "merged_chunks": [m.model_dump() for m in merged_fused],
            "context": assembled.context,
            "citations": [c.model_dump() for c in assembled.citations],
            "federated_result_count": len(merged_fused),
            "total_latency_ms": round(elapsed, 2),
            "integrity": integrity_report["integrity_valid"],
        }

        # Cache the federated result
        await cache.set_query(query, "__federated__", top_k, result)
        RETRIEVAL_CACHE_WRITE.labels(level="federated").inc()

        return result


# ── Helpers ─────────────────────────────────────────────────────────

def _map_to_retrieved_chunks(qdrant_results: List) -> List[RetrievedChunk]:
    chunks = []
    for r in qdrant_results:
        payload = r.payload or {}
        chunks.append(
            RetrievedChunk(
                id=str(r.id),
                document_id=payload.get("document_id"),
                chunk_id=payload.get("chunk_id"),
                text=payload.get("text", ""),
                score=r.score,
                source=payload.get("source"),
                metadata=payload,
            )
        )
    return chunks


def _dense_to_fused(dense_results: List[RetrievedChunk]) -> List[FusedResult]:
    return [
        FusedResult(
            chunk_id=c.id,
            text=c.text,
            rrf_score=c.score,
            dense_rank=i + 1,
            dense_score=c.score,
            fusion_method=FusionMethod.RRF.value,
            source=c.source,
            metadata=c.metadata,
        )
        for i, c in enumerate(dense_results)
    ]


# Module-level singleton
_hybrid_retrieval_service: Optional[HybridRetrievalService] = None


def get_hybrid_retrieval_service() -> HybridRetrievalService:
    global _hybrid_retrieval_service
    if _hybrid_retrieval_service is None:
        _hybrid_retrieval_service = HybridRetrievalService()
    return _hybrid_retrieval_service


def reset_hybrid_retrieval_service() -> None:
    global _hybrid_retrieval_service
    _hybrid_retrieval_service = None


def __getattr__(name: str):
    if name == "hybrid_retrieval_service":
        return get_hybrid_retrieval_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
