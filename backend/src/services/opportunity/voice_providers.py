"""RC3.1 Voice Provider Abstraction Layer.

Provides a pluggable interface for voice synthesis and conversational agents.
ElevenLabsProvider is the current implementation. Future providers can be added
without modifying the orchestrator or agent layer.

CRITICAL: ElevenLabs must not appear outside this provider layer.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VoiceSynthesisResult:
    provider: str
    status: str  # success, failed, blocked, mock
    audio_url: Optional[str] = None
    audio_bytes: Optional[int] = None
    voice_id: Optional[str] = None
    model: Optional[str] = None
    script: str = ""
    duration_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceCallResult:
    provider: str
    status: str  # queued, sent, failed, blocked
    call_sid: Optional[str] = None
    phone_number: str = ""
    duration_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationalTurn:
    role: str  # agent, user
    content: str
    intent: Optional[str] = None
    timestamp: Optional[str] = None


class VoiceProvider(ABC):
    """Abstract base for voice synthesis and conversational providers."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VoiceSynthesisResult:
        ...

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...


class ElevenLabsProvider(VoiceProvider):
    """ElevenLabs TTS provider via MCP Router."""

    def provider_name(self) -> str:
        return "elevenlabs"

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VoiceSynthesisResult:
        t0 = time.time()
        meta = metadata or {}

        if not (settings.ELEVENLABS_API_KEY or "").strip():
            return VoiceSynthesisResult(
                provider=self.provider_name(),
                status="blocked",
                script=text,
                duration_ms=round((time.time() - t0) * 1000, 2),
                error="ELEVENLABS_API_KEY not configured",
            )

        try:
            from src.services.mcp.mcp_router import get_mcp_router
            router = get_mcp_router()
            result = await router.dispatch(
                tool_name="generate_audio",
                arguments={
                    "candidate_name": meta.get("candidate_name", "user"),
                    "job_title": meta.get("job_title", ""),
                    "company": meta.get("company", ""),
                    "match_score": meta.get("match_score", 0),
                    "urgency": meta.get("urgency", "normal"),
                },
                session_uid=meta.get("session_uid", str(uuid.uuid4())),
            )

            status = result.get("status", "unknown")
            return VoiceSynthesisResult(
                provider=self.provider_name(),
                status="success" if status == "success" else ("mock" if status == "mock" else "failed"),
                audio_url=result.get("audio_file_path"),
                audio_bytes=result.get("audio_size_bytes"),
                voice_id=voice_id or result.get("metadata", {}).get("voice_id"),
                model=result.get("metadata", {}).get("model"),
                script=text,
                duration_ms=round((time.time() - t0) * 1000, 2),
                error=result.get("error"),
                metadata=result,
            )
        except Exception as exc:
            logger.error("ElevenLabsProvider synthesis failed: %s", exc)
            return VoiceSynthesisResult(
                provider=self.provider_name(),
                status="failed",
                script=text,
                duration_ms=round((time.time() - t0) * 1000, 2),
                error=str(exc),
            )

    async def health_check(self) -> Dict[str, Any]:
        api_key = (settings.ELEVENLABS_API_KEY or "").strip()
        configured = bool(api_key) and api_key != "your_elevenlabs_api_key_here"
        return {
            "provider": self.provider_name(),
            "configured": configured,
            "api_key_present": bool(api_key),
            "voice_id": (settings.VOICE_ELEVENLABS_VOICE_ID or "default"),
            "model": (settings.VOICE_ELEVENLABS_MODEL or "eleven_multilingual_v2"),
        }


class MockVoiceProvider(VoiceProvider):
    """Mock provider for testing without real credentials."""

    def provider_name(self) -> str:
        return "mock"

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VoiceSynthesisResult:
        return VoiceSynthesisResult(
            provider=self.provider_name(),
            status="mock",
            script=text,
            metadata={"note": "Mock provider — no real synthesis"},
        )

    async def health_check(self) -> Dict[str, Any]:
        return {"provider": "mock", "configured": True, "mode": "mock"}


# ── Provider Registry ──────────────────────────────────────────────

_PROVIDERS: Dict[str, type] = {
    "elevenlabs": ElevenLabsProvider,
    "mock": MockVoiceProvider,
}

# Future providers (not yet implemented):
# "retell": RetellProvider,
# "bland": BlandProvider,
# "custom": CustomProvider,

_active_provider: Optional[VoiceProvider] = None


def get_voice_provider(name: Optional[str] = None) -> VoiceProvider:
    """Get the active voice provider. Falls back to mock if no credentials."""
    global _active_provider

    if name:
        cls = _PROVIDERS.get(name)
        if cls:
            return cls()

    if _active_provider is not None:
        return _active_provider

    if (settings.ELEVENLABS_API_KEY or "").strip():
        _active_provider = ElevenLabsProvider()
    else:
        _active_provider = MockVoiceProvider()

    return _active_provider


def reset_voice_provider() -> None:
    global _active_provider
    _active_provider = None
