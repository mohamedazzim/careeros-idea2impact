import os
import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("elevenlabs")

# Try to import the real ElevenLabs client. The MCP server uses the HTTP API
# below for a stable bytes response, but this import proves the SDK is present
# in the container runtime.
try:
    from elevenlabs.client import ElevenLabs  # noqa: F401
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False


def _get_api_key() -> str:
    return os.getenv("ELEVENLABS_API_KEY", "")


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower()).strip("_")
    return slug[:80] or "career_alert"


def _normalize_language(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw.startswith("ta") or raw in {"tamil", "தமிழ்"}:
        return "tamil"
    return "english"


def _build_message(
    *,
    message: str | None,
    candidate_name: str,
    job_title: str,
    company: str,
    match_score: int,
    urgency: str,
    language: str,
) -> str:
    if message and message.strip():
        return message.strip()

    if language == "tamil":
        return (
            f"வணக்கம் {candidate_name}. "
            f"{company}-இல் உள்ள {job_title} பணி உங்கள் profile-க்கு {match_score} சதவீதம் பொருந்துகிறது. "
            f"அவசரம்: {urgency}. CareerOS dashboard-ஐ பார்க்கவும்."
        )
    return (
        f"High priority opportunity: you are a {match_score} percent match "
        f"for the {job_title} role at {company}. "
        f"Deadline urgency is {urgency}. Review immediately."
    )


def _generate_audio_bytes(api_key: str, voice_id: str, message: str, model: str) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = json.dumps({
        "text": message,
        "model_id": model,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.75,
        },
    }).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


@mcp.tool()
def generate_audio(
    candidate_name: str,
    job_title: str,
    company: str,
    match_score: int,
    urgency: str,
    message: str = "",
    language: str = "english",
) -> str:
    """Generate an audio message using ElevenLabs TTS."""
    normalized_language = _normalize_language(language)
    message = _build_message(
        message=message,
        candidate_name=candidate_name,
        job_title=job_title,
        company=company,
        match_score=match_score,
        urgency=urgency,
        language=normalized_language,
    )

    api_key = _get_api_key()
    voice_id = (
        os.getenv("ELEVENLABS_VOICE_ID")
        or os.getenv("VOICE_ELEVENLABS_VOICE_ID")
        or "JBFqnCBsd6RMkjVDRZzb"  # George, premade voice exposed by current ElevenLabs API
    )
    model = os.getenv("VOICE_ELEVENLABS_MODEL", "eleven_turbo_v2_5")

    if api_key:
        try:
            audio_bytes = _generate_audio_bytes(api_key, voice_id, message, model)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            audio_dir = Path(os.getenv("ELEVENLABS_AUDIO_DIR", "/tmp/careeros_elevenlabs"))
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_filename = f"elevenlabs_{_safe_slug(candidate_name)}_{match_score}_{timestamp}.mp3"
            audio_path = audio_dir / audio_filename
            audio_path.write_bytes(audio_bytes)

            result = {
                "audio_asset_reference": audio_filename,
                "audio_file_path": str(audio_path),
                "audio_size_bytes": len(audio_bytes),
                "message_generated": message,
                "status": "success",
                "remote_tts": True,
                "provider": "elevenlabs",
                "provider_generation_id": audio_filename,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "model": model,
                    "voice_id": voice_id,
                    "language": normalized_language,
                    "sdk_import_available": ELEVENLABS_AVAILABLE,
                    "transport": "https_api",
                },
            }
            logger.info(f"Real ElevenLabs TTS generated: {len(audio_bytes)} bytes")
            return json.dumps(result)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            logger.error(f"ElevenLabs TTS failed with HTTP {e.code}: {error_body}")
            return json.dumps({
                "audio_asset_reference": "",
                "message_generated": message,
                "status": "failed",
                "error": f"http_{e.code}: {error_body}",
                "remote_tts": True,
                "metadata": {
                    "model": model,
                    "voice_id": voice_id,
                    "language": normalized_language,
                    "sdk_import_available": ELEVENLABS_AVAILABLE,
                },
            })
        except Exception as e:
            logger.error(f"ElevenLabs TTS failed: {e}")
            return json.dumps({
                "audio_asset_reference": "",
                "message_generated": message,
                "status": "failed",
                "error": str(e),
                "remote_tts": True,
                "metadata": {
                    "model": model,
                    "voice_id": voice_id,
                    "language": normalized_language,
                    "sdk_import_available": ELEVENLABS_AVAILABLE,
                },
            })

    # Mock fallback
    logger.info(f"[MOCK ElevenLabs] Would synthesize: {message[:80]}...")
    return json.dumps({
        "audio_asset_reference": f"elevenlabs_audio_{candidate_name.lower().replace(' ', '_')}_{match_score}.mp3",
        "message_generated": message,
        "status": "mock",
        "remote_tts": False,
        "metadata": {
            "note": "ElevenLabs credentials not configured. Audio would be synthesized here.",
        },
    })


if __name__ == "__main__":
    mcp.run()
