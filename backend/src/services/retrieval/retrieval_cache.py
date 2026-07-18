"""
Multi-level retrieval cache layer with Redis backing.

Caches query-results, rerank scores, context assembly, routing decisions,
and query understanding results. Cache invalidation via configurable TTLs
per cache level. Version-aware cache keys for automatic invalidation.

Stateless, async-safe, observable. Worker-safe.
"""
import hashlib
import json
import logging
from typing import Dict, Any, Optional

from src.db.redis import get_redis
from src.core.config import settings
from src.observability.metrics import (
    RETRIEVAL_CACHE_HIT,
    RETRIEVAL_CACHE_MISS,
    RETRIEVAL_CACHE_WRITE,
)

logger = logging.getLogger(__name__)

PREFIX = settings.RETRIEVAL_CACHE_KEY_PREFIX

# Embedding version tag for version-aware keys (bumped on model changes)
EMBEDDING_VERSION = "nv-embed-v1:v1"

# Per-level TTLs
TTL_QUERY = settings.RETRIEVAL_CACHE_TTL
TTL_RERANK = settings.RETRIEVAL_CACHE_TTL_RERANK
TTL_CONTEXT = settings.RETRIEVAL_CACHE_TTL_CONTEXT
TTL_ROUTING = settings.RETRIEVAL_CACHE_TTL_ROUTING
TTL_QU = settings.RETRIEVAL_CACHE_TTL_QUERY_UNDERSTANDING


def _invalidation_tag() -> str:
    """Global tag bumped on reindex/version changes for query cache keys."""
    return f"{EMBEDDING_VERSION}:reindex-epoch"


def _cache_key(level: str, content: str, extra: str = "") -> str:
    """Deterministic cache key with invalidation tag for version-aware keys."""
    digest = content + (extra or "")
    h = hashlib.sha256(digest.encode("utf-8", errors="ignore")).hexdigest()[:16]
    tag = _invalidation_tag() if level in ("query", "rerank", "context") else ""
    suffix = f":{hashlib.sha256(tag.encode()).hexdigest()[:8]}" if tag else ""
    return f"{PREFIX}{level}:{h}{suffix}"


