import time
import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self):
        self.mock_redis_store = {}
        self._redis_available = None

    async def _use_real_redis(self) -> bool:
        if self._redis_available is not None:
            return self._redis_available
        try:
            from src.db.redis import redis_client
            await redis_client.ping()
            self._redis_available = True
        except Exception:
            self._redis_available = False
        return self._redis_available

    async def check_rate_limit(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """
        Sliding window rate limit logic using Redis when available.
        Returns: (is_allowed, remaining_requests)
        """
        if await self._use_real_redis():
            from src.db.redis import redis_client
            current_time = time.time()
            redis_key = f"rate_limit:{key}"
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, current_time - window)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(current_time): current_time})
            pipe.expire(redis_key, window + 5)
            _, count, *_ = await pipe.execute()
            if count >= limit:
                return False, 0
            return True, limit - count - 1

        if os.getenv("MOCK_REDIS") == "true":
            store = self.mock_redis_store
        else:
            store = self.mock_redis_store

        current_time = time.time()

        if key not in store:
            store[key] = []

        store[key] = [t for t in store[key] if t > current_time - window]

        if len(store[key]) >= limit:
            return False, 0

        store[key].append(current_time)
        return True, limit - len(store[key])

rate_limiter = RateLimiter()

# Definitions for different API limits (requests per minute)
RATE_LIMITS = {
    "auth": {"limit": 5, "window": 60},
    "upload": {"limit": 20, "window": 60},
    "evaluation": {"limit": 10, "window": 60},
    "search": {"limit": 60, "window": 60},
}
