"""Small Redis-backed cache for TheirStack search responses."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from src.core.config import settings

logger = logging.getLogger(__name__)


class TheirStackCache:
    def __init__(self, ttl_seconds: int = 900):
        self.ttl_seconds = ttl_seconds

    def key_for(self, payload: Dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"theirstack:jobs:{digest}"

    async def get(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            import redis.asyncio as redis
            client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            value = await client.get(self.key_for(payload))
            await client.aclose()
            return json.loads(value) if value else None
        except Exception as exc:
            logger.debug("TheirStack cache read skipped: %s", exc)
            return None

    async def set(self, payload: Dict[str, Any], response: Dict[str, Any]) -> None:
        try:
            import redis.asyncio as redis
            client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await client.setex(self.key_for(payload), self.ttl_seconds, json.dumps(response, default=str))
            await client.aclose()
        except Exception as exc:
            logger.debug("TheirStack cache write skipped: %s", exc)

