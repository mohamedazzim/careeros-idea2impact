import sys
import json
import logging
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Ensure the repository root is on sys.path when the server is launched as a subprocess.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.mcp.twilio_adapter import (
    get_twilio_health,
    place_voice_call,
    send_sms as send_sms_via_adapter,
)

logger = logging.getLogger(__name__)
mcp = FastMCP("twilio")


@mcp.tool()
def make_call(phone_number: str, audio_message: str) -> str:
    """Make an outbound voice call using Twilio."""
    result = place_voice_call(phone_number=phone_number, audio_message=audio_message)
    if result.get("status") == "blocked_by_credentials":
        logger.warning("Twilio call blocked for %s", phone_number)
    return json.dumps(result)


@mcp.tool()
def send_sms(phone_number: str, message: str) -> str:
    """Send an SMS via Twilio."""
    result = send_sms_via_adapter(phone_number=phone_number, message=message)
    if result.get("status") == "blocked_by_credentials":
        logger.warning("Twilio SMS blocked for %s", phone_number)
    return json.dumps(result)


@mcp.tool()
def health() -> str:
    """Return Twilio credential health for MCP validation."""
    return json.dumps(get_twilio_health())


if __name__ == "__main__":
    mcp.run()
