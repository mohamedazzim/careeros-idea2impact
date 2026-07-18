"""Phase 6 — Retry Coordinator.

Coordinates retry execution for orchestration sessions with
exponential backoff, jitter, max attempt tracking, and dead-letter.
"""

import time
import random
import logging
import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Dict, Optional
from src.core.config import settings

logger = logging.getLogger(__name__)

RETRY_KEY_PREFIX = "orch:retry:"


@dataclass
class RetryState:
    retry_id: str
    session_uid: str
    attempt: int = 1
    max_attempts: int = 3
    base_delay: float = 1.0
    backoff_factor: float = 2.0
    jitter_max: float = 0.5
    last_error: Optional[str] = None
    last_attempt_at: float = 0.0
    next_attempt_at: float = 0.0
    status: str = "pending"  # pending, in_flight, completed, exhausted

    def compute_delay(self) -> float:
        """Compute delay with exponential backoff and jitter."""
        delay = self.base_delay * (self.backoff_factor ** (self.attempt - 1))
        jitter = random.uniform(0, self.jitter_max)
        return delay + jitter

    def to_dict(self) -> Dict[str, Any]:
        return {
            "retry_id": self.retry_id,
            "session_uid": self.session_uid,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "last_error": self.last_error,
            "last_attempt_at": self.last_attempt_at,
            "next_attempt_at": self.next_attempt_at,
            "status": self.status,
        }


class RetryCoordinator:
    """Coordinates retry execution with persistent state tracking."""

    async def schedule(
        self,
        session_uid: str,
        fn: Callable[[], Coroutine[Any, Any, Any]],
        max_attempts: int = 3,
    ) -> Dict[str, Any]:
        """Execute fn with retry, recording each attempt."""
        state = RetryState(
            retry_id=f"retry_{session_uid}_{int(time.time())}",
            session_uid=session_uid,
            max_attempts=max_attempts,
        )

        try:
            from src.observability.metrics import MCP_RETRY_AMPLIFICATION
        except ImportError:
            MCP_RETRY_AMPLIFICATION = None

        for attempt in range(1, max_attempts + 1):
            state.attempt = attempt
            state.last_attempt_at = time.time()
            state.status = "in_flight"
            state.next_attempt_at = state.last_attempt_at + state.compute_delay()

            try:
                result = await fn()
                state.status = "completed"
                await self._persist_state(state)
                if isinstance(result, dict):
                    result["retry_attempts"] = attempt
                return result
            except Exception as exc:
                state.last_error = str(exc)
                state.status = "exhausted" if attempt >= max_attempts else "pending"

                if MCP_RETRY_AMPLIFICATION:
                    try:
                        MCP_RETRY_AMPLIFICATION.labels(tool_name="retry_coordinator", attempt=str(attempt)).inc()
                    except Exception:
                        pass

                if attempt < max_attempts:
                    delay = state.compute_delay()
                    logger.warning(
                        f"Retry {attempt}/{max_attempts} for {session_uid} failed. "
                        f"Retrying in {delay:.1f}s. Error: {exc}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All {max_attempts} retries exhausted for {session_uid}. "
                        f"Last error: {exc}"
                    )

        await self._persist_state(state)
        return {
            "status": "failed",
            "reason": "max_retries_exhausted",
            "attempts": attempt,
            "last_error": state.last_error,
        }

    async def get_retry_state(self, retry_id: str) -> Optional[RetryState]:
        """Retrieve retry state from Redis."""
        try:
            from src.db.redis import redis_client
            raw = await redis_client.get(f"{RETRY_KEY_PREFIX}{retry_id}")
            if raw:
                import json
                return RetryState(**json.loads(raw))
        except Exception:
            pass
        return None

    async def _persist_state(self, state: RetryState):
        try:
            from src.db.redis import redis_client
            import json
            await redis_client.setex(
                f"{RETRY_KEY_PREFIX}{state.retry_id}",
                getattr(settings, 'ORCHESTRATION_SESSION_TTL', 7200),
                json.dumps(state.to_dict()),
            )
        except Exception:
            pass


# ── Singleton ────────────────────────────────────────────────────────

_coordinator: Optional[RetryCoordinator] = None


def get_retry_coordinator() -> RetryCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = RetryCoordinator()
    return _coordinator
