"""
Production-grade Qdrant vector store service.
Collection lifecycle, payload schema validation, metadata indexing,
filter support, vector versioning, namespace isolation.

Stateless, async-safe, retry-safe, observable. Worker-safe.
"""
import logging
import time
from typing import List, Dict, Any, Optional, Set

from qdrant_client.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    Range,
    PayloadSchemaType,
    Distance,
    VectorParams,
    ScoredPoint,
)

from src.db.qdrant import get_qdrant, validate_qdrant_connection
from src.observability.metrics import (
    QDRANT_SERVICE_INSERTS,
    QDRANT_SERVICE_QUERIES,
    QDRANT_SERVICE_DELETES,
    QDRANT_POINTS_INSERTED,
)
from src.services.vector_store.payload_monitoring import sanitize_payload_batch

logger = logging.getLogger(__name__)


ALLOWED_COLLECTIONS = frozenset(
    [
        "careeros_resumes",
        "careeros_jobs",
        "careeros_knowledge",
        "job_opportunities",
        "careeros_rag_docs",
    ]
)

DIMENSIONS = 4096
VECTOR_DISTANCE = Distance.COSINE

# ── Payload Schemas ─────────────────────────────────────────────────

RESUME_PAYLOAD_SCHEMA: Dict[str, PayloadSchemaType] = {
    "user_id": PayloadSchemaType.KEYWORD,
    "resume_id": PayloadSchemaType.INTEGER,
    "version_num": PayloadSchemaType.INTEGER,
    "chunk_index": PayloadSchemaType.INTEGER,
    "section": PayloadSchemaType.KEYWORD,
    "chunk_type": PayloadSchemaType.KEYWORD,
    "text": PayloadSchemaType.TEXT,
    "source": PayloadSchemaType.KEYWORD,
    "model": PayloadSchemaType.KEYWORD,
    "has_overlap": PayloadSchemaType.BOOL,
}

JOB_PAYLOAD_SCHEMA: Dict[str, PayloadSchemaType] = {
    "job_id": PayloadSchemaType.KEYWORD,
    "company": PayloadSchemaType.KEYWORD,
    "title": PayloadSchemaType.TEXT,
    "text": PayloadSchemaType.TEXT,
    "source": PayloadSchemaType.KEYWORD,
    "source_provider": PayloadSchemaType.KEYWORD,
    "freshness_bucket": PayloadSchemaType.KEYWORD,
    "version_num": PayloadSchemaType.INTEGER,
}

KNOWLEDGE_PAYLOAD_SCHEMA: Dict[str, PayloadSchemaType] = {
    "document_id": PayloadSchemaType.KEYWORD,
    "category": PayloadSchemaType.KEYWORD,
    "text": PayloadSchemaType.TEXT,
    "source": PayloadSchemaType.KEYWORD,
    "version_num": PayloadSchemaType.INTEGER,
}

RAG_DOC_PAYLOAD_SCHEMA: Dict[str, PayloadSchemaType] = {
    "chunk_id": PayloadSchemaType.KEYWORD,
    "doc_name": PayloadSchemaType.KEYWORD,
    "section_title": PayloadSchemaType.KEYWORD,
    "source_path": PayloadSchemaType.KEYWORD,
    "chunk_index": PayloadSchemaType.INTEGER,
    "updated_at": PayloadSchemaType.KEYWORD,
    "content_hash": PayloadSchemaType.KEYWORD,
    "text": PayloadSchemaType.TEXT,
    "source": PayloadSchemaType.KEYWORD,
}

RESUME_REQUIRED_FIELDS: Set[str] = {"text", "chunk_index", "version_num"}
JOB_REQUIRED_FIELDS: Set[str] = {"job_id", "text"}
KNOWLEDGE_REQUIRED_FIELDS: Set[str] = {"document_id", "text"}
RAG_DOC_REQUIRED_FIELDS: Set[str] = {
    "chunk_id",
    "doc_name",
    "section_title",
    "source_path",
    "chunk_index",
    "updated_at",
    "content_hash",
    "text",
    "source",
}


