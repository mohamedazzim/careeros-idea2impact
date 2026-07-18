"""MCP reliability layer for CareerOS.

Wraps MCP server calls with timeout protection, retry with exponential backoff,
fallback handling, and structured logging.

Usage:
    from src.observability.mcp_reliability import reliable_mcp_call

    result = await reliable_mcp_call(
        "twilio",
        "make_call",
        phone_number="+12025550123",
        message="Hello",
    )
"""
from __future__ import annotations
import asyncio
import time
from typing import Any, Dict, Optional

from src.core.exceptions import MCPError, MCPTimeoutError, MCPConnectionError
from src.observability.enterprise_logging import mcp_log


DEFAULT_TIMEOUT_S = 30.0
DEFAULT_RETRIES = 2
DEFAULT_BACKOFF_BASE = 2.0

# MCP-specific circuit breaker state
_mcp_circuits: Dict[str, Dict[str, Any]] = {}


def _get_circuit(provider: str) -> Dict[str, Any]:
    if provider not in _mcp_circuits:
        _mcp_circuits[provider] = {
            "failures": 0,
            "open": False,
            "last_failure": 0.0,
            "threshold": 5,
            "recovery_s": 30.0,
        }
    return _mcp_circuits[provider]


def _check_circuit(provider: str) -> bool:
    c = _get_circuit(provider)
    if not c["open"]:
        return True  # Circuit closed — proceed
    elapsed = time.time() - c["last_failure"]
    if elapsed >= c["recovery_s"]:
        c["open"] = False
        c["failures"] = 0
        mcp_log.info(f"MCP circuit reset for {provider}", extra={
            "operation": "mcp_circuit_reset",
            "provider": provider,
        })
        return True
    return False  # Circuit still open


def _record_success(provider: str) -> None:
    c = _get_circuit(provider)
    c["failures"] = 0
    c["open"] = False


def _record_failure(provider: str) -> None:
    c = _get_circuit(provider)
    c["failures"] += 1
    c["last_failure"] = time.time()
    if c["failures"] >= c["threshold"]:
        c["open"] = True
        mcp_log.error(f"MCP circuit opened for {provider}", extra={
            "operation": "mcp_circuit_open",
            "provider": provider,
            "failures": c["failures"],
        })


async def reliable_mcp_call(
    provider: str,
    tool: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    retries: int = DEFAULT_RETRIES,
    fallback_result: Optional[Any] = None,
    **tool_args: Any,
) -> Any:
    """Call an MCP tool with reliability guarantees.

    Args:
        provider: MCP provider name ("twilio", "elevenlabs").
        tool: Tool name to invoke ("make_call", "generate_audio", etc.).
        timeout_s: Per-call timeout in seconds.
        retries: Max retries after the initial attempt.
        fallback_result: Value to return if all attempts fail (None = raise).
        **tool_args: Arguments passed to the MCP tool.

    Returns:
        The tool's response, or fallback_result if specified and all retries exhausted.

    Raises:
        MCPError: If all attempts fail and no fallback_result specified.
    """
    # Circuit breaker check
    if not _check_circuit(provider):
        if fallback_result is not None:
            mcp_log.warning(f"MCP circuit open, returning fallback for {provider}/{tool}", extra={
                "operation": "mcp_fallback",
                "provider": provider,
                "tool": tool,
            })
            return fallback_result
        raise MCPConnectionError(
            f"MCP circuit breaker open for {provider}",
            error_code="MCP_CIRCUIT_OPEN",
            details={"provider": provider, "tool": tool},
        )

    last_error: Optional[Exception] = None
    max_attempts = 1 + retries

    for attempt in range(max_attempts):
        start = time.time()
        mcp_log.log_event(
            operation="mcp_call",
            message=f"MCP {provider}/{tool} attempt {attempt + 1}/{max_attempts}",
            metadata={"provider": provider, "tool": tool, "attempt": attempt + 1},
        )

        try:
            # Late import to avoid circular dependency at module level
            from src.services.mcp_client import mcp_pool

            result = await asyncio.wait_for(
                mcp_pool.call_tool(provider, tool, **tool_args),
                timeout=timeout_s,
            )

            duration_ms = (time.time() - start) * 1000
            _record_success(provider)
            mcp_log.log_event(
                operation="mcp_call_success",
                message=f"MCP {provider}/{tool} succeeded",
                duration_ms=duration_ms,
                status="success",
                metadata={"provider": provider, "tool": tool},
            )
            return result

        except asyncio.TimeoutError:
            last_error = MCPTimeoutError(
                f"MCP {provider}/{tool} timed out after {timeout_s}s",
                details={"provider": provider, "tool": tool, "timeout_s": timeout_s},
            )
            mcp_log.error(str(last_error), extra={
                "operation": "mcp_timeout",
                "provider": provider,
                "tool": tool,
                "attempt": attempt + 1,
            })
        except (MCPError, ConnectionError, OSError) as e:
            last_error = e
            mcp_log.warning(f"MCP {provider}/{tool} failed: {e}", extra={
                "operation": "mcp_call_failure",
                "provider": provider,
                "tool": tool,
                "attempt": attempt + 1,
                "error": str(e),
            })
        except Exception as e:
            # Unexpected errors — don't retry unless it's a known transient type
            _record_failure(provider)
            mcp_log.critical(f"Unexpected MCP error for {provider}/{tool}: {e}", extra={
                "operation": "mcp_call_fatal",
                "provider": provider,
                "tool": tool,
                "error": str(e),
                "error_type": type(e).__name__,
            })
            raise MCPError(
                f"Unexpected MCP error: {e}",
                details={"provider": provider, "tool": tool, "error_type": type(e).__name__},
            )

        _record_failure(provider)

        if attempt < retries:
            delay = DEFAULT_BACKOFF_BASE ** attempt
            mcp_log.debug(f"Retrying MCP {provider}/{tool} in {delay:.1f}s", extra={
                "operation": "mcp_retry_wait",
                "provider": provider,
                "tool": tool,
                "delay_s": delay,
            })
            await asyncio.sleep(delay)

    # All attempts exhausted
    if fallback_result is not None:
        mcp_log.warning(f"MCP fallback used for {provider}/{tool}", extra={
            "operation": "mcp_fallback",
            "provider": provider,
            "tool": tool,
            "attempts": max_attempts,
        })
        return fallback_result

    raise MCPError(
        f"MCP {provider}/{tool} failed after {max_attempts} attempts",
        error_code="MCP_ALL_RETRIES_EXHAUSTED",
        details={"provider": provider, "tool": tool, "attempts": max_attempts},
    )
