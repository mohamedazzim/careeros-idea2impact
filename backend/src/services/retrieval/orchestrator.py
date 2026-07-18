import logging
import time
from typing import Dict, Any, Optional
from langsmith import traceable

from src.schemas.retrieval import RetrievalResult, RetrievedChunk
from src.services.embedding.nvembed_service import get_nvembed_service
from src.services.vector_store.engine import get_vector_engine
from src.services.retrieval.reranker import get_reranker_service
from src.services.retrieval.context_builder import get_context_builder
from src.observability.tracing import trace_async

logger = logging.getLogger(__name__)

class RetrievalOrchestrator:
    @trace_async("retrieve_context_orchestrator")
    @traceable(name="retrieve_context_orchestrator")
    async def retrieve_context(
        self,
        query: str,
        collection_type: str = "resumes",
        filter_kwargs: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        top_n: int = 5
    ) -> RetrievalResult:
        metrics = {}
        start_time = time.time()
        nvembed = get_nvembed_service()
        vengine = get_vector_engine()
        reranker = get_reranker_service()
        ctx_builder = get_context_builder()
        
        # 1. Embed Query
        t0 = time.time()
        query_vector = await nvembed.embed_query(query)
        metrics["embed_latency"] = time.time() - t0
        
        # 2. Retrieve Vectors
        t0 = time.time()
        if collection_type == "resumes":
            qdrant_results = await vengine.query_resumes(
                query_vector=query_vector,
                limit=top_k,
                **(filter_kwargs or {})
            )
        elif collection_type == "jobs":
            qdrant_results = await vengine.query_jobs(
                query_vector=query_vector,
                limit=top_k,
                **(filter_kwargs or {})
            )
        elif collection_type == "knowledge":
            qdrant_results = await vengine.query_knowledge(
                query_vector=query_vector,
                limit=top_k,
                **(filter_kwargs or {})
            )
        else:
            raise ValueError(f"Unknown collection type: {collection_type}")
            
        metrics["retrieval_latency"] = time.time() - t0
        
        # Map to RetrievedChunk
        retrieved_chunks = []
        for r in qdrant_results:
            payload = r.payload or {}
            retrieved_chunks.append(RetrievedChunk(
                id=str(r.id),
                document_id=payload.get("document_id"),
                chunk_id=payload.get("chunk_id"),
                text=payload.get("text", ""),
                score=r.score,
                source=payload.get("source"),
                metadata=payload
            ))
            
        # 3. Rerank
        t0 = time.time()
        reranked_chunks = await reranker.rerank(query, retrieved_chunks, top_n=top_n)
        metrics["rerank_latency"] = time.time() - t0
        
        # 4. Assemble Context & Citations
        t0 = time.time()
        context, citations = ctx_builder.assemble(reranked_chunks)
        metrics["assembly_latency"] = time.time() - t0
        
        metrics["total_latency"] = time.time() - start_time
        
        return RetrievalResult(
            query=query,
            retrieved_chunks=retrieved_chunks,
            reranked_chunks=reranked_chunks,
            context=context,
            citations=citations,
            metrics=metrics
        )

_retrieval_orchestrator = None


def get_retrieval_orchestrator() -> RetrievalOrchestrator:
    global _retrieval_orchestrator
    if _retrieval_orchestrator is None:
        _retrieval_orchestrator = RetrievalOrchestrator()
    return _retrieval_orchestrator


def reset_retrieval_orchestrator() -> None:
    global _retrieval_orchestrator
    _retrieval_orchestrator = None


def __getattr__(name: str):
    if name == "retrieval_orchestrator":
        return get_retrieval_orchestrator()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
