"""
Retrieval pipeline.
Full retrieval workflow orchestrator with LangGraph-compatible execution states.

Stateless, async-safe, retry-safe, observable. Worker-safe.
"""
import logging
from typing import Dict, Any, List, Optional

from src.services.retrieval.retrieval_service import get_retrieval_service

logger = logging.getLogger(__name__)


class RetrievalPipeline:
    """
    Full retrieval workflow orchestrator.

    Capabilities:
    - Multi-collection semantic search
    - Section-aware retrieval
    - Hybrid retrieval with metadata filtering
    - Retrieval benchmarking with latency breakdown
    - LangGraph node integration
    - Graceful degradation on failures
    """

    async def search(
        self,
        query: str,
        collection: str = "careeros_resumes",
        filter_kwargs: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        top_n: int = 5,
        use_reranker: bool = True,
        use_section_aware: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a retrieval query with full result set.

        Returns structured result dict for downstream consumers.
        """
        result = await get_retrieval_service().retrieve(
            query=query,
            collection=collection,
            filter_kwargs=filter_kwargs,
            top_k=top_k,
            top_n=top_n,
            use_reranker=use_reranker,
            use_section_aware=use_section_aware,
        )

        return {
            "query": result.query,
            "context": result.context,
            "chunks": [
                {
                    "text": c.text,
                    "score": c.score,
                    "rerank_score": c.rerank_score if hasattr(c, "rerank_score") else None,
                    "metadata": c.metadata,
                }
                for c in result.reranked_chunks
            ],
            "citations": [
                {
                    "id": c.citation_id,
                    "source": c.source,
                    "document_id": c.document_id,
                    "chunk_id": c.chunk_id,
                }
                for c in result.citations
            ],
            "metrics": result.metrics,
            "total_results": len(result.reranked_chunks),
        }

    async def search_resumes(
        self,
        query: str,
        user_id: Optional[str] = None,
        resume_id: Optional[int] = None,
        section: Optional[str] = None,
        top_k: int = 10,
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """Convenience method: search careeros_resumes."""
        filter_kwargs = {}
        if user_id:
            filter_kwargs["user_id"] = user_id
        if resume_id is not None:
            filter_kwargs["resume_id"] = resume_id
        if section:
            filter_kwargs["section"] = section

        return await self.search(
            query=query,
            collection="careeros_resumes",
            filter_kwargs=filter_kwargs or None,
            top_k=top_k,
            top_n=top_n,
            use_section_aware=True,
        )

    async def search_jobs(
        self,
        query: str,
        company: Optional[str] = None,
        top_k: int = 10,
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """Convenience method: search careeros_jobs."""
        filter_kwargs = {}
        if company:
            filter_kwargs["company"] = company

        return await self.search(
            query=query,
            collection="careeros_jobs",
            filter_kwargs=filter_kwargs or None,
            top_k=top_k,
            top_n=top_n,
        )

    async def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """Convenience method: search careeros_knowledge."""
        filter_kwargs = {}
        if category:
            filter_kwargs["category"] = category

        return await self.search(
            query=query,
            collection="careeros_knowledge",
            filter_kwargs=filter_kwargs or None,
            top_k=top_k,
            top_n=top_n,
        )

    async def benchmark(
        self,
        queries: List[str],
        collection: str = "careeros_resumes",
    ) -> List[Dict[str, Any]]:
        """
        Run retrieval benchmarks across multiple queries.

        Returns per-query latency breakdown and score distributions.
        """
        results = []
        for query in queries:
            benchmark = await get_retrieval_service().benchmark_retrieval(
                query=query,
                collection=collection,
            )
            results.append(benchmark)
        return results

    # ── LangGraph Node Interface ─────────────────────────────────────

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node entry point for retrieval.

        Expects query in state. Produces retrieved_context and retrieval_metrics.

        Args:
            state: CareerOSState or similar dict

        Returns:
            State update dict with retrieval results
        """
        query = state.get("query") or state.get("job_data", {}).get("description", "")
        if not query:
            return {
                "retrieved_context": "",
                "retrieval_error": "No query provided",
                "status": "error",
            }

        collection = state.get("retrieval_collection", "careeros_resumes")
        filter_kwargs = state.get("retrieval_filters")
        user_id = state.get("user_id")

        try:
            result = await self.search(
                query=query,
                collection=collection,
                filter_kwargs=filter_kwargs,
                top_k=state.get("retrieval_top_k", 10),
                top_n=state.get("retrieval_top_n", 5),
                use_reranker=state.get("use_reranker", True),
                use_section_aware=True,
            )

            return {
                "retrieved_context": result["context"],
                "retrieval_chunks": result["chunks"],
                "retrieval_citations": result["citations"],
                "retrieval_metrics": result["metrics"],
                "retrieval_error": None,
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Retrieval pipeline failed: {e}")
            return {
                "retrieved_context": "",
                "retrieval_chunks": [],
                "retrieval_metrics": {"error": str(e)},
                "retrieval_error": str(e),
                "status": "error",
            }


_retrieval_pipeline = None


def get_retrieval_pipeline() -> RetrievalPipeline:
    global _retrieval_pipeline
    if _retrieval_pipeline is None:
        _retrieval_pipeline = RetrievalPipeline()
    return _retrieval_pipeline


def reset_retrieval_pipeline() -> None:
    global _retrieval_pipeline
    _retrieval_pipeline = None


def __getattr__(name: str):
    if name == "retrieval_pipeline":
        return get_retrieval_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
