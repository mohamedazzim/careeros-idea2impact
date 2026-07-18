"""
Production-grade retrieval service.
Semantic similarity search with metadata filtering, section-aware retrieval,
hybrid retrieval preparation, scoring, and benchmarking.

Stateless, async-safe, retry-safe, observable. Worker-safe.
"""
import logging
import time
from typing import List, Dict, Any, Optional

from src.services.embedding.embedding_service import get_embedding_service
from src.services.vector_store.qdrant_service import get_qdrant_service
from src.services.retrieval.reranker import get_reranker_service
from src.services.retrieval.context_builder import get_context_builder
from src.schemas.retrieval import (
    RetrievalResult,
    RetrievedChunk,
    RerankedChunk,
)
from src.observability.metrics import (
    RETRIEVAL_SERVICE_CALLS,
    RETRIEVAL_SERVICE_SCORES,
    RETRIEVAL_SERVICE_TOP_K,
    RETRIEVAL_LATENCY_HIST,
    QDRANT_LATENCY_HIST,
    RERANK_LATENCY_HIST,
    RETRIEVAL_MISS_TOTAL,
    RETRIEVAL_EMPTY_RESULTS,
    RETRIEVAL_RERANK_FAILURES,
)

logger = logging.getLogger(__name__)

# Section weights used in section-aware retrieval
RETRIEVAL_SECTION_WEIGHTS: Dict[str, float] = {
    "experience": 1.0,
    "skills": 1.2,
    "summary": 1.1,
    "education": 0.9,
    "projects": 0.9,
    "certifications": 0.85,
    "awards": 0.8,
    "languages": 0.7,
    "publications": 0.8,
    "contact": 0.3,
    "general": 0.5,
    "preamble": 0.4,
}


