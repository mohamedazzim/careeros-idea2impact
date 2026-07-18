"""Phase 5 — MCP Observability.

Thin wrapper around Prometheus metrics for MCP tool execution.
Follows the same pattern as InterviewObservability from Phase 4D.
"""

from typing import Optional

from src.observability.metrics import (
    MCP_EXECUTION_TOTAL,
    MCP_EXECUTION_LATENCY,
    MCP_EXECUTION_FAILURES,
    MCP_RETRY_AMPLIFICATION,
)


class MCPObservability:

    def record_execution(self, tool_name: str, server_name: str, status: str, duration_ms: int) -> None:
        MCP_EXECUTION_TOTAL.labels(tool_name=tool_name, status=status).inc()
        MCP_EXECUTION_LATENCY.labels(tool_name=tool_name).observe(duration_ms)

    def record_failure(self, tool_name: str, reason: str) -> None:
        MCP_EXECUTION_FAILURES.labels(tool_name=tool_name, reason=reason).inc()

    def record_retry(self, tool_name: str, attempt: int) -> None:
        MCP_RETRY_AMPLIFICATION.labels(tool_name=tool_name, attempt=str(attempt)).inc()

    def record_call(self, tool_name: str, status: str, duration_ms: int) -> None:
        MCP_EXECUTION_TOTAL.labels(tool_name=tool_name, status=status).inc()
        MCP_EXECUTION_LATENCY.labels(tool_name=tool_name).observe(duration_ms)


# ── Singleton ────────────────────────────────────────────────────────

_obs: Optional[MCPObservability] = None


def get_mcp_observability() -> MCPObservability:
    global _obs
    if _obs is None:
        _obs = MCPObservability()
    return _obs


def reset_mcp_observability() -> None:
    global _obs
    _obs = None
