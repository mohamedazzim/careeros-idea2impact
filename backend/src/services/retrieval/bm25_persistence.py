"""
BM25 sparse index persistence layer.

Redis-backed serialization for worker-safe index synchronization,
warm-restart support (no full cold-start rebuilds), and index versioning.

Stateless, async-safe, observable. Worker-safe.
"""
import json
import logging
import time
import zlib
from typing import Dict, Any, List, Optional

from src.db.redis import get_redis
from src.core.config import settings

logger = logging.getLogger(__name__)

BM25_NS = settings.BM25_REDIS_NS


def _make_key(collection: str, suffix: str = "index") -> str:
    return f"{BM25_NS}{collection}:{suffix}"


def _make_version_key(collection: str) -> str:
    return f"{BM25_NS}{collection}:version"


async def save_index(
    collection: str,
    tokenized: List[List[str]],
    doc_ids: List[str],
    doc_texts: List[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Persist a BM25 sparse index to Redis with compression and versioning.

    Tokenized corpus, doc IDs, and texts are JSON-serialized, gzip-compressed,
    and stored in Redis. An incrementing version tracks freshness across workers.
    """
    start = time.monotonic()
    try:
        redis = await get_redis()

        payload = {
            "v": 1,
            "tokenized": tokenized,
            "doc_ids": doc_ids,
            "doc_texts": doc_texts,
            "meta": metadata or {},
            "saved_at": time.time(),
            "collection": collection,
        }

        raw = json.dumps(payload).encode("utf-8")
        compressed = zlib.compress(raw, level=6)

        pipe = redis.pipeline()
        pipe.set(_make_key(collection), compressed)
        pipe.set(_make_key(collection, "texts"), json.dumps(doc_texts))
        pipe.incr(_make_version_key(collection))
        await pipe.execute()

        elapsed = (time.monotonic() - start) * 1000

        logger.info(
            f"BM25 index persisted for '{collection}': "
            f"{len(tokenized)} docs, {len(compressed)} bytes compressed "
            f"in {elapsed:.0f}ms"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to persist BM25 index for '{collection}': {e}")
        return False


async def load_index(
    collection: str,
) -> Optional[Dict[str, Any]]:
    """Load a persisted BM25 index from Redis.

    Returns dict with tokenized, doc_ids, doc_texts, metadata, version
    or None if not found.
    """
    start = time.monotonic()
    try:
        redis = await get_redis()

        compressed = await redis.get(_make_key(collection))
        if not compressed:
            return None

        raw = zlib.decompress(compressed)
        payload = json.loads(raw)

        version = await redis.get(_make_version_key(collection))
        if version:
            payload["version"] = int(version)

        elapsed = (time.monotonic() - start) * 1000

        saved_ago = time.time() - payload.get("saved_at", 0)
        staleness_flag = 1 if saved_ago > settings.BM25_STALENESS_TTL else 0

        logger.info(
            f"BM25 index loaded for '{collection}': "
            f"{len(payload.get('tokenized', []))} docs "
            f"(saved {saved_ago:.0f}s ago, staleness={staleness_flag}) "
            f"in {elapsed:.0f}ms"
        )

        return payload

    except Exception as e:
        logger.error(f"Failed to load BM25 index for '{collection}': {e}")
        return None


async def get_index_version(collection: str) -> int:
    """Get current index version number."""
    try:
        redis = await get_redis()
        version = await redis.get(_make_version_key(collection))
        return int(version) if version else 0
    except Exception:
        return 0


async def delete_index(collection: str) -> bool:
    """Delete a persisted BM25 index from Redis."""
    try:
        redis = await get_redis()
        await redis.delete(
            _make_key(collection),
            _make_key(collection, "texts"),
            _make_version_key(collection),
        )
        logger.info(f"BM25 index deleted for '{collection}'")
        return True
    except Exception as e:
        logger.error(f"Failed to delete BM25 index for '{collection}': {e}")
        return False


async def index_is_stale(collection: str) -> bool:
    """Check if the persisted index is beyond staleness TTL."""
    try:
        redis = await get_redis()
        compressed = await redis.get(_make_key(collection))
        if not compressed:
            return True
        raw = zlib.decompress(compressed)
        payload = json.loads(raw)
        saved_at = payload.get("saved_at", 0)
        return (time.time() - saved_at) > settings.BM25_STALENESS_TTL
    except Exception:
        return True