class RetrievalCache:
    """Multi-level retrieval cache backed by Redis."""

    def __init__(self):
        self._enabled = settings.RETRIEVAL_CACHE_ENABLED

    async def get(self, key: str) -> Optional[Any]:
        if not self._enabled:
            return None
        try:
            redis = await get_redis()
            data = await redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.debug(f"Cache read failed: {e}")
        return None

    async def set(
        self, key: str, value: Any, ttl: int = TTL_QUERY
    ) -> bool:
        if not self._enabled:
            return False
        try:
            redis = await get_redis()
            await redis.setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.debug(f"Cache write failed: {e}")
            return False

    async def invalidate_on_reindex(self, collections: Optional[list] = None) -> int:
        """Invalidate all retrieval caches after Qdrant reindexing.

        Bumps the invalidation tag in Redis so all version-aware keys
        become stale. Also flushes per-collection caches.
        """
        try:
            redis = await get_redis()
            tag_key = f"{PREFIX}__invalidation_epoch"
            await redis.incr(tag_key)
            count = 0
            if collections:
                for coll in collections:
                    count += await self.invalidate_collection(coll)
            else:
                count = await self.invalidate_all()
            logger.info(
                f"Cache invalidated after reindex: {count} keys flushed "
                f"(collections={collections})"
            )
            return count
        except Exception as e:
            logger.error(f"Reindex invalidation failed: {e}")
            return 0

    async def delete(self, key: str) -> bool:
        try:
            redis = await get_redis()
            await redis.delete(key)
            return True
        except Exception:
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern. Returns count deleted."""
        try:
            redis = await get_redis()
            keys = await redis.keys(pattern + "*")
            if keys:
                await redis.delete(*keys)
            return len(keys)
        except Exception:
            return 0

    # ── Convenience methods per cache level ─────────────────────────

    # Query-level: cache for final hybrid retrieval results
    def query_key(self, query: str, collection: str, top_k: int) -> str:
        return _cache_key("query", f"{query}|{collection}|{top_k}")

    async def get_query(self, query: str, collection: str, top_k: int) -> Optional[Dict]:
        result = await self.get(self.query_key(query, collection, top_k))
        if result is not None:
            RETRIEVAL_CACHE_HIT.labels(level="query").inc()
        else:
            RETRIEVAL_CACHE_MISS.labels(level="query").inc()
        return result

    async def set_query(self, query: str, collection: str, top_k: int,
                        result: Dict, ttl: int = TTL_QUERY) -> bool:
        ok = await self.set(self.query_key(query, collection, top_k), result, ttl)
        if ok:
            RETRIEVAL_CACHE_WRITE.labels(level="query").inc()
        return ok

    # Rerank-level
    def rerank_key(self, query: str, chunks_hash: str) -> str:
        return _cache_key("rerank", f"{query}|{chunks_hash}")

    async def get_rerank(self, query: str, chunks_hash: str) -> Optional[Dict]:
        result = await self.get(self.rerank_key(query, chunks_hash))
        if result is not None:
            RETRIEVAL_CACHE_HIT.labels(level="rerank").inc()
        else:
            RETRIEVAL_CACHE_MISS.labels(level="rerank").inc()
        return result

    async def set_rerank(self, query: str, chunks_hash: str,
                         result: Dict, ttl: int = TTL_RERANK) -> bool:
        ok = await self.set(self.rerank_key(query, chunks_hash), result, ttl)
        if ok:
            RETRIEVAL_CACHE_WRITE.labels(level="rerank").inc()
        return ok

    # Context-level
    def context_key(self, chunks_hash: str, max_tokens: int) -> str:
        return _cache_key("context", f"{chunks_hash}|{max_tokens}")

    async def get_context(self, chunks_hash: str, max_tokens: int) -> Optional[Dict]:
        result = await self.get(self.context_key(chunks_hash, max_tokens))
        if result is not None:
            RETRIEVAL_CACHE_HIT.labels(level="context").inc()
        else:
            RETRIEVAL_CACHE_MISS.labels(level="context").inc()
        return result

    async def set_context(self, chunks_hash: str, max_tokens: int,
                          result: Dict, ttl: int = TTL_CONTEXT) -> bool:
        ok = await self.set(self.context_key(chunks_hash, max_tokens), result, ttl)
        if ok:
            RETRIEVAL_CACHE_WRITE.labels(level="context").inc()
        return ok

    # Routing-level
    def routing_key(self, query: str) -> str:
        return _cache_key("routing", query)

    async def get_routing(self, query: str) -> Optional[Dict]:
        result = await self.get(self.routing_key(query))
        if result is not None:
            RETRIEVAL_CACHE_HIT.labels(level="routing").inc()
        else:
            RETRIEVAL_CACHE_MISS.labels(level="routing").inc()
        return result

    async def set_routing(self, query: str,
                          result: Dict, ttl: int = TTL_ROUTING) -> bool:
        ok = await self.set(self.routing_key(query), result, ttl)
        if ok:
            RETRIEVAL_CACHE_WRITE.labels(level="routing").inc()
        return ok

    # Query-understanding cache
    def qu_key(self, query: str) -> str:
        return _cache_key("qu", query)

    async def get_query_understanding(self, query: str) -> Optional[Dict]:
        result = await self.get(self.qu_key(query))
        if result is not None:
            RETRIEVAL_CACHE_HIT.labels(level="query_understanding").inc()
        else:
            RETRIEVAL_CACHE_MISS.labels(level="query_understanding").inc()
        return result

    async def set_query_understanding(self, query: str,
                                      result: Dict, ttl: int = TTL_QU) -> bool:
        ok = await self.set(self.qu_key(query), result, ttl)
        if ok:
            RETRIEVAL_CACHE_WRITE.labels(level="query_understanding").inc()
        return ok

    # ── Invalidation ────────────────────────────────────────────────

    async def invalidate_query(self, query: str) -> int:
        """Invalidate all cache entries for a given query."""
        count = 0
        for level in ["query", "rerank", "context", "routing", "qu"]:
            key = _cache_key(level, query)
            if await self.delete(key):
                count += 1
        return count

    async def invalidate_collection(self, collection: str) -> int:
        """Invalidate all cache entries matching a collection (bulk invalidation)."""
        return await self.delete_pattern(f"{PREFIX}query:*{collection}*")

    async def invalidate_all(self) -> int:
        """Full cache flush for retrieval namespace."""
        return await self.delete_pattern(PREFIX)


_retrieval_cache: Optional[RetrievalCache] = None


def get_retrieval_cache() -> RetrievalCache:
    global _retrieval_cache
    if _retrieval_cache is None:
        _retrieval_cache = RetrievalCache()
    return _retrieval_cache


def reset_retrieval_cache() -> None:
    global _retrieval_cache
    _retrieval_cache = None


def __getattr__(name: str):
    if name == "retrieval_cache":
        return get_retrieval_cache()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
