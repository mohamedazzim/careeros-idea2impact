"""Phase 6 — Execution Queues.

Priority, retry, and dead-letter queue implementations for orchestration jobs.
Redis-backed with poison message handling and replay.
"""

import json
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from src.core.config import settings

logger = logging.getLogger(__name__)

PRIORITY_QUEUE_KEY = "orch:queue:priority"
RETRY_QUEUE_KEY = "orch:queue:retry"
DEAD_LETTER_QUEUE_KEY = "orch:queue:dead_letter"


@dataclass
class QueueItem:
    item_id: str
    session_uid: str
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 50
    attempt: int = 0
    max_attempts: int = 3
    enqueued_at: float = field(default_factory=time.time)
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "session_uid": self.session_uid,
            "payload": self.payload,
            "priority": self.priority,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "enqueued_at": self.enqueued_at,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueItem":
        return cls(**data)


class PriorityQueue:
    """Redis-backed priority queue for orchestration jobs."""

    async def enqueue(self, item: QueueItem) -> str:
        try:
            from src.db.redis import redis_client
            await redis_client.zadd(
                PRIORITY_QUEUE_KEY,
                {item.item_id: item.priority},
            )
            detail_key = f"{PRIORITY_QUEUE_KEY}:{item.item_id}"
            await redis_client.setex(detail_key, 3600, json.dumps(item.to_dict()))
            return item.item_id
        except Exception as exc:
            logger.error(f"Priority enqueue failed: {exc}")
            return ""

    async def dequeue(self) -> Optional[QueueItem]:
        try:
            from src.db.redis import redis_client
            results = await redis_client.zpopmax(PRIORITY_QUEUE_KEY, count=1)
            if not results:
                return None
            item_id, score = results[0]
            detail_key = f"{PRIORITY_QUEUE_KEY}:{item_id}"
            raw = await redis_client.get(detail_key)
            if raw:
                await redis_client.delete(detail_key)
                return QueueItem.from_dict(json.loads(raw))
        except Exception as exc:
            logger.error(f"Priority dequeue failed: {exc}")
        return None

    async def peek(self, limit: int = 10) -> List[QueueItem]:
        try:
            from src.db.redis import redis_client
            results = await redis_client.zrevrange(PRIORITY_QUEUE_KEY, 0, limit - 1, withscores=True)
            items = []
            for item_id, score in results:
                detail_key = f"{PRIORITY_QUEUE_KEY}:{item_id}"
                raw = await redis_client.get(detail_key)
                if raw:
                    items.append(QueueItem.from_dict(json.loads(raw)))
            return items
        except Exception:
            return []

    async def size(self) -> int:
        try:
            from src.db.redis import redis_client
            return await redis_client.zcard(PRIORITY_QUEUE_KEY) or 0
        except Exception:
            return 0


class RetryQueue:
    """Redis-backed retry queue with delayed retry support."""

    async def enqueue(self, item: QueueItem) -> str:
        try:
            from src.db.redis import redis_client
            item.attempt += 1
            item.enqueued_at = time.time()
            score = time.time() + (2 ** min(item.attempt, 5))
            await redis_client.zadd(RETRY_QUEUE_KEY, {item.item_id: score})
            detail_key = f"{RETRY_QUEUE_KEY}:{item.item_id}"
            await redis_client.setex(detail_key, 3600, json.dumps(item.to_dict()))
            return item.item_id
        except Exception as exc:
            logger.error(f"Retry enqueue failed: {exc}")
            return ""

    async def pop_ready(self, limit: int = 10) -> List[QueueItem]:
        try:
            from src.db.redis import redis_client
            now = time.time()
            results = await redis_client.zrangebyscore(RETRY_QUEUE_KEY, 0, now, start=0, num=limit)
            items = []
            for item_id in results:
                detail_key = f"{RETRY_QUEUE_KEY}:{item_id}"
                raw = await redis_client.get(detail_key)
                if raw:
                    items.append(QueueItem.from_dict(json.loads(raw)))
                    await redis_client.zrem(RETRY_QUEUE_KEY, str(item_id))
                    await redis_client.delete(detail_key)
            return items
        except Exception:
            return []

    async def size(self) -> int:
        try:
            from src.db.redis import redis_client
            return await redis_client.zcard(RETRY_QUEUE_KEY) or 0
        except Exception:
            return 0


