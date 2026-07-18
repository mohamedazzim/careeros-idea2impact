"""
Embedding preparation pipeline.
Transforms semantic chunks into NV-Embed-v1-ready payloads with
metadata enrichment and retrieval optimization metadata.

Stateless, async-safe, retry-safe, observable.
LangGraph node compatible.
"""
import asyncio
import hashlib
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List

from src.observability.metrics import (
    EMBED_PREP_COUNT,
    EMBED_PREP_LATENCY,
    EMBED_PAYLOAD_COUNT,
    EMBED_SECTION_DISTRIBUTION,
)
from .interfaces import (
    EmbeddingPayload,
    EmbeddingBatch,
    EmbeddingResult,
    ProcessingStatus,
    RetryablePipelineError,
)

logger = logging.getLogger(__name__)

_EMBED_PREP_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="embed-prep-")

# ── Retrieval Strategy Configuration ────────────────────────────────

SECTION_RETRIEVAL_WEIGHTS: Dict[str, float] = {
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

# ── Embedding Text Templates ────────────────────────────────────────

SECTION_PREFIX_TEMPLATES: Dict[str, str] = {
    "experience": "Work experience: ",
    "education": "Education: ",
    "skills": "Skills: ",
    "summary": "Professional summary: ",
    "projects": "Project: ",
    "certifications": "Certification: ",
    "awards": "Award: ",
    "languages": "Language: ",
    "publications": "Publication: ",
    "contact": "Contact: ",
    "general": "",
    "preamble": "",
}


class EmbeddingPreparationPipeline:
    """
    Production-grade embedding preparation pipeline.

    Capabilities:
    - Transforms semantic chunks into NV-Embed-v1 payloads
    - Metadata enrichment (section, position, retrieval weight, boundaries)
    - Retrieval optimization metadata (weights, reranking hints)
    - Section-prefixed embedding text for improved semantic search
    - Batched payload organization
    - Deterministic chunk identification
    """

    DEFAULT_BATCH_SIZE = 100

    async def prepare(
        self,
        chunks: List[Dict[str, Any]],
        resume_id: int,
        user_id: str,
        version_num: int = 1,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> EmbeddingResult:
        """
        Prepare chunks for embedding generation.

        Args:
            chunks: Semantic chunks (from chunking pipeline)
            resume_id: Parent resume ID
            user_id: User identifier
            version_num: Resume version number
            batch_size: Maximum chunks per batch

        Returns:
            EmbeddingResult with EmbeddingBatch ready for NV-Embed-v1
        """
        if not chunks:
            raise RetryablePipelineError("No chunks provided for embedding preparation")

        start = time.monotonic()
        logger.info(f"Preparing embeddings for {len(chunks)} chunks (resume: {resume_id})")

        try:
            loop = asyncio.get_event_loop()

            batch = await loop.run_in_executor(
                _EMBED_PREP_EXECUTOR,
                self._prepare_sync,
                chunks,
                resume_id,
                user_id,
                version_num,
            )

            elapsed = time.monotonic() - start

            EMBED_PREP_COUNT.labels(status="success").inc()
            EMBED_PREP_LATENCY.observe(elapsed)
            EMBED_PAYLOAD_COUNT.observe(len(batch.payloads))

            for section, count in batch.section_distribution.items():
                EMBED_SECTION_DISTRIBUTION.labels(section=section).inc(count)

            result = EmbeddingResult(
                batch=batch,
                model="nvidia/nv-embed-v1",
                dimensions=4096,
                metadata={
                    "resume_id": resume_id,
                    "user_id": user_id,
                    "version_num": version_num,
                    "preparation_duration_ms": round(elapsed * 1000, 2),
                    "retrieval_strategy": batch.retrieval_strategy,
                },
            )

            logger.info(
                "Embedding preparation complete",
                extra={
                    "total_chunks": batch.total_chunks,
                    "total_tokens": batch.total_tokens,
                    "avg_chunk_tokens": round(batch.avg_chunk_tokens, 1),
                    "section_distribution": batch.section_distribution,
                },
            )

            return result

        except Exception as e:
            EMBED_PREP_COUNT.labels(status="error").inc()
            logger.error(f"Embedding preparation failed: {e}")
            raise RetryablePipelineError(f"Embedding preparation failed: {e}")

    def _prepare_sync(
        self,
        chunks: List[Dict[str, Any]],
        resume_id: int,
        user_id: str,
        version_num: int,
    ) -> EmbeddingBatch:
        """Synchronous payload preparation."""
        payloads: List[EmbeddingPayload] = []
        total_tokens = 0
        section_dist: Dict[str, int] = {}

        for i, chunk_data in enumerate(chunks):
            chunk = self._normalize_chunk(chunk_data, i)

            section = chunk.get("section", "general")
            section_dist[section] = section_dist.get(section, 0) + 1

            # Build embedding text with section prefix for better retrieval
            embedding_text = self._build_embedding_text(
                chunk.get("text", ""), section
            )

            # Build metadata
            metadata = {
                "resume_id": resume_id,
                "user_id": user_id,
                "version_num": version_num,
                "chunk_index": i,
                "section": section,
                "chunk_type": chunk.get("chunk_type", "general"),
                "char_start": chunk.get("char_start", 0),
                "char_end": chunk.get("char_end", 0),
                "word_count": chunk.get("word_count", 0),
                "sentence_count": chunk.get("sentence_count", 0),
                "has_overlap": chunk.get("overlap_with_previous", False),
            }

            # Add any existing chunk metadata
            if isinstance(chunk.get("metadata"), dict):
                metadata.update(chunk["metadata"])

            # Build retrieval metadata for optimization
            retrieval_metadata = self._build_retrieval_metadata(
                chunk, section, i, len(chunks)
            )

            # Generate deterministic chunk ID
            chunk_id = self._generate_payload_id(
                resume_id, version_num, i, embedding_text
            )

            payloads.append(
                EmbeddingPayload(
                    chunk_id=chunk_id,
                    text=chunk.get("text", ""),
                    embedding_text=embedding_text,
                    input_type="passage",
                    metadata=metadata,
                    retrieval_metadata=retrieval_metadata,
                )
            )

            total_tokens += chunk.get("token_count", 0)

        avg_tokens = total_tokens / len(payloads) if payloads else 0.0

        return EmbeddingBatch(
            payloads=payloads,
            batch_id=str(uuid.uuid4()),
            total_chunks=len(payloads),
            total_tokens=total_tokens,
            avg_chunk_tokens=round(avg_tokens, 1),
            section_distribution=section_dist,
            retrieval_strategy="semantic",
        )

    def _normalize_chunk(self, chunk_data: Dict[str, Any], index: int) -> Dict[str, Any]:
        """
        Normalize chunk data from various sources into a uniform format.
        Handles both dict chunks and SerializedChunk objects.
        """
        if isinstance(chunk_data, dict):
            return {
                "text": chunk_data.get("text", ""),
                "section": chunk_data.get("section", "general"),
                "chunk_type": chunk_data.get("chunk_type", "general"),
                "char_start": chunk_data.get("char_start", 0),
                "char_end": chunk_data.get("char_end", 0),
                "word_count": chunk_data.get("word_count", len(chunk_data.get("text", "").split())),
                "sentence_count": chunk_data.get("sentence_count", 1),
                "token_count": chunk_data.get("token_count", 0),
                "overlap_with_previous": chunk_data.get("overlap_with_previous", False),
                "overlap_with_next": chunk_data.get("overlap_with_next", False),
                "metadata": chunk_data.get("metadata", {}),
            }
        # Handle if it's a dataclass or other object
        if hasattr(chunk_data, "to_dict"):
            return chunk_data.to_dict()
        return {
            "text": str(chunk_data),
            "section": "general",
            "chunk_type": "general",
            "char_start": 0,
            "char_end": len(str(chunk_data)),
            "word_count": len(str(chunk_data).split()),
            "sentence_count": 1,
            "token_count": 0,
            "overlap_with_previous": False,
            "overlap_with_next": False,
            "metadata": {},
        }

    def _build_embedding_text(self, text: str, section: str) -> str:
        """
        Build optimized embedding text with section prefix.

        Adding section context as a prefix helps NV-Embed-v1
        better understand the semantic domain of the chunk,
        improving retrieval relevance.
        """
        prefix = SECTION_PREFIX_TEMPLATES.get(section, "")
        if prefix:
            return f"{prefix}{text}"
        return text

    def _build_retrieval_metadata(
        self,
        chunk: Dict[str, Any],
        section: str,
        chunk_index: int,
        total_chunks: int,
    ) -> Dict[str, Any]:
        """
        Build retrieval optimization metadata.

        Includes:
        - Section weight for boosted scoring
        - Position-based relevance score
        - Overlap hints for chunk stitching
        - Boundary indicators
        """
        weight = SECTION_RETRIEVAL_WEIGHTS.get(section, 0.5)

        # Position score: earlier chunks get higher weight
        # Weighted towards first 30% of document
        position_ratio = 1.0 - (chunk_index / max(total_chunks, 1))
        if chunk_index < total_chunks * 0.3:
            position_score = 1.0
        elif chunk_index < total_chunks * 0.7:
            position_score = 0.8
        else:
            position_score = 0.5

        retrieval_score = weight * position_score

        return {
            "section_weight": weight,
            "position_ratio": round(position_ratio, 3),
            "position_score": round(position_score, 3),
            "retrieval_score": round(retrieval_score, 3),
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "has_overlap_prev": chunk.get("overlap_with_previous", False),
            "has_overlap_next": chunk.get("overlap_with_next", False),
            "retrieval_strategy": "semantic",
            "reranking_hints": {
                "boost_experience": section == "experience",
                "boost_skills": section == "skills",
                "is_summary": section == "summary",
                "first_chunk": chunk_index == 0,
                "last_chunk": chunk_index == total_chunks - 1,
            },
        }

    def _generate_payload_id(
        self,
        resume_id: int,
        version_num: int,
        chunk_index: int,
        text: str,
    ) -> str:
        """Generate deterministic payload ID."""
        hasher = hashlib.sha256()
        hasher.update(f"{resume_id}:v{version_num}:chunk{chunk_index}".encode())
        hasher.update(text.encode("utf-8", errors="ignore"))
        return hasher.hexdigest()[:16]

    # ── LangGraph Node Interface ─────────────────────────────────────

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node entry point for embedding preparation.

        Args:
            state: ProcessingState dict

        Returns:
            State update dict with embedding_payloads and embedding_batch
        """
        # Get chunks from semantic_chunks or chunks
        chunks = (
            state.get("semantic_chunks")
            or state.get("chunks")
        )

        if not chunks:
            return {
                "embedding_payloads": None,
                "embedding_error": "No chunks available for embedding preparation",
                "status": ProcessingStatus.FAILED,
            }

        resume_id = state.get("resume_id", 0)
        user_id = state.get("user_id", "unknown")
        version_id = state.get("version_id", 1)

        try:
            result = await self.prepare(
                chunks=chunks,
                resume_id=resume_id,
                user_id=user_id,
                version_num=version_id,
            )

            return {
                "embedding_payloads": [p.to_dict() for p in result.batch.payloads],
                "embedding_batch": result.batch.to_dict(),
                "embedding_error": None,
                "status": ProcessingStatus.EMBEDDING,
            }

        except RetryablePipelineError as e:
            return {
                "embedding_payloads": None,
                "embedding_error": str(e),
                "status": ProcessingStatus.PREPARING,
            }


embedding_preparation_pipeline = EmbeddingPreparationPipeline()
