"""Phase 5 — MCP Router.

Dynamic MCP tool routing with selection reasoning, fallback chains,
and structured responses. All MCP calls pass through this layer.
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.observability.tracing import trace_async

from src.services.mcp.twilio_mcp_service import get_twilio_mcp_service
from src.services.mcp.elevenlabs_mcp_service import get_elevenlabs_mcp_service
from src.services.mcp.mcp_governance import get_mcp_governance
from src.services.mcp.mcp_observability import get_mcp_observability

# ── Tool Registry ─────────────────────────────────────────────────────

TOOL_REGISTRY: Dict[str, str] = {
    "generate_audio": "elevenlabs",
    "make_call": "twilio",
    "send_sms": "twilio",
    "synthesize_speech": "elevenlabs",
}

TOOL_FALLBACK: Dict[str, str] = {
    "send_sms": "twilio",  # same server, different tool
}


class MCPRouter:
    """Routes MCP tool calls to the correct server with governance."""

    def __init__(self):
        try:
            self.governance = get_mcp_governance()
        except Exception:
            self.governance = None
        try:
            self.observability = get_mcp_observability()
        except Exception:
            self.observability = None
        try:
            self._two = get_twilio_mcp_service()
        except Exception:
            self._two = None
        try:
            self._eleven = get_elevenlabs_mcp_service()
        except Exception:
            self._eleven = None

    @trace_async("mcp_router_dispatch")
    async def dispatch(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        session_uid: str = "",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.time()
        idempotency_key = idempotency_key or str(uuid.uuid4())
        server = self._resolve_server(tool_name)
        selection_reason = f"tool_to_server:{tool_name}->{server}"

        governance = self.governance or get_mcp_governance()
        pre_check = await governance.validate_call(tool_name, arguments, session_uid, idempotency_key)
        if not pre_check.get("allowed", True):
            return {
                "status": "rejected",
                "reason": pre_check.get("reason", "governance_blocked"),
                "governance_verdict": "blocked",
            }

        result = await self._call_with_retry(server, tool_name, arguments, session_uid)
        duration_ms = int((time.time() - t0) * 1000)

        observability = self.observability or get_mcp_observability()
        observability.record_execution(
            tool_name=tool_name,
            server_name=server,
            status=result.get("status", "unknown"),
            duration_ms=duration_ms,
        )

        result["selection_reason"] = selection_reason
        result["idempotency_key"] = idempotency_key
        result["duration_ms"] = duration_ms
        return result

    def _resolve_server(self, tool_name: str) -> str:
        return TOOL_REGISTRY.get(tool_name, "unknown")

    async def _call_with_retry(
        self, server: str, tool_name: str, arguments: Dict[str, Any], session_uid: str
    ) -> Dict[str, Any]:
        governance = self.governance or get_mcp_governance()
        last_error = None

        for attempt in range(1, settings.MCP_MAX_RETRIES + 1):
            try:
                if server == "twilio":
                    twilio = self._two or get_twilio_mcp_service()
                    return await governance.guarded_execution(
                        twilio, tool_name, arguments, session_uid, attempt
                    )
                elif server == "elevenlabs":
                    eleven = self._eleven or get_elevenlabs_mcp_service()
                    return await governance.guarded_execution(
                        eleven, tool_name, arguments, session_uid, attempt
                    )
                else:
                    return {
                        "status": "failed",
                        "reason": f"unknown_server:{server}",
                        "error": f"No MCP server registered for tool '{tool_name}'",
                    }
            except Exception as exc:
                last_error = str(exc)
                continue

        return {
            "status": "failed",
            "reason": "max_retries_exceeded",
            "error": last_error,
        }

    def available_tools(self) -> List[Dict[str, str]]:
        return [
            {"tool": name, "server": server}
            for name, server in TOOL_REGISTRY.items()
        ]


# ── Singleton ────────────────────────────────────────────────────────

_router: Optional[MCPRouter] = None


def get_mcp_router() -> MCPRouter:
    global _router
    if _router is None:
        _router = MCPRouter()
    return _router


def reset_mcp_router() -> None:
    global _router
    _router = None
