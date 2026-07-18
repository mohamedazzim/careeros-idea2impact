"""
Production-grade embedding service.
NV-Embed-v1 integration with async batching, retries, versioning, and Redis caching.
Stateless, async-safe, retry-safe, observable. Worker-safe.
"""
import asyncio
import hashlib
import json
import logging
import math
import time
from typing import List, Dict, Any, Optional, Tuple

from src.services.embedding.nvembed_service import get_nvembed_service
from src.services.embedding.resilience import (
    get_circuit_breaker,
    get_rate_limit_tracker,
    get_embedding_queue,
)
from src.db.redis import get_redis
from src.observability.metrics import (
    EMBED_SERVICE_CALLS,
    EMBED_SERVICE_LATENCY,
    EMBED_SERVICE_RETRIES,
    EMBED_SERVICE_BATCH_SIZE,
    EMBED_SERVICE_CACHE,
    EMBED_CIRCUIT_BREAKER_STATE,
    EMBED_RATE_LIMIT_HITS,
    EMBED_QUEUE_DEPTH,
    EMBED_QUEUE_REJECTIONS,
    EMBED_CACHE_HIT_RATIO,
)

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Production-grade embedding service.

    Capabilities:
    - Async batching with configurable batch size
    - Exponential backoff retries (max 3)
    - Redis-backed embedding cache (content hash → vector)
    - Embedding versioning (model name + dimensions)
    - Metadata-aware payload generation
    - Chunk-to-vector mapping with deterministic IDs
    - Graceful degradation when API unavailable
    """

    DEFAULT_BATCH_SIZE = 50
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0
    CACHE_TTL_SECONDS = 86400  # 24 hours
    CACHE_KEY_PREFIX = "embed:"

    def __init__(self):
        nvembed = get_nvembed_service()
        self._model_name = nvembed.model_name
        self._dimensions = nvembed.dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def generate_embeddings(
        self,
        texts: List[str],
        input_type: str = "passage",
        batch_size: Optional[int] = None,
        use_cache: bool = True,
    ) -> List[List[float]]:
        """
        Generate embeddings with batching, retries, and caching.

        Args:
            texts: List of texts to embed
            input_type: 'passage' for documents, 'query' for search
            batch_size: Max texts per API call (default 50)
            use_cache: Whether to use Redis cache

        Returns:
            List of embedding vectors (each 4096-dim)
        """
        if not texts:
            return []

        bs = batch_size or self.DEFAULT_BATCH_SIZE
        total = len(texts)

        logger.info(
            f"Generating embeddings for {total} texts (batch_size={bs}, input_type={input_type})"
        )

        # Check cache first
        if use_cache:
            cached_vectors, uncached_texts, uncached_indices = await self._check_cache(
                texts
            )
            cache_hits = total - len(uncached_indices)
            if cache_hits > 0:
                EMBED_SERVICE_CACHE.labels(result="hit").inc(cache_hits)
                logger.debug(f"Cache hits: {cache_hits}/{total}")
            # Track cache hit ratio
            if total > 0:
                EMBED_CACHE_HIT_RATIO.observe(cache_hits / total)
        else:
            cached_vectors = {}
            uncached_texts = texts
            uncached_indices = list(range(total))

        # Generate embeddings for uncached texts in batches
        if uncached_texts:
            new_vectors = await self._batch_generate(
                uncached_texts, uncached_indices, input_type, bs
            )

            # Merge with cached results
            for idx, vec in new_vectors.items():
                cached_vectors[idx] = vec

            # Cache new embeddings
            if use_cache:
                await self._cache_embeddings(
                    uncached_texts,
                    [new_vectors[i] for i in uncached_indices if i in new_vectors],
                    uncached_indices,
                )
        else:
            EMBED_SERVICE_CACHE.labels(result="hit").inc(total)

        # Return in original order
        return [cached_vectors[i] for i in range(total)]

    async def embed_query(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding for a single query.

        Args:
            text: Query text
            use_cache: Whether to use Redis cache

        Returns:
            4096-dim embedding vector
        """
        if not text:
            return []

        results = await self.generate_embeddings(
            [text], input_type="query", batch_size=1, use_cache=use_cache
        )
        return results[0] if results else []

    # ── Batch Generation with Retries ────────────────────────────────

    async def _batch_generate(
        self,
        texts: List[str],
        indices: List[int],
        input_type: str,
        batch_size: int,
    ) -> Dict[int, List[float]]:
        """Generate embeddings in batches with retry logic."""
        all_vectors: Dict[int, List[float]] = {}
        total_batches = math.ceil(len(texts) / batch_size)

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(texts))
            batch_texts = texts[start_idx:end_idx]
            batch_indices = indices[start_idx:end_idx]

            EMBED_SERVICE_BATCH_SIZE.observe(len(batch_texts))

            vectors = await self._generate_with_retries(
                batch_texts, input_type
            )

            for i, vec in enumerate(vectors):
                all_vectors[batch_indices[i]] = vec

        return all_vectors

    async def _generate_with_retries(
        self,
        texts: List[str],
        input_type: str,
    ) -> List[List[float]]:
        """Generate embeddings for a single batch with exponential backoff retries,
        circuit breaker protection, rate-limit handling, and queue backpressure."""
        last_exception = None
        cb = get_circuit_breaker()
        rl = get_rate_limit_tracker()
        queue = get_embedding_queue()

        # Backpressure: queue depth monitoring
        EMBED_QUEUE_DEPTH.observe(queue.queue_depth)

        if not await queue.acquire():
            EMBED_QUEUE_REJECTIONS.inc()
            raise RuntimeError("Embedding queue full — backpressure rejected request")

        try:
            # Rate-limit cooldown check
            if rl.is_in_cooldown:
                wait = rl.cooldown_remaining()
                EMBED_RATE_LIMIT_HITS.labels(input_type=input_type).inc()
                logger.warning(
                    f"Rate limit cooldown active — waiting {wait:.1f}s"
                )
                await asyncio.sleep(wait)

            # Circuit breaker check
            if not await cb.acquire():
                EMBED_CIRCUIT_BREAKER_STATE.labels(
                    from_state=cb.state.value, to_state=cb.state.value
                ).inc()
                raise RuntimeError("Circuit breaker open — embedding API unavailable")

            for attempt in range(self.MAX_RETRIES):
                try:
                    start = time.monotonic()
                    vectors = await get_nvembed_service().generate_embeddings(texts)
                    elapsed = time.monotonic() - start

                    cb.record_success()
                    rl.record_success()

                    EMBED_SERVICE_CALLS.labels(
                        input_type=input_type, status="success"
                    ).inc()
                    EMBED_SERVICE_LATENCY.labels(input_type=input_type).observe(elapsed)

                    return vectors

                except Exception as e:
                    last_exception = e
                    error_msg = str(e).lower()

                    # Detect rate limit (HTTP 429)
                    if "429" in error_msg or "rate limit" in error_msg or "too many requests" in error_msg:
                        cooldown = rl.record_rate_limit()
                        EMBED_RATE_LIMIT_HITS.labels(input_type=input_type).inc()
                        if attempt < self.MAX_RETRIES - 1:
                            wait = max(cooldown, self.RETRY_BASE_DELAY * (2**attempt))
                            logger.warning(
                                f"Rate limited on attempt {attempt + 1}, waiting {wait:.1f}s"
                            )
                            await asyncio.sleep(wait)
                            continue

                    cb.record_failure()
                    EMBED_SERVICE_RETRIES.labels(input_type=input_type).inc()

                    if attempt < self.MAX_RETRIES - 1:
                        delay = self.RETRY_BASE_DELAY * (2**attempt)
                        logger.warning(
                            f"Embedding attempt {attempt + 1} failed, "
                            f"retrying in {delay:.1f}s: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Embedding failed after {self.MAX_RETRIES} attempts: {e}"
                        )
                        EMBED_SERVICE_CALLS.labels(
                            input_type=input_type, status="error"
                        ).inc()

            raise ValueError(
                f"Failed to generate embeddings after {self.MAX_RETRIES} attempts: {last_exception}"
            )
        finally:
            queue.release()

    # ── Redis Caching ────────────────────────────────────────────────

    def _cache_key(self, text: str) -> str:
        """Generate deterministic cache key from text content."""
        content_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        return f"{self.CACHE_KEY_PREFIX}{self._model_name}:{content_hash}"

    async def _check_cache(
        self, texts: List[str]
    ) -> Tuple[Dict[int, List[float]], List[str], List[int]]:
        """Check Redis cache for existing embeddings. Returns cached, uncached."""
        cached: Dict[int, List[float]] = {}
        uncached_texts: List[str] = []
        uncached_indices: List[int] = []

        try:
            redis = await get_redis()
            for i, text in enumerate(texts):
                key = self._cache_key(text)
                cached_data = await redis.get(key)
                if cached_data:
                    vector = json.loads(cached_data)
                    if len(vector) == self._dimensions:
                        cached[i] = vector
                        continue
                uncached_texts.append(text)
                uncached_indices.append(i)
        except Exception as e:
            logger.warning(f"Redis cache check failed: {e} — falling back to no cache")
            EMBED_SERVICE_CACHE.labels(result="miss").inc(len(texts))
            return {}, list(texts), list(range(len(texts)))

        if uncached_indices:
            EMBED_SERVICE_CACHE.labels(result="miss").inc(len(uncached_indices))

        return cached, uncached_texts, uncached_indices

    async def _cache_embeddings(
        self,
        texts: List[str],
        vectors: List[List[float]],
        indices: List[int],
    ) -> None:
        """Store generated embeddings in Redis cache."""
        try:
            redis = await get_redis()
            pipeline = redis.pipeline()

            for text, idx in zip(texts, indices):
                if idx < len(vectors):
                    key = self._cache_key(text)
                    pipeline.setex(
                        key,
                        self.CACHE_TTL_SECONDS,
                        json.dumps(vectors[idx]),
                    )

            await pipeline.execute()
        except Exception as e:
            logger.warning(f"Failed to cache embeddings: {e}")

    # ── Payload Generation ───────────────────────────────────────────

    def generate_payload(
        self,
        chunk_text: str,
        embedding_text: str,
        chunk_index: int,
        resume_id: int,
        user_id: str,
        version_num: int,
        metadata: Optional[Dict[str, Any]] = None,
        retrieval_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate metadata-aware payload for Qdrant.

        Returns dict ready for PointStruct creation.
        """
        return {
            "user_id": user_id,
            "resume_id": resume_id,
            "version_num": version_num,
            "chunk_index": chunk_index,
            "text": chunk_text,
            "embedding_text": embedding_text,
            "source": "nv-embed-v1",
            "model": self._model_name,
            "dimensions": self._dimensions,
            "metadata": metadata or {},
            "retrieval_metadata": retrieval_metadata or {},
        }


_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """Lazily initialize and return the module-level singleton.

    Uses lazy initialization to prevent import-time side effects
    and eliminate __init__.py re-export aliasing.
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def reset_embedding_service() -> None:
    """Reset singleton for testing."""
    global _embedding_service
    _embedding_service = None


def __getattr__(name: str):
    if name == "embedding_service":
        return get_embedding_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
