import redis.asyncio as redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry
from redis.exceptions import ConnectionError, TimeoutError

from src.core.config import settings

# Redis short-term memory + Cache with timeout and retry handling
redis_client = redis.Redis.from_url(
    settings.REDIS_URL, 
    decode_responses=True,
    socket_timeout=5.0,
    socket_connect_timeout=5.0,
    retry=Retry(ExponentialBackoff(cap=10, base=1), 3),
    retry_on_error=[ConnectionError, TimeoutError]
)

async def get_redis():
    return redis_client