class QdrantService:
    """
    Production-grade Qdrant vector store service.

    Capabilities:
    - Collection lifecycle management (create, delete, recreate, verify)
    - Payload schema validation + index enforcement
    - Metadata payload indexing (keyword, integer, text, bool)
    - Filter-based queries (exact match, range, multi-value)
    - Vector versioning (tag vectors with model + version)
    - Namespace isolation (separate collections per domain)
    - Batch point operations with retry safety
    """

    # ── Collection Lifecycle ─────────────────────────────────────────

    async def init_collections(self) -> None:
        """Initialize all required collections with payload indices."""
        await validate_qdrant_connection()

        for col_name in ALLOWED_COLLECTIONS:
            await self._ensure_collection(col_name)

    async def _ensure_collection(self, collection_name: str) -> None:
        """Create collection if not exists, with payload indices."""
        qdrant = await get_qdrant()
        try:
            collections = await qdrant.get_collections()
            existing = {c.name for c in collections.collections}
        except Exception:
            existing = set()

        if collection_name in existing:
            logger.info(f"Collection '{collection_name}' already exists")
            return

        logger.info(f"Creating collection '{collection_name}' (dim={DIMENSIONS}, dist={VECTOR_DISTANCE})")
        await qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=DIMENSIONS, distance=VECTOR_DISTANCE),
        )

        # Create payload indices for efficient filtering
        await self._create_payload_indices(collection_name)

    async def _create_payload_indices(self, collection_name: str) -> None:
        """Create payload indices based on collection schema."""
        schemas = {
            "careeros_resumes": RESUME_PAYLOAD_SCHEMA,
            "careeros_jobs": JOB_PAYLOAD_SCHEMA,
            "job_opportunities": JOB_PAYLOAD_SCHEMA,
            "careeros_knowledge": KNOWLEDGE_PAYLOAD_SCHEMA,
            "careeros_rag_docs": RAG_DOC_PAYLOAD_SCHEMA,
        }
        schema = schemas.get(collection_name)
        if not schema:
            return

        qdrant = await get_qdrant()
        for field_name, field_type in schema.items():
            try:
                await qdrant.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                )
            except Exception as e:
                logger.warning(
                    f"Could not create index for {collection_name}.{field_name}: {e}"
                )

    async def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists."""
        qdrant = await get_qdrant()
        try:
            collections = await qdrant.get_collections()
            return collection_name in {c.name for c in collections.collections}
        except Exception:
            return False

    async def delete_collection(self, collection_name: str) -> None:
        """Delete a collection if it exists."""
        qdrant = await get_qdrant()
        try:
            if await self.collection_exists(collection_name):
                await qdrant.delete_collection(collection_name=collection_name)
                QDRANT_SERVICE_DELETES.labels(collection=collection_name).inc()
                logger.info(f"Deleted collection '{collection_name}'")
        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")

    async def recreate_collection(self, collection_name: str) -> None:
        """Drop and recreate a collection."""
        await self.delete_collection(collection_name)
        await self._ensure_collection(collection_name)

    # ── Point Operations ─────────────────────────────────────────────

    async def upsert_points(
        self,
        collection_name: str,
        points: List[PointStruct],
        validate: bool = True,
    ) -> int:
        """
        Upsert points with optional payload validation.

        Returns number of points upserted.
        """
        if collection_name not in ALLOWED_COLLECTIONS:
            raise ValueError(f"Unknown collection: {collection_name}")

        if not points:
            return 0

        if validate:
            self._validate_payloads(collection_name, points)

        # Payload size monitoring and sanitization
        payloads = [point.payload or {} for point in points]
        sanitized_payloads = sanitize_payload_batch(payloads, collection=collection_name)
        for point, sanitized in zip(points, sanitized_payloads):
            point.payload = sanitized

        start = time.monotonic()
        qdrant = await get_qdrant()

        try:
            await qdrant.upsert(
                collection_name=collection_name,
                points=points,
            )
            elapsed = time.monotonic() - start
            QDRANT_SERVICE_INSERTS.labels(
                collection=collection_name, status="success"
            ).inc()
            QDRANT_POINTS_INSERTED.labels(collection=collection_name).observe(
                len(points)
            )
            logger.info(
                f"Upserted {len(points)} points to '{collection_name}' "
                f"in {elapsed*1000:.1f}ms"
            )
            return len(points)

        except Exception as e:
            QDRANT_SERVICE_INSERTS.labels(
                collection=collection_name, status="error"
            ).inc()
            logger.error(
                f"Failed to upsert points to '{collection_name}': {e}"
            )
            raise

    async def delete_points(
        self,
        collection_name: str,
        point_ids: List[str],
    ) -> bool:
        """Delete points by ID."""
        if not point_ids:
            return True
        try:
            qdrant = await get_qdrant()
            await qdrant.delete(
                collection_name=collection_name,
                points_selector=point_ids,
            )
            QDRANT_SERVICE_DELETES.labels(collection=collection_name).inc()
            return True
        except Exception as e:
            logger.error(f"Failed to delete points: {e}")
            return False

    async def delete_by_filter(
        self,
        collection_name: str,
        filter_kwargs: Dict[str, Any],
    ) -> bool:
        """Delete points matching a filter."""
        try:
            qdrant = await get_qdrant()
            qdrant_filter = self._build_filter(filter_kwargs)
            await qdrant.delete(
                collection_name=collection_name,
                points_selector=qdrant_filter,
            )
            QDRANT_SERVICE_DELETES.labels(collection=collection_name).inc()
            return True
        except Exception as e:
            logger.error(f"Failed to delete by filter: {e}")
            return False

    # ── Query Operations ─────────────────────────────────────────────

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        filter_kwargs: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        score_threshold: Optional[float] = None,
        with_payload: bool = True,
    ) -> List[ScoredPoint]:
        """
        Semantic similarity search with optional metadata filters.

        Args:
            collection_name: Target collection
            query_vector: 4096-dim query embedding
            filter_kwargs: Metadata filters (exact match by default)
            limit: Max results
            score_threshold: Minimum cosine similarity score
            with_payload: Include payload in results
        """
        if collection_name not in ALLOWED_COLLECTIONS:
            raise ValueError(f"Unknown collection: {collection_name}")

        start = time.monotonic()
        qdrant = await get_qdrant()

        qdrant_filter = self._build_filter(filter_kwargs) if filter_kwargs else None

        try:
            response = await qdrant.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=with_payload,
            )
            results = list(response.points) if hasattr(response, 'points') else list(response)
            elapsed = time.monotonic() - start
            QDRANT_SERVICE_QUERIES.labels(collection=collection_name).inc()
            logger.debug(
                f"Search '{collection_name}': {len(results)} results in {elapsed*1000:.1f}ms"
            )
            return results

        except Exception as e:
            QDRANT_SERVICE_QUERIES.labels(collection=collection_name).inc()
            logger.error(f"Search failed on '{collection_name}': {e}")
            raise

    async def search_with_section_waiting(
        self,
        collection_name: str,
        query_vector: List[float],
        section_weights: Dict[str, float],
        filter_kwargs: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        oversample_multiplier: int = 3,
    ) -> List[ScoredPoint]:
        """
        Section-aware retrieval with oversampling and section-weighted reranking.

        Retrieves oversample_multiplier × limit results, then reweights by
        section weight from payload metadata.
        """
        oversample_limit = limit * oversample_multiplier

        results = await self.search(
            collection_name=collection_name,
            query_vector=query_vector,
            filter_kwargs=filter_kwargs,
            limit=oversample_limit,
        )

        # Reweight by section
        weighted = []
        for r in results:
            payload = r.payload or {}
            section = payload.get("metadata", {}).get("section", payload.get("section", "general"))
            weight = section_weights.get(section, 0.5)
            adjusted_score = r.score * weight
            weighted.append((adjusted_score, r))

        # Rescore and trim
        weighted.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in weighted[:limit]]

    # ── Filter Building ──────────────────────────────────────────────

    def _build_filter(
        self, filter_kwargs: Dict[str, Any]
    ) -> Optional[Filter]:
        """
        Build Qdrant filter from keyword args.

        Supports:
        - Exact match: {"user_id": "abc"}
        - Multi-value: {"section": ["experience", "skills"]} → OR
        - Range: {"chunk_index": {"gte": 0, "lte": 10}}
        - Combined: all conditions joined with AND
        """
        if not filter_kwargs:
            return None

        conditions = []
        for key, value in filter_kwargs.items():
            if value is None:
                continue

            if isinstance(value, list):
                conditions.append(
                    FieldCondition(key=key, match=MatchAny(any=value))
                )
            elif isinstance(value, dict) and ("gte" in value or "lte" in value):
                conditions.append(
                    FieldCondition(key=key, range=Range(**value))
                )
            else:
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )

        return Filter(must=conditions) if conditions else None

    # ── Payload Validation ───────────────────────────────────────────

    def _validate_payloads(
        self, collection_name: str, points: List[PointStruct]
    ) -> None:
        """Validate payloads against collection schema."""
        required = {
            "careeros_resumes": RESUME_REQUIRED_FIELDS,
            "careeros_jobs": JOB_REQUIRED_FIELDS,
            "careeros_knowledge": KNOWLEDGE_REQUIRED_FIELDS,
            "careeros_rag_docs": RAG_DOC_REQUIRED_FIELDS,
        }.get(collection_name, set())

        for point in points:
            payload = point.payload or {}
            missing = required - set(payload.keys())
            if missing:
                raise ValueError(
                    f"Missing required fields in {collection_name} payload: {missing}"
                )

            if not point.vector or len(point.vector) != DIMENSIONS:
                raise ValueError(
                    f"Invalid vector dimension for {collection_name}: "
                    f"expected {DIMENSIONS}"
                )

    # ── Collection Statistics ────────────────────────────────────────

    async def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get collection metadata and point count."""
        qdrant = await get_qdrant()
        try:
            info = await qdrant.get_collection(collection_name)
            return {
                "name": collection_name,
                "vectors_count": getattr(info, "vectors_count", 0),
                "points_count": getattr(info, "points_count", 0),
                "indexed_vectors_count": getattr(info, "indexed_vectors_count", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get collection info for '{collection_name}': {e}")
            return {"name": collection_name, "error": str(e)}


_qdrant_service = None


def get_qdrant_service() -> QdrantService:
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service


def reset_qdrant_service() -> None:
    global _qdrant_service
    _qdrant_service = None


def __getattr__(name: str):
    if name == "qdrant_service":
        return get_qdrant_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
