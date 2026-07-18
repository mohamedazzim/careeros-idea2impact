"""
Embedding pipeline.
Full embedding workflow orchestrator: preparation → generation → indexing.
Stateless, async-safe, retry-safe, observable. Worker-safe.
LangGraph-compatible execution states.
"""
import logging
import time
from typing import Dict, Any, List

from src.services.resume.processing.embedding_preparation import (
    embedding_preparation_pipeline,
)
from src.services.resume.processing.indexing_pipeline import indexing_pipeline
from src.observability.metrics import (
    EMBED_PREP_COUNT,
    EMBED_PREP_LATENCY,
    INDEXING_COUNT,
    INDEXING_LATENCY,
)
from src.services.resume.processing.interfaces import ProcessingStatus

logger = logging.getLogger(__name__)


class EmbeddingPipeline:
    """
    Full embedding workflow orchestrator.

    Pipeline: Chunks → EmbeddingPreperation → IndexingPipeline → Done

    Combines the two stages that were previously separate:
    1. Embedding Preparation: chunks → NV-Embed-v1-ready payloads
    2. Indexing: payloads → embeddings → Qdrant upsert

    This provides a single entry point for the full "vectorize and store" flow.
    """

    async def process_chunks(
        self,
        chunks: List[Dict[str, Any]],
        resume_id: int,
        user_id: str,
        version_num: int = 1,
        collection: str = "careeros_resumes",
    ) -> Dict[str, Any]:
        """
        Full embedding pipeline: prepare → index.

        Args:
            chunks: Semantic chunk dicts from chunking pipeline
            resume_id: Parent resume ID
            user_id: Owner user ID
            version_num: Resume version
            collection: Target Qdrant collection

        Returns:
            Pipeline result with prepare + index metrics
        """
        if not chunks:
            return {
                "payloads_prepared": 0,
                "chunks_indexed": 0,
                "status": "skip",
                "error": "No chunks provided",
            }

        overall_start = time.monotonic()
        logger.info(f"Full embedding pipeline for {len(chunks)} chunks (resume: {resume_id})")

        try:
            # Stage 1: Embedding preparation
            prep_start = time.monotonic()
            prep_result = await embedding_preparation_pipeline.prepare(
                chunks=chunks,
                resume_id=resume_id,
                user_id=user_id,
                version_num=version_num,
            )
            prep_elapsed = (time.monotonic() - prep_start) * 1000
            EMBED_PREP_COUNT.labels(status="success").inc()
            EMBED_PREP_LATENCY.observe(prep_elapsed / 1000)

            payloads = [p.to_dict() for p in prep_result.batch.payloads]

            # Stage 2: Indexing
            index_start = time.monotonic()
            index_result = await indexing_pipeline.index_chunks(
                payloads=payloads,
                resume_id=resume_id,
                user_id=user_id,
                version_num=version_num,
                collection=collection,
            )
            index_elapsed = (time.monotonic() - index_start) * 1000
            INDEXING_COUNT.labels(status="success").inc()
            INDEXING_LATENCY.observe(index_elapsed / 1000)

            overall_elapsed = round((time.monotonic() - overall_start) * 1000, 2)

            result = {
                "payloads_prepared": len(payloads),
                "chunks_indexed": index_result.get("chunks_indexed", 0),
                "collection": collection,
                "status": "success",
                "metrics": {
                    "preparation_latency_ms": round(prep_elapsed, 2),
                    "indexing_latency_ms": round(index_elapsed, 2),
                    "total_latency_ms": overall_elapsed,
                },
                "batch_metadata": {
                    "total_tokens": prep_result.batch.total_tokens,
                    "avg_chunk_tokens": prep_result.batch.avg_chunk_tokens,
                    "section_distribution": prep_result.batch.section_distribution,
                },
            }

            logger.info(f"Embedding pipeline complete: {len(payloads)} chunks indexed in {overall_elapsed}ms")
            return result

        except Exception as e:
            logger.error(f"Embedding pipeline failed: {e}")
            return {
                "payloads_prepared": 0,
                "chunks_indexed": 0,
                "status": "error",
                "error": str(e),
            }

    # ── LangGraph Node Interface ─────────────────────────────────────

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node entry point for full embedding pipeline.

        Expects semantic_chunks or chunks in state.
        Produces embedding_result and status update.

        Args:
            state: ProcessingState dict

        Returns:
            State update dict
        """
        chunks = state.get("semantic_chunks") or state.get("chunks")
        resume_id = state.get("resume_id", 0)
        user_id = state.get("user_id", "unknown")
        version_id = state.get("version_id", 1)

        if not chunks:
            return {
                "embedding_error": "No chunks available for embedding",
                "status": ProcessingStatus.FAILED,
            }

        try:
            result = await self.process_chunks(
                chunks=chunks,
                resume_id=resume_id,
                user_id=user_id,
                version_num=version_id,
                collection="careeros_resumes",
            )

            return {
                "embedding_result": result,
                "embedding_error": None,
                "status": ProcessingStatus.COMPLETED,
            }

        except Exception as e:
            return {
                "embedding_result": None,
                "embedding_error": str(e),
                "status": ProcessingStatus.FAILED,
            }


embedding_pipeline = EmbeddingPipeline()
