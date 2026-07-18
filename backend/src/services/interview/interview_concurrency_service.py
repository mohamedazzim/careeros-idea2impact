"""
Interview concurrency service — dedicated interview runtime isolation.

Implements:
- Dedicated interview concurrency pools via asyncio.Semaphore
- Interview-specific token budgets with adaptive throttling
- Adaptive timeout handling per operation type
- Interview retry throttling with exponential backoff
- Queue governance for overload protection

Phase 4D Hardening: Runtime isolation boundaries.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional

from src.core.config import settings
from src.observability.metrics import (
    DOMAIN_SEMAPHORE_WAIT,
    DOMAIN_SEMAPHORE_PRESSURE,
    DOMAIN_TOKEN_PRESSURE,
    DOMAIN_THROTTLE_EVENTS,
    DOMAIN_RETRY_AMPLIFICATION,
)

logger = logging.getLogger(__name__)


class TokenBudget:
    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
        self.used = 0

    def can_consume(self, tokens: int) -> bool:
        return (self.used + tokens) <= self.max_tokens

    def consume(self, tokens: int) -> bool:
        if self.can_consume(tokens):
            self.used += tokens
            return True
        return False

    def utilization(self) -> float:
        return self.used / max(self.max_tokens, 1)

    def remaining(self) -> int:
        return max(0, self.max_tokens - self.used)

    def reset(self) -> None:
        self.used = 0


class InterviewConcurrencyService:
    def __init__(self):
        max_concurrent = settings.INTERVIEW_CONCURRENT_EVALUATIONS
        self._evaluation_semaphore = asyncio.Semaphore(max_concurrent)
        self._question_semaphore = asyncio.Semaphore(max_concurrent)
        self._feedback_semaphore = asyncio.Semaphore(max(1, max_concurrent // 2))
        self.token_budget = TokenBudget(settings.INTERVIEW_TOKEN_BUDGET)
        self.timeout_eval = settings.INTERVIEW_TIMEOUT_EVALUATION
        self.timeout_question = settings.INTERVIEW_TIMEOUT_QUESTION
        self.timeout_feedback = settings.INTERVIEW_TIMEOUT_FEEDBACK
        self.max_retries = settings.INTERVIEW_RETRY_MAX
        self.retry_base_delay = settings.INTERVIEW_RETRY_BASE_DELAY

    async def run_evaluation(self, fn, *args, **kwargs) -> Dict[str, Any]:
        return await self._run_guarded(
            self._evaluation_semaphore, self.timeout_eval, "evaluation", fn, *args, **kwargs
        )

    async def run_question_generation(self, fn, *args, **kwargs) -> Dict[str, Any]:
        return await self._run_guarded(
            self._question_semaphore, self.timeout_question, "question_generation", fn, *args, **kwargs
        )

    async def run_feedback(self, fn, *args, **kwargs) -> Dict[str, Any]:
        return await self._run_guarded(
            self._feedback_semaphore, self.timeout_feedback, "feedback", fn, *args, **kwargs
        )

    async def _run_guarded(
        self, sem: asyncio.Semaphore, timeout: int,
        operation: str, fn, *args, **kwargs
    ) -> Dict[str, Any]:
        wait_start = time.monotonic()
        sem_acquired = False
        try:
            async with asyncio.timeout(timeout + 5):
                await sem.acquire()
                sem_acquired = True
            wait_ms = (time.monotonic() - wait_start) * 1000
            DOMAIN_SEMAPHORE_WAIT.labels(domain="interview").observe(wait_ms / 1000)
            if wait_ms > 500:
                DOMAIN_SEMAPHORE_PRESSURE.labels(domain="interview").observe(1)

            return await self._retry_with_backoff(fn, timeout, operation, *args, **kwargs)
        except asyncio.TimeoutError:
            logger.warning("interview_semaphore_timeout", extra={"operation": operation})
            return {"error": "semaphore_timeout", "operation": operation}
        finally:
            if sem_acquired:
                sem.release()

    async def _retry_with_backoff(
        self, fn, timeout: int, operation: str, *args, **kwargs
    ) -> Dict[str, Any]:
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with asyncio.timeout(timeout):
                    result = await fn(*args, **kwargs)
                return result
            except asyncio.TimeoutError:
                last_error = f"timeout after {timeout}s"
                logger.warning("interview_operation_timeout",
                               extra={"operation": operation, "attempt": attempt})
                DOMAIN_RETRY_AMPLIFICATION.labels(domain="interview", attempt=str(attempt)).inc()
            except Exception as e:
                last_error = str(e)
                logger.warning("interview_operation_error",
                               extra={"operation": operation, "attempt": attempt, "error": str(e)})
                DOMAIN_RETRY_AMPLIFICATION.labels(domain="interview", attempt=str(attempt)).inc()

            if attempt < self.max_retries:
                delay = self.retry_base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

        return {"error": last_error or "max_retries_exceeded", "operation": operation}

    def check_token_budget(self, estimated_tokens: int) -> bool:
        return self.token_budget.can_consume(estimated_tokens)

    def consume_tokens(self, tokens: int) -> bool:
        ok = self.token_budget.consume(tokens)
        DOMAIN_TOKEN_PRESSURE.labels(domain="interview").observe(self.token_utilization())
        return ok

    def token_utilization(self) -> float:
        return self.token_budget.utilization()

    def throttle_if_needed(self) -> Optional[int]:
        util = self.token_utilization()
        if util >= 0.9:
            DOMAIN_THROTTLE_EVENTS.labels(domain="interview").inc()
            return max(256, int(4096 * 0.125))
        elif util >= 0.75:
            DOMAIN_THROTTLE_EVENTS.labels(domain="interview").inc()
            return max(512, int(4096 * 0.25))
        elif util >= 0.5:
            return max(1024, int(4096 * 0.5))
        return None

    def reset_budget(self) -> None:
        self.token_budget.reset()

    async def active_operations(self) -> Dict[str, int]:
        return {
            "evaluation_queue": self._evaluation_semaphore._value,
            "question_queue": self._question_semaphore._value,
            "feedback_queue": self._feedback_semaphore._value,
        }


_svc: InterviewConcurrencyService | None = None


def get_interview_concurrency_service() -> InterviewConcurrencyService:
    global _svc
    if _svc is None:
        _svc = InterviewConcurrencyService()
    return _svc


def reset_interview_concurrency_service() -> None:
    global _svc
    _svc = None


def __getattr__(name: str):
    if name == "interview_concurrency_service":
        return get_interview_concurrency_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
