"""
Embedding service resilience: circuit breaker, rate-limit handling, backpressure.

Stateless, async-safe, observable. Worklet-safe.
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker for embedding API calls.

    Protects the upstream NVIDIA API from cascading failures.
    Transitions: CLOSED → OPEN on consecutive failures, OPEN → HALF_OPEN
    after recovery timeout, HALF_OPEN → CLOSED on success, HALF_OPEN → OPEN on failure.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_requests: int = 2

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    half_open_requests: int = 0

    def _should_attempt_recovery(self) -> bool:
        return (time.monotonic() - self.last_failure_time) >= self.recovery_timeout

    async def acquire(self) -> bool:
        """Attempt to acquire a permit. Returns True if request may proceed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self.state = CircuitState.HALF_OPEN
                self.half_open_requests = 0
                logger.info("Circuit breaker transitioning OPEN → HALF_OPEN for recovery attempt")
            else:
                return False

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_requests >= self.half_open_max_requests:
                return False
            self.half_open_requests += 1
            return True

        return False

    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.half_open_requests = 0
            logger.info("Circuit breaker closed — upstream recovered")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.half_open_requests = 0
            logger.warning("Circuit breaker re-opened — recovery attempt failed")
        elif self.failure_count >= self.failure_threshold and self.state == CircuitState.CLOSED:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} consecutive failures"
            )


@dataclass
class RateLimitTracker:
    """Tracks rate-limit responses and enforces cooldown periods.

    When the API returns 429, applies progressive cooldown to prevent retry storms.
    """

    base_cooldown: float = 5.0
    max_cooldown: float = 60.0
    cooldown_multiplier: float = 2.0

    current_cooldown: float = 0.0
    last_rate_limit_time: float = 0.0
    rate_limit_count: int = 0

    def record_rate_limit(self) -> float:
        """Record a rate-limit hit, return seconds to wait."""
        self.rate_limit_count += 1
        self.last_rate_limit_time = time.monotonic()
        self.current_cooldown = min(
            self.base_cooldown * (self.cooldown_multiplier ** (self.rate_limit_count - 1)),
            self.max_cooldown,
        )
        logger.warning(
            f"Rate limit hit #{self.rate_limit_count} — cooldown {self.current_cooldown:.1f}s"
        )
        return self.current_cooldown

    def record_success(self) -> None:
        """Record a successful call — decay the rate limit counter."""
        if self.rate_limit_count > 0:
            self.rate_limit_count = max(0, self.rate_limit_count - 1)
            self.current_cooldown = max(
                0,
                self.base_cooldown * (self.cooldown_multiplier ** max(0, self.rate_limit_count - 1)),
            )

    def cooldown_remaining(self) -> float:
        """Seconds remaining in cooldown. 0 if no cooldown active."""
        elapsed = time.monotonic() - self.last_rate_limit_time
        remaining = self.current_cooldown - elapsed
        return max(0.0, remaining)

    @property
    def is_in_cooldown(self) -> bool:
        return self.cooldown_remaining() > 0


class EmbeddingQueue:
    """Backpressure-aware embedding request queue.

    Uses an async semaphore to limit concurrent embedding requests,
    preventing downstream resource exhaustion.
    """

    def __init__(self, max_concurrent: int = 5, max_queue_depth: int = 50):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue_depth = 0
        self._max_queue_depth = max_queue_depth

    async def acquire(self) -> bool:
        """Try to enter the queue. Returns False if queue is full."""
        if self._queue_depth >= self._max_queue_depth:
            logger.warning(
                f"Embedding queue full ({self._queue_depth}/{self._max_queue_depth})"
            )
            return False
        self._queue_depth += 1
        await self._semaphore.acquire()
        self._queue_depth -= 1
        return True

    def release(self) -> None:
        """Release a queue slot."""
        self._semaphore.release()

    @property
    def queue_depth(self) -> int:
        return self._queue_depth

    @property
    def available_slots(self) -> int:
        return self._max_queue_depth - self._queue_depth


# Module-level singletons (lazy via __getattr__)
_circuit_breaker: Optional[CircuitBreaker] = None
_rate_limit_tracker: Optional[RateLimitTracker] = None
_embedding_queue: Optional[EmbeddingQueue] = None


def get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker


def get_rate_limit_tracker() -> RateLimitTracker:
    global _rate_limit_tracker
    if _rate_limit_tracker is None:
        _rate_limit_tracker = RateLimitTracker()
    return _rate_limit_tracker


def get_embedding_queue() -> EmbeddingQueue:
    global _embedding_queue
    if _embedding_queue is None:
        _embedding_queue = EmbeddingQueue()
    return _embedding_queue


def reset_resilience() -> None:
    global _circuit_breaker, _rate_limit_tracker, _embedding_queue
    _circuit_breaker = None
    _rate_limit_tracker = None
    _embedding_queue = None
