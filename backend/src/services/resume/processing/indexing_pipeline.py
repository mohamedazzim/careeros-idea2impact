"""
Indexing pipeline.
Orchestrates embedding generation + Qdrant upsert with retries, batching,
and full observability.

Stateless, async-safe, retry-safe, observable. Worker-safe.
LangGraph-compatible execution states.
"""
import asyncio
import logging
import time
import uuid
from typing import Dict, Any, List

from qdrant_client.models import PointStruct

from src.services.embedding.embedding_service import get_embedding_service
from src.services.vector_store.qdrant_service import get_qdrant_service
from src.observability.metrics import (
    INDEXING_COUNT,
    INDEXING_LATENCY,
    INDEXING_CHUNKS_INDEXED,
    INDEXING_BATCHES,
    INDEXING_PARTIAL_BATCH,
    INDEXING_RETRY_IDEMPOTENT,
    INDEXING_DEAD_LETTER,
)
from src.services.resume.processing.interfaces import ProcessingStatus

logger = logging.getLogger(__name__)


class IndexingPipeline:
    """
    Production-grade indexing pipeline.

    Pipeline: embedding_preparation → embedding_generation → qdrant_upsert

    Capabilities:
    - Takes EmbeddingPayload objects and converts to Qdrant PointStructs
    - Batch embedding generation with retries
    - Upsert with retry safety and payload validation
    - Namespace isolation per collection
    - Checkpoint-compatible for LangGraph
    - Full observability (latency, chunks indexed, batch counts)
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0

    async def index_chunks(
        self,
        payloads: List[Dict[str, Any]],
        resume_id: int,
        user_id: str,
        version_num: int = 1,
        collection: str = "careeros_resumes",
    ) -> Dict[str, Any]:
        """
        Index chunks: generate embeddings → upsert to Qdrant.

        Args:
            payloads: EmbeddingPayload dicts from embedding preparation
            resume_id: Parent resume ID
            user_id: Owner user ID
            version_num: Resume version number
            collection: Target Qdrant collection

        Returns:
            Indexing result with metrics
        """
        if not payloads:
            logger.warning("No payloads to index")
            return {
                "chunks_indexed": 0,
                "batches_processed": 0,
                "status": "skip",
            }

        overall_start = time.monotonic()
        total = len(payloads)

        logger.info(f"Indexing {total} chunks to '{collection}' (resume: {resume_id})")

        try:
            # 1. Extract embedding texts from payloads
            embedding_texts = [
                p.get("embedding_text", p.get("text", "")) for p in payloads
            ]

            # 2. Generate embeddings (batched with retries via embedding_service)
            vectors = await get_embedding_service().generate_embeddings(
                texts=embedding_texts,
                input_type="passage",
                use_cache=True,
            )

            # 3. Build Qdrant PointStructs
            points = self._build_points(
                payloads, vectors, resume_id, user_id, version_num
            )

            # 4. Upsert to Qdrant
            await get_qdrant_service().upsert_points(
                collection_name=collection,
                points=points,
                validate=True,
            )

            elapsed = (time.monotonic() - overall_start) * 1000

            INDEXING_COUNT.labels(status="success").inc()
            INDEXING_LATENCY.observe(elapsed / 1000)
            INDEXING_CHUNKS_INDEXED.labels(collection=collection).inc(total)
            INDEXING_BATCHES.labels(collection=collection).inc(1)

            logger.info(
                f"Indexed {total} chunks to '{collection}' in {elapsed:.0f}ms"
            )

            return {
                "chunks_indexed": total,
                "batches_processed": 1,
                "total_latency_ms": round(elapsed, 2),
                "collection": collection,
                "status": "success",
            }

        except Exception as e:
            INDEXING_COUNT.labels(status="error").inc()
            logger.error(f"Indexing failed: {e}")
            raise

    async def index_with_retries(
        self,
        payloads: List[Dict[str, Any]],
        resume_id: int,
        user_id: str,
        version_num: int = 1,
        collection: str = "careeros_resumes",
    ) -> Dict[str, Any]:
        """
        Index chunks with exponential backoff retry logic and idempotency.

        Uses deterministic point IDs (UUID5) so replays of the same
        resume_id+version_num+chunk_index produce the same upsert — safe
        to retry without creating duplicates.
        """
        last_exception = None
        for attempt in range(self.MAX_RETRIES):
            try:
                INDEXING_RETRY_IDEMPOTENT.labels(
                    collection=collection, attempt=str(attempt + 1)
                ).inc()
                return await self.index_chunks(
                    payloads=payloads,
                    resume_id=resume_id,
                    user_id=user_id,
                    version_num=version_num,
                    collection=collection,
                )
            except Exception as e:
                last_exception = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"Index attempt {attempt + 1} failed, retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Dead-letter: log the failed batch metadata for later replay
                    self._dead_letter_enqueue(
                        payloads=payloads,
                        resume_id=resume_id,
                        user_id=user_id,
                        version_num=version_num,
                        collection=collection,
                        error=str(e),
                    )

        INDEXING_COUNT.labels(status="error").inc()
        raise Exception(
            f"Indexing failed after {self.MAX_RETRIES} attempts: {last_exception}"
        )

    async def index_batches_with_partial_recovery(
        self,
        payload_batches: List[List[Dict[str, Any]]],
        resume_id: int,
        user_id: str,
        version_num: int = 1,
        collection: str = "careeros_resumes",
    ) -> Dict[str, Any]:
        """
        Index multiple batches with partial failure recovery.

        Each batch is independently retried. Failures in one batch do
        not prevent other batches from succeeding. Failed batches are
        sent to the dead-letter queue.
        """
        if not payload_batches:
            return {
                "chunks_indexed": 0,
                "batches_processed": 0,
                "failed_batches": 0,
                "status": "skip",
            }

        total_indexed = 0
        total_batches = len(payload_batches)
        failed_batches = 0
        errors: List[str] = []
        overall_start = time.monotonic()

        for batch_idx, batch_payloads in enumerate(payload_batches):
            try:
                result = await self.index_with_retries(
                    payloads=batch_payloads,
                    resume_id=resume_id,
                    user_id=user_id,
                    version_num=version_num,
                    collection=collection,
                )
                total_indexed += result.get("chunks_indexed", 0)
                INDEXING_PARTIAL_BATCH.labels(collection=collection).inc()

            except Exception as e:
                failed_batches += 1
                errors.append(f"Batch {batch_idx}: {e}")
                logger.error(f"Batch {batch_idx} failed permanently: {e}")

        elapsed = (time.monotonic() - overall_start) * 1000
        status = "partial" if failed_batches > 0 else "success"

        result = {
            "chunks_indexed": total_indexed,
            "batches_processed": total_batches - failed_batches,
            "failed_batches": failed_batches,
            "total_batches": total_batches,
            "total_latency_ms": round(elapsed, 2),
            "collection": collection,
            "status": status,
        }

        if errors:
            result["errors"] = errors

        return result

    def _dead_letter_enqueue(
        self,
        payloads: List[Dict[str, Any]],
        resume_id: int,
        user_id: str,
        version_num: int,
        collection: str,
        error: str,
    ) -> None:
        """
        Dead-letter preparation hook for permanently failed indexing.

        Logs structured dead-letter metadata for async replay.
        Future integration point: Redis/message-queue dead-letter store.
        """
        INDEXING_DEAD_LETTER.labels(collection=collection).inc()

        dead_letter = {
            "resume_id": resume_id,
            "user_id": user_id,
            "version_num": version_num,
            "collection": collection,
            "chunk_count": len(payloads),
            "chunk_ids": [p.get("chunk_id", "unknown") for p in payloads],
            "error": error,
        }
        logger.error(
            f"DEAD_LETTER: indexing dead-letter enqueued — {len(payloads)} chunks "
            f"for resume {resume_id}, collection '{collection}': {error}"
        )
        # Integration point: publish to Redis dead-letter stream
        # e.g., redis.xadd("dead_letter:embedding:indexing", dead_letter)

    def _build_points(
        self,
        payloads: List[Dict[str, Any]],
        vectors: List[List[float]],
        resume_id: int,
        user_id: str,
        version_num: int,
    ) -> List[PointStruct]:
        """Build Qdrant PointStructs from payloads and vectors."""
        points = []

        for i, payload in enumerate(payloads):
            chunk_id = payload.get("chunk_id", str(uuid.uuid4())[:16])
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_OID,
                    f"resume_{resume_id}_v{version_num}_chunk_{i}",
                )
            )

            # Enrich payload with Qdrant-required fields
            enriched_payload = {
                "user_id": user_id,
                "resume_id": resume_id,
                "version_num": version_num,
                "chunk_index": i,
                "text": payload.get("text", ""),
                "chunk_id": chunk_id,
                "document_id": f"resume_{resume_id}",
                "source": payload.get("metadata", {}).get("source", "careeros_resumes"),
                "section": payload.get("metadata", {}).get("section", "general"),
                "chunk_type": payload.get("metadata", {}).get("chunk_type", "general"),
                "has_overlap": payload.get("metadata", {}).get("has_overlap", False),
                "model": "nvidia/nv-embed-v1",
                "metadata": payload.get("metadata", {}),
                "retrieval_metadata": payload.get("retrieval_metadata", {}),
            }

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vectors[i],
                    payload=enriched_payload,
                )
            )

        return points

    # ── Delete by Resume ─────────────────────────────────────────────

    async def delete_resume_vectors(
        self, resume_id: int, collection: str = "careeros_resumes"
    ) -> bool:
        """Remove all vectors for a specific resume."""
        return await get_qdrant_service().delete_by_filter(
            collection_name=collection,
            filter_kwargs={"resume_id": resume_id},
        )

    # ── LangGraph Node Interface ─────────────────────────────────────

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node entry point for indexing.

        Reads embedding_payloads from state, indexes them, writes result.

        Args:
            state: ProcessingState dict

        Returns:
            State update dict
        """
        payloads = state.get("embedding_payloads")
        resume_id = state.get("resume_id")
        user_id = state.get("user_id", "unknown")
        version_id = state.get("version_id", 1)

        if not payloads:
            return {
                "indexing_error": "No embedding payloads to index",
                "status": ProcessingStatus.FAILED,
            }

        try:
            result = await self.index_with_retries(
                payloads=payloads,
                resume_id=resume_id,
                user_id=user_id,
                version_num=version_id,
                collection="careeros_resumes",
            )

            return {
                "indexing_result": result,
                "indexing_error": None,
                "status": ProcessingStatus.COMPLETED,
            }

        except Exception as e:
            return {
                "indexing_result": None,
                "indexing_error": str(e),
                "status": ProcessingStatus.FAILED,
            }


_indexing_pipeline = None


def get_indexing_pipeline() -> IndexingPipeline:
    global _indexing_pipeline
    if _indexing_pipeline is None:
        _indexing_pipeline = IndexingPipeline()
    return _indexing_pipeline


def reset_indexing_pipeline() -> None:
    global _indexing_pipeline
    _indexing_pipeline = None


def __getattr__(name: str):
    if name == "indexing_pipeline":
        return get_indexing_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
