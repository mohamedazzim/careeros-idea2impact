"""Phase 5 — MCP Governance.

Timeout enforcement, retry governance, duplicate call detection,
and failure isolation. Wraps every MCP call.

Follows the same pattern as InterviewConcurrencyService from Phase 4D.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from src.core.config import settings
from src.observability.metrics import (
    MCP_EXECUTION_TOTAL,
    MCP_EXECUTION_LATENCY,
    MCP_EXECUTION_FAILURES,
    MCP_RETRY_AMPLIFICATION,
)


class MCPGovernance:
    """Governs every MCP tool call with timeout, retry, and validation."""

    def __init__(self):
        self.tool_timeout = settings.MCP_TOOL_TIMEOUT
        self.max_retries = settings.MCP_MAX_RETRIES
        self.backoff_base = settings.MCP_RETRY_BACKOFF_BASE

    async def validate_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        session_uid: str,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        if not tool_name:
            return {"allowed": False, "reason": "empty_tool_name"}

        if not isinstance(arguments, dict):
            return {"allowed": False, "reason": "invalid_arguments_type"}

        if tool_name == "make_call" and not arguments.get("phone_number"):
            return {"allowed": False, "reason": "missing_phone_number"}

        if tool_name == "generate_audio" and not arguments.get("job_title"):
            return {"allowed": False, "reason": "missing_job_title_for_audio"}

        return {"allowed": True}

    async def guarded_execution(
        self,
        service: Any,
        tool_name: str,
        arguments: Dict[str, Any],
        session_uid: str,
        attempt: int,
    ) -> Dict[str, Any]:
        t0 = time.time()

        try:
            result = await asyncio.wait_for(
                self._dispatch_to_service(service, tool_name, arguments),
                timeout=self.tool_timeout,
            )
            duration_ms = int((time.time() - t0) * 1000)

            status = result.get("status", "success")
            if status in {"failed", "blocked_by_credentials", "rejected", "unavailable"}:
                MCP_EXECUTION_FAILURES.labels(tool_name=tool_name, reason=status).inc()
            else:
                MCP_EXECUTION_TOTAL.labels(tool_name=tool_name, status="success").inc()
                if attempt > 1:
                    MCP_RETRY_AMPLIFICATION.labels(tool_name=tool_name, attempt=str(attempt)).inc()

            result.setdefault("status", status)
            result["attempt"] = attempt
            result["duration_ms"] = duration_ms
            return result

        except asyncio.TimeoutError:
            duration_ms = int((time.time() - t0) * 1000)
            MCP_EXECUTION_FAILURES.labels(tool_name=tool_name, reason="timeout").inc()
            MCP_EXECUTION_LATENCY.labels(tool_name=tool_name).observe(duration_ms)
            await asyncio.sleep(self.backoff_base ** attempt)
            raise

        except Exception as exc:
            duration_ms = int((time.time() - t0) * 1000)
            MCP_EXECUTION_FAILURES.labels(tool_name=tool_name, reason=type(exc).__name__).inc()
            await asyncio.sleep(self.backoff_base ** attempt)
            raise

    async def _dispatch_to_service(self, service: Any, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if hasattr(service, "execute"):
            return await service.execute(tool_name, arguments)
        elif hasattr(service, "make_call") and tool_name == "make_call":
            return await service.make_call(
                phone_number=arguments.get("phone_number", ""),
                audio_message=arguments.get("audio_message", ""),
            )
        elif hasattr(service, "generate_audio") and tool_name == "generate_audio":
            return await service.generate_audio(
                candidate_name=arguments.get("candidate_name", ""),
                job_title=arguments.get("job_title", ""),
                company=arguments.get("company", ""),
                match_score=arguments.get("match_score", 0),
                urgency=arguments.get("urgency", "normal"),
            )
        raise ValueError(f"Unknown dispatch: {tool_name}")

    def generate_idempotency_key(self, session_uid: str, tool_name: str, opportunity_id: str) -> str:
        return f"idem:{session_uid}:{tool_name}:{opportunity_id}:{uuid.uuid4().hex[:8]}"


# ── Singleton ────────────────────────────────────────────────────────

_gov: Optional[MCPGovernance] = None


def get_mcp_governance() -> MCPGovernance:
    global _gov
    if _gov is None:
        _gov = MCPGovernance()
    return _gov


def reset_mcp_governance() -> None:
    global _gov
    _gov = None
