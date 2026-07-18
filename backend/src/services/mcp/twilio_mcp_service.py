"""Phase 5 — Twilio MCP Service.

Wraps the existing Twilio MCP server call with Phase 5 governance and observability.
All telephony calls pass through this service.
"""

import logging
import os
from typing import Any, Dict, Optional

from src.core.config import settings
from src.observability.tracing import trace_async
from src.services.mcp.twilio_adapter import build_blocked_result, get_twilio_health

logger = logging.getLogger(__name__)

_MOCK_RESULT = {
    "success": True,
    "call_sid": "CA_MOCK_SID_001",
    "status": "completed",
    "provider": "mock_mcp",
    "dry_run": True,
}


class TwilioMCPService:
    """Service wrapper for Twilio MCP tool calls."""

    def _health(self) -> Dict[str, Any]:
        return get_twilio_health()

    def has_credentials(self) -> bool:
        return self._health().get("configured", False)

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "make_call":
            return await self.make_call(
                phone_number=arguments.get("phone_number", ""),
                audio_message=arguments.get("audio_message", ""),
            )
        if tool_name == "send_sms":
            return await self.send_sms(
                phone_number=arguments.get("phone_number", ""),
                message=arguments.get("message", ""),
            )
        if tool_name == "health":
            return await self.check_health()
        return {"status": "failed", "reason": f"unknown_twilio_tool:{tool_name}"}

    @trace_async("twilio_make_call")
    async def make_call(self, phone_number: str, audio_message: str) -> Dict[str, Any]:
        if os.getenv("MOCK_MCP", "").lower() == "true":
            logger.info("MOCK_MCP enabled — returning simulated Twilio call result")
            return dict(_MOCK_RESULT)

        health = self._health()
        if not health.get("configured", False):
            return build_blocked_result(
                tool_name="make_call",
                phone_number=phone_number,
                reason=health.get("blocker_reason", "missing_credentials"),
                message="Twilio credentials are not configured; call blocked.",
            )
        from src.services.mcp_client import run_twilio_mcp

        try:
            result = await run_twilio_mcp(
                phone_number=phone_number,
                audio_message=audio_message,
                retries=settings.MCP_MAX_RETRIES,
            )
            return result
        except Exception as exc:
            logger.error(f"Twilio call failed: {exc}")
            return {
                "status": "failed",
                "error": str(exc),
                "call_sid": None,
                "reason": "twilio_runtime_error",
            }

    @trace_async("twilio_send_sms")
    async def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        health = self._health()
        if not health.get("configured", False):
            result = build_blocked_result(
                tool_name="send_sms",
                phone_number=phone_number,
                reason=health.get("blocker_reason", "missing_credentials"),
                message="Twilio credentials are not configured; SMS blocked.",
            )
            result["sid"] = None
            return result

        from src.services.mcp_client import run_twilio_sms_mcp

        try:
            return await run_twilio_sms_mcp(
                phone_number=phone_number,
                message=message,
                retries=settings.MCP_MAX_RETRIES,
            )
        except Exception as exc:
            logger.error(f"Twilio SMS failed: {exc}")
            return {
                "status": "failed",
                "error": str(exc),
                "sid": None,
                "reason": "twilio_runtime_error",
            }

    @trace_async("twilio_check_health")
    async def check_health(self) -> Dict[str, Any]:
        return self._health()

    def available_tools(self) -> list:
        return ["make_call", "send_sms", "health"]


# ── Singleton ────────────────────────────────────────────────────────

_svc: Optional[TwilioMCPService] = None


def get_twilio_mcp_service() -> TwilioMCPService:
    global _svc
    if _svc is None:
        _svc = TwilioMCPService()
    return _svc


def reset_twilio_mcp_service() -> None:
    global _svc
    _svc = None
