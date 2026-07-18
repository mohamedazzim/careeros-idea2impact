"""Agent reliability framework for CareerOS.

Provides retry with exponential backoff, timeout protection, circuit breaker,
and structured logging for all agent executions.

Usage:
    from src.observability.agent_reliability import reliable_agent

    @reliable_agent("opportunity_discovery", retries=3, timeout_ms=30_000)
    async def discover_opportunities(...):
        ...
"""
from __future__ import annotations
import asyncio
import time
import functools
from typing import Any, Callable, Optional, TypeVar, Awaitable

from src.core.exceptions import AgentExecutionError, AgentTimeoutError
from src.observability.enterprise_logging import agent_log

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])

# In-memory circuit breaker state
_circuit_state: dict[str, dict] = {}


class CircuitBreaker:
    """Simple circuit breaker for agent calls.

    After `failure_threshold` consecutive failures, the circuit opens
    for `recovery_timeout` seconds before allowing a test call.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        if name not in _circuit_state:
            _circuit_state[name] = {
                "failures": 0,
                "last_failure_time": 0.0,
                "open": False,
            }

    @property
    def _state(self) -> dict:
        return _circuit_state[self.name]

    def is_open(self) -> bool:
        if not self._state["open"]:
            return False
        # Check if recovery timeout has passed
        elapsed = time.time() - self._state["last_failure_time"]
        if elapsed >= self.recovery_timeout:
            self._state["open"] = False
            self._state["failures"] = 0
            agent_log.info("Circuit breaker reset to half-open", extra={
                "operation": "circuit_breaker",
                "agent": self.name,
                "elapsed_ms": elapsed * 1000,
            })
            return False
        return True

    def record_success(self) -> None:
        self._state["failures"] = 0
        self._state["open"] = False

    def record_failure(self) -> None:
        self._state["failures"] += 1
        self._state["last_failure_time"] = time.time()
        if self._state["failures"] >= self.failure_threshold:
            self._state["open"] = True
            agent_log.error("Circuit breaker opened", extra={
                "operation": "circuit_breaker",
                "agent": self.name,
                "failures": self._state["failures"],
            })


def reliable_agent(
    name: str,
    retries: int = 3,
    timeout_ms: int = 60_000,
    backoff_base: float = 1.5,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    allowed_exceptions: tuple = (Exception,),
):
    """Decorator that adds retries, timeout, circuit breaker, and logging to agents.

    Args:
        name: Agent name for logging and circuit breaker identity.
        retries: Max retry attempts (not counting the initial call).
        timeout_ms: Per-call timeout in milliseconds.
        backoff_base: Exponential backoff multiplier base.
        failure_threshold: Consecutive failures before opening the circuit.
        recovery_timeout: Seconds before circuit attempts recovery.
        allowed_exceptions: Exceptions that trigger a retry (others propagate immediately).
    """
    circuit = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
    )

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if circuit.is_open():
                agent_log.warning("Circuit breaker open — rejecting call", extra={
                    "operation": "agent_call_rejected",
                    "agent": name,
                })
                raise AgentExecutionError(
                    f"Agent '{name}' circuit breaker is open",
                    error_code="AGENT_CIRCUIT_OPEN",
                    status_code=503,
                )

            last_error: Optional[Exception] = None
            max_attempts = 1 + retries
            start = time.time()

            for attempt in range(max_attempts):
                agent_log.log_event(
                    operation="agent_call",
                    message=f"Agent {name} attempt {attempt + 1}/{max_attempts}",
                    status="attempt",
                    metadata={"agent": name, "attempt": attempt + 1, "max_attempts": max_attempts},
                )

                try:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout_ms / 1000.0,
                    )
                    duration_ms = (time.time() - start) * 1000
                    circuit.record_success()
                    agent_log.log_event(
                        operation="agent_call_success",
                        message=f"Agent {name} succeeded on attempt {attempt + 1}",
                        status="success",
                        duration_ms=duration_ms,
                        metadata={"agent": name, "attempt": attempt + 1, "duration_ms": duration_ms},
                    )
                    return result

                except asyncio.TimeoutError:
                    error_msg = f"Agent '{name}' timed out after {timeout_ms}ms"
                    last_error = AgentTimeoutError(error_msg, error_code="AGENT_TIMEOUT")
                    agent_log.error(error_msg, extra={
                        "operation": "agent_timeout",
                        "agent": name,
                        "attempt": attempt + 1,
                    })
                except allowed_exceptions as e:
                    last_error = e
                    agent_log.warning(f"Agent {name} attempt {attempt + 1} failed: {e}", extra={
                        "operation": "agent_call_failure",
                        "agent": name,
                        "attempt": attempt + 1,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    })

                circuit.record_failure()

                if attempt < retries:
                    delay = backoff_base ** attempt
                    agent_log.debug(f"Retrying agent {name} in {delay:.1f}s", extra={
                        "operation": "agent_retry_wait",
                        "agent": name,
                        "delay_s": delay,
                    })
                    await asyncio.sleep(delay)

            # All retries exhausted
            agent_log.error(f"Agent {name} failed after {max_attempts} attempts", extra={
                "operation": "agent_call_fatal",
                "agent": name,
                "attempts": max_attempts,
                "last_error": str(last_error) if last_error else "unknown",
            })
            raise AgentExecutionError(
                f"Agent '{name}' failed after {max_attempts} attempts: {last_error}",
                error_code="AGENT_ALL_RETRIES_EXHAUSTED",
                details={
                    "agent": name,
                    "attempts": max_attempts,
                    "last_error_type": type(last_error).__name__ if last_error else "unknown",
                },
            )

        return wrapper  # type: ignore[return-value]
    return decorator


def agent_health_check(agent_name: str) -> dict:
    """Check the health/circuit state of a named agent."""
    circuit = CircuitBreaker(agent_name)  # Reuses existing state
    return {
        "agent": agent_name,
        "circuit_open": circuit.is_open(),
        "failures": circuit._state["failures"],
    }