class DeadLetterQueue:
    """Redis-backed dead-letter queue for permanently failed orchestrations."""

    async def enqueue(self, item: QueueItem, reason: str = "unknown") -> str:
        try:
            from src.db.redis import redis_client
            item.last_error = reason
            await redis_client.zadd(DEAD_LETTER_QUEUE_KEY, {item.item_id: time.time()})
            detail_key = f"{DEAD_LETTER_QUEUE_KEY}:{item.item_id}"
            await redis_client.setex(detail_key, 86400, json.dumps(item.to_dict()))
            from src.observability.metrics import EVENT_BUS_QUEUE_DEPTH_GAUGE
            EVENT_BUS_QUEUE_DEPTH_GAUGE.set(await self.size())
            logger.warning(f"Dead-lettered {item.session_uid}: {reason}")
            return item.item_id
        except Exception as exc:
            logger.error(f"Dead-letter enqueue failed: {exc}")
            return ""

    async def list(self, limit: int = 50) -> List[QueueItem]:
        try:
            from src.db.redis import redis_client
            results = await redis_client.zrevrange(DEAD_LETTER_QUEUE_KEY, 0, limit - 1, withscores=True)
            items = []
            for item_id, score in results:
                detail_key = f"{DEAD_LETTER_QUEUE_KEY}:{item_id}"
                raw = await redis_client.get(detail_key)
                if raw:
                    items.append(QueueItem.from_dict(json.loads(raw)))
            return items
        except Exception:
            return []

    async def replay(self, item_id: str) -> Optional[QueueItem]:
        """Replay a dead-lettered item back to the retry queue."""
        try:
            from src.db.redis import redis_client
            from src.runtime.queues import RetryQueue
            detail_key = f"{DEAD_LETTER_QUEUE_KEY}:{item_id}"
            raw = await redis_client.get(detail_key)
            if not raw:
                return None
            item = QueueItem.from_dict(json.loads(raw))
            item.attempt = 0
            await redis_client.zrem(DEAD_LETTER_QUEUE_KEY, item_id)
            await redis_client.delete(detail_key)
            retry_queue = RetryQueue()
            await retry_queue.enqueue(item)
            return item
        except Exception as exc:
            logger.error(f"Dead-letter replay failed: {exc}")
            return None

    async def clear(self, item_id: str) -> bool:
        try:
            from src.db.redis import redis_client
            await redis_client.zrem(DEAD_LETTER_QUEUE_KEY, item_id)
            await redis_client.delete(f"{DEAD_LETTER_QUEUE_KEY}:{item_id}")
            return True
        except Exception:
            return False

    async def size(self) -> int:
        try:
            from src.db.redis import redis_client
            return await redis_client.zcard(DEAD_LETTER_QUEUE_KEY) or 0
        except Exception:
            return 0


# ── Singletons (lazy) ────────────────────────────────────────────────

_priority: Optional[PriorityQueue] = None
_retry: Optional[RetryQueue] = None
_dead: Optional[DeadLetterQueue] = None


def get_priority_queue() -> PriorityQueue:
    global _priority
    if _priority is None:
        _priority = PriorityQueue()
    return _priority


def get_retry_queue() -> RetryQueue:
    global _retry
    if _retry is None:
        _retry = RetryQueue()
    return _retry


def get_dead_letter_queue() -> DeadLetterQueue:
    global _dead
    if _dead is None:
        _dead = DeadLetterQueue()
    return _dead
