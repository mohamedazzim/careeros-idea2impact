"""Enterprise logging for CareerOS.

Extends the existing structured JSON logger with domain-scoped
loggers for every subsystem: auth, agent, retrieval, MCP, graph, LLM.

Usage:
    from src.observability.enterprise_logging import auth_log
    auth_log.info("User authenticated", user_id=..., auth_method=...)
"""
from __future__ import annotations
import time
import contextvars
from typing import Any, Dict, Optional

from src.observability.context import request_id_ctx, user_id_ctx, workflow_id_ctx

# Re-export structured_logger so everything routes through one import
from src.observability.logger import structured_logger  # noqa: F401


# ── Logging Context Management ──────────────────────────────────────

_correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def set_logging_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Set all context vars for the current async context."""
    if request_id:
        request_id_ctx.set(request_id)
    if user_id:
        user_id_ctx.set(user_id)
    if workflow_id:
        workflow_id_ctx.set(workflow_id)
    if correlation_id:
        _correlation_id_ctx.set(correlation_id)


def get_log_context() -> Dict[str, Any]:
    """Get current logging context as a dictionary."""
    return {
        "request_id": request_id_ctx.get(),
        "user_id": user_id_ctx.get(),
        "workflow_id": workflow_id_ctx.get(),
        "correlation_id": _correlation_id_ctx.get(),
    }


# ── Domain-Scoped Logging Helpers ───────────────────────────────────

class DomainLogger:
    """Logger wrapper that auto-injects domain context into every call."""

    def __init__(self, domain: str):
        self.domain = domain

    def _enrich(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        base = {
            "service": self.domain,
            "timestamp": time.time(),
        }
        # Merge context vars
        ctx = get_log_context()
        for k, v in ctx.items():
            if v is not None:
                base[k] = v
        if extra:
            base.update(extra)
        return base

    def info(self, msg: str, **kwargs: Any) -> None:
        structured_logger.info(msg, extra=self._enrich(kwargs.get("extra")))  # type: ignore[arg-type]

    def warning(self, msg: str, **kwargs: Any) -> None:
        structured_logger.warning(msg, extra=self._enrich(kwargs.get("extra")))

    def error(self, msg: str, **kwargs: Any) -> None:
        structured_logger.error(msg, extra=self._enrich(kwargs.get("extra")))

    def critical(self, msg: str, **kwargs: Any) -> None:
        structured_logger.critical(msg, extra=self._enrich(kwargs.get("extra")))

    def debug(self, msg: str, **kwargs: Any) -> None:
        structured_logger.debug(msg, extra=self._enrich(kwargs.get("extra")))

    # Convenience: log with explicit domain kwargs
    def log_event(
        self,
        operation: str,
        message: str,
        level: str = "info",
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra: Dict[str, Any] = {
            "operation": operation,
        }
        if duration_ms is not None:
            extra["duration_ms"] = duration_ms
        if error is not None:
            extra["error"] = error
        if status is not None:
            extra["status"] = status
        if metadata:
            extra.update(metadata)

        enriched = self._enrich(extra)

        if level == "error":
            structured_logger.error(message, extra=enriched)
        elif level == "warning":
            structured_logger.warning(message, extra=enriched)
        elif level == "debug":
            structured_logger.debug(message, extra=enriched)
        elif level == "critical":
            structured_logger.critical(message, extra=enriched)
        else:
            structured_logger.info(message, extra=enriched)


# ── Domain Logger Instances ──────────────────────────────────────────

api_log = DomainLogger("api")
auth_log = DomainLogger("auth")
agent_log = DomainLogger("agent")
retrieval_log = DomainLogger("retrieval")
rerank_log = DomainLogger("rerank")
embed_log = DomainLogger("embedding")
mcp_log = DomainLogger("mcp")
graph_log = DomainLogger("graph")
llm_log = DomainLogger("llm")
interview_log = DomainLogger("interview")
orchestration_log = DomainLogger("orchestration")
privacy_log = DomainLogger("privacy")
indexing_log = DomainLogger("indexing")
infra_log = DomainLogger("infrastructure")
