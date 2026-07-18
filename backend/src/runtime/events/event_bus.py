"""Phase 5 — Event Bus.

Redis-backed event coordinator for orchestration events.
Supports: publish, subscribe (pubsub), replay (streams), dead letters.
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.db.redis import redis_client
from src.observability.metrics import EVENT_BUS_QUEUE_DEPTH_GAUGE

PREFIX = f"{settings.ORCHESTRATION_REDIS_KEY_PREFIX}events"


@dataclass
class Event:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    session_uid: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0
    status: str = "pending"


class EventBus:
    """Redis-backed event bus for orchestration event coordination."""

    def _stream_key(self, session_uid: str) -> str:
        return f"{PREFIX}:stream:{session_uid}"

    def _pubsub_channel(self, pattern: str) -> str:
        return f"{PREFIX}:channel:{pattern}"

    def _dead_letter_key(self) -> str:
        return f"{PREFIX}:dead_letter"

    async def publish(self, event: Event) -> str:
        data = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "session_uid": event.session_uid,
            "payload": json.dumps(event.payload),
            "timestamp": str(event.timestamp),
            "retry_count": str(event.retry_count),
            "status": event.status,
        }
        stream_key = self._stream_key(event.session_uid)
        msg_id = await redis_client.xadd(stream_key, data, maxlen=settings.ORCHESTRATION_EVENT_RETENTION)
        await redis_client.expire(stream_key, settings.ORCHESTRATION_DEAD_LETTER_TTL)

        channel = self._pubsub_channel(event.event_type)
        await redis_client.publish(channel, json.dumps(data))
        EVENT_BUS_QUEUE_DEPTH_GAUGE.set(await redis_client.xlen(stream_key))
        return msg_id

    async def replay(self, session_uid: str, count: int = 100) -> List[Event]:
        stream_key = self._stream_key(session_uid)
        results = await redis_client.xread({stream_key: "0"}, count=count)
        events = []
        for _, messages in results:
            for msg_id, data in messages:
                events.append(Event(
                    event_id=data.get("event_id", ""),
                    event_type=data.get("event_type", ""),
                    session_uid=data.get("session_uid", ""),
                    payload=json.loads(data.get("payload", "{}")),
                    timestamp=float(data.get("timestamp", time.time())),
                    retry_count=int(data.get("retry_count", 0)),
                    status=data.get("status", "pending"),
                ))
        return events

    async def dead_letter(self, event: Event, reason: str) -> None:
        entry = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "reason": reason,
            "timestamp": time.time(),
        }
        await redis_client.lpush(self._dead_letter_key(), json.dumps(entry))
        await redis_client.ltrim(self._dead_letter_key(), 0, settings.ORCHESTRATION_EVENT_RETENTION)

    async def get_dead_letters(self, limit: int = 50) -> List[Dict[str, Any]]:
        items = await redis_client.lrange(self._dead_letter_key(), 0, limit - 1)
        return [json.loads(i) for i in items]


# ── Singleton ────────────────────────────────────────────────────────

_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_event_bus() -> None:
    global _bus
    _bus = None