class RetrievalService:
    """
    Production-grade retrieval service.

    Capabilities:
    - Semantic similarity search across all collections
    - Metadata filtering (user_id, resume_id, version_num, section, company, etc.)
    - Section-aware retrieval with oversampling + weight-based reranking
    - Hybrid retrieval preparation (semantic + metadata)
    - Retrieval scoring and benchmark capture
    - Full observability (latency histograms, score distributions, top-k counts)
    """

    # ── Primary Retrieval ────────────────────────────────────────────

    async def retrieve(
        self,
        query: str,
        collection: str = "careeros_resumes",
        filter_kwargs: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        top_n: int = 5,
        score_threshold: Optional[float] = None,
        use_reranker: bool = True,
        use_section_aware: bool = False,
    ) -> RetrievalResult:
        """
        Full retrieval pipeline: embed → search → (section-weight) → rerank → assemble.

        Args:
            query: Natural language query
            collection: Target collection name
            filter_kwargs: Metadata filters
            top_k: Number of initial candidates
            top_n: Number of final results after reranking
            score_threshold: Minimum cosine similarity
            use_reranker: Apply NVIDIA reranker
            use_section_aware: Apply section-weighted retrieval
        """
        if not query:
            raise ValueError("Query text is required")

        overall_start = time.monotonic()
        metrics: Dict[str, float] = {}

        try:
            # 1. Embed query
            t0 = time.monotonic()
            query_vector = await get_embedding_service().embed_query(query)
            metrics["embed_latency_ms"] = round((time.monotonic() - t0) * 1000, 2)
            RETRIEVAL_LATENCY_HIST.labels(operation="embed").observe(
                metrics["embed_latency_ms"] / 1000
            )

            # 2. Vector search
            t0 = time.monotonic()
            qdrant = get_qdrant_service()

            if use_section_aware:
                oversample = top_k * 3
                qdrant_results = await qdrant.search_with_section_waiting(
                    collection_name=collection,
                    query_vector=query_vector,
                    section_weights=RETRIEVAL_SECTION_WEIGHTS,
                    filter_kwargs=filter_kwargs,
                    limit=min(top_k, top_k),
                    oversample_multiplier=3,
                )
            else:
                qdrant_results = await qdrant.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    filter_kwargs=filter_kwargs,
                    limit=top_k,
                    score_threshold=score_threshold,
                )

            metrics["qdrant_latency_ms"] = round((time.monotonic() - t0) * 1000, 2)
            QDRANT_LATENCY_HIST.observe(metrics["qdrant_latency_ms"] / 1000)

            # Track empty results after vector search
            if not qdrant_results:
                RETRIEVAL_MISS_TOTAL.labels(collection=collection).inc()
                RETRIEVAL_EMPTY_RESULTS.labels(
                    collection=collection, stage="post_qdrant"
                ).inc()

            # 3. Map to RetrievedChunk
            retrieved_chunks = self._map_chunks(qdrant_results)
            for rc in retrieved_chunks:
                RETRIEVAL_SERVICE_SCORES.observe(rc.score)

            # 4. Rerank (optional) — with failure tracking
            if use_reranker and retrieved_chunks:
                t0 = time.monotonic()
                try:
                    reranked_chunks = await get_reranker_service().rerank(
                        query, retrieved_chunks, top_n=top_n
                    )
                    metrics["rerank_latency_ms"] = round((time.monotonic() - t0) * 1000, 2)
                    RERANK_LATENCY_HIST.observe(metrics["rerank_latency_ms"] / 1000)
                except Exception as e:
                    RETRIEVAL_RERANK_FAILURES.inc()
                    logger.warning(f"Reranker failed, falling back to score-only ordering: {e}")
                    reranked_chunks = [
                        RerankedChunk(**rc.model_dump(), rerank_score=rc.score)
                        for rc in sorted(
                            retrieved_chunks, key=lambda x: x.score, reverse=True
                        )[:top_n]
                    ]
            else:
                reranked_chunks = [
                    RerankedChunk(**rc.model_dump(), rerank_score=rc.score)
                    for rc in retrieved_chunks[:top_n]
                ]

            # Track empty results after rerank
            if not reranked_chunks:
                RETRIEVAL_EMPTY_RESULTS.labels(
                    collection=collection, stage="post_rerank"
                ).inc()

            # 5. Assemble context
            t0 = time.monotonic()
            context, citations = get_context_builder().assemble(reranked_chunks)
            metrics["assembly_latency_ms"] = round((time.monotonic() - t0) * 1000, 2)

            # Total
            metrics["total_latency_ms"] = round(
                (time.monotonic() - overall_start) * 1000, 2
            )
            RETRIEVAL_SERVICE_TOP_K.observe(len(reranked_chunks))

            RETRIEVAL_SERVICE_CALLS.labels(status="success").inc()

            logger.info(
                f"Retrieval: '{query[:60]}...' → {len(reranked_chunks)} results "
                f"({metrics['total_latency_ms']}ms total)"
            )

            return RetrievalResult(
                query=query,
                retrieved_chunks=retrieved_chunks,
                reranked_chunks=reranked_chunks,
                context=context,
                citations=citations,
                metrics=metrics,
            )

        except Exception as e:
            RETRIEVAL_SERVICE_CALLS.labels(status="error").inc()
            logger.error(f"Retrieval failed: {e}")

            return RetrievalResult(
                query=query,
                retrieved_chunks=[],
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
        version_num: Optional[int] = None,
        section: Optional[str] = None,
        top_k: int = 10,
        top_n: int = 5,
    ) -> RetrievalResult:
        """Retrieve from careeros_resumes with resume-specific filters."""
        filter_kwargs = {}
        if user_id:
            filter_kwargs["user_id"] = user_id
        if resume_id is not None:
            filter_kwargs["resume_id"] = resume_id
        if version_num is not None:
            filter_kwargs["version_num"] = version_num
        if section:
            filter_kwargs["section"] = section

        return await self.retrieve(
            query=query,
            collection="careeros_resumes",
            filter_kwargs=filter_kwargs or None,
            top_k=top_k,
            top_n=top_n,
            use_section_aware=bool(section is None),
        )

    async def retrieve_jobs(
        self,
        query: str,
        company: Optional[str] = None,
        job_id: Optional[str] = None,
        top_k: int = 10,
        top_n: int = 5,
    ) -> RetrievalResult:
        """Retrieve from careeros_jobs."""
        filter_kwargs = {}
        if company:
            filter_kwargs["company"] = company
        if job_id:
            filter_kwargs["job_id"] = job_id

        return await self.retrieve(
            query=query,
            collection="careeros_jobs",
            filter_kwargs=filter_kwargs or None,
            top_k=top_k,
            top_n=top_n,
        )

    async def retrieve_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        source: Optional[str] = None,
        top_k: int = 10,
        top_n: int = 5,
    ) -> RetrievalResult:
        """Retrieve from careeros_knowledge."""
        filter_kwargs = {}
        if category:
            filter_kwargs["category"] = category
        if source:
            filter_kwargs["source"] = source

        return await self.retrieve(
            query=query,
            collection="careeros_knowledge",
            filter_kwargs=filter_kwargs or None,
            top_k=top_k,
            top_n=top_n,
        )

    # ── Benchmark Method ─────────────────────────────────────────────

    async def benchmark_retrieval(
        self,
        query: str,
        collection: str = "careeros_resumes",
        filter_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run retrieval benchmark with full latency breakdown.

        Returns detailed metrics for each pipeline stage.
        """
        result = await self.retrieve(
            query=query,
            collection=collection,
            filter_kwargs=filter_kwargs,
            top_k=20,
            top_n=10,
            use_reranker=True,
        )

        return {
            "query": query,
            "collection": collection,
            "results_count": len(result.reranked_chunks),
            "metrics": result.metrics,
            "top_scores": [round(c.rerank_score, 4) for c in result.reranked_chunks[:5]],
            "top_sections": [
                (c.metadata.get("section", "unknown") if isinstance(c.metadata, dict) else "unknown")
                for c in result.reranked_chunks[:5]
            ],
        }

    # ── Helpers ──────────────────────────────────────────────────────

    def _map_chunks(self, qdrant_results: List) -> List[RetrievedChunk]:
        """Map Qdrant ScoredPoints to RetrievedChunks."""
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


_retrieval_service = None


def get_retrieval_service() -> RetrievalService:
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    return _retrieval_service


def reset_retrieval_service() -> None:
    global _retrieval_service
    _retrieval_service = None


def __getattr__(name: str):
    if name == "retrieval_service":
        return get_retrieval_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
