"""Phase 5 — ElevenLabs MCP Service.

Wraps the existing ElevenLabs MCP server call with Phase 5 governance and observability.
All voice synthesis calls pass through this service.
"""

import logging
from typing import Any, Dict, Optional

from src.core.config import settings
from src.observability.tracing import trace_async

logger = logging.getLogger(__name__)


class ElevenLabsMCPService:
    """Service wrapper for ElevenLabs MCP tool calls."""

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "generate_audio":
            return await self.generate_audio(
                candidate_name=arguments.get("candidate_name", ""),
                job_title=arguments.get("job_title", ""),
                company=arguments.get("company", ""),
                match_score=arguments.get("match_score", 0),
                urgency=arguments.get("urgency", "normal"),
                message=arguments.get("message", ""),
                language=arguments.get("language", "english"),
            )
        if tool_name == "synthesize_speech":
            return await self.synthesize_speech(
                text=arguments.get("text", ""),
                voice_id=arguments.get("voice_id", settings.VOICE_ELEVENLABS_VOICE_ID),
            )
        return {"status": "failed", "reason": f"unknown_elevenlabs_tool:{tool_name}"}

    @trace_async("elevenlabs_generate_audio")
    async def generate_audio(
        self,
        candidate_name: str,
        job_title: str,
        company: str,
        match_score: int,
        urgency: str,
        message: str = "",
        language: str = "english",
    ) -> Dict[str, Any]:
        from src.services.mcp_client import run_elevenlabs_mcp

        try:
            result = await run_elevenlabs_mcp(
                candidate_name=candidate_name,
                job_title=job_title,
                company=company,
                match_score=match_score,
                urgency=urgency,
                message=message,
                language=language,
                retries=settings.MCP_MAX_RETRIES,
            )
            result["status"] = "success"
            return result
        except Exception as exc:
            logger.error(f"ElevenLabs audio generation failed: {exc}")
            return {
                "status": "failed",
                "error": str(exc),
                "audio_asset_reference": None,
                "reason": "elevenlabs_runtime_error",
            }

    @trace_async("elevenlabs_synthesize_speech")
    async def synthesize_speech(self, text: str, voice_id: str = "default") -> Dict[str, Any]:
        from src.services.mcp_client import run_elevenlabs_mcp

        try:
            result = await run_elevenlabs_mcp(
                candidate_name="system",
                job_title="notification",
                company="CareerOS",
                match_score=0,
                urgency="normal",
                retries=settings.MCP_MAX_RETRIES,
            )
            result["status"] = "success"
            result["synthesized_from"] = text[:100]
            return result
        except Exception as exc:
            logger.error(f"ElevenLabs speech synthesis failed: {exc}")
            return {
                "status": "failed",
                "error": str(exc),
                "audio_asset_reference": None,
            }

    def available_tools(self) -> list:
        return ["generate_audio", "synthesize_speech"]


# ── Singleton ────────────────────────────────────────────────────────

_svc: Optional[ElevenLabsMCPService] = None


def get_elevenlabs_mcp_service() -> ElevenLabsMCPService:
    global _svc
    if _svc is None:
        _svc = ElevenLabsMCPService()
    return _svc


def reset_elevenlabs_mcp_service() -> None:
    global _svc
    _svc = None
