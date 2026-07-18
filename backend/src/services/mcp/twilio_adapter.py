"""Twilio MCP adapter and runtime guards.

This module centralizes Twilio credential checks, blocked-state shaping,
and direct Twilio REST calls for the MCP server/service stack.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"

INTERACTIVE_PROMPT_PATTERN = re.compile(
    r"\bwould you like to hear more about the match reasoning, or should i proceed to application guidance\??",
    re.IGNORECASE,
)

TAMIL_HINT_PATTERN = re.compile(r"(தமிழ்|தமிழில்|tamil)", re.IGNORECASE)


def _looks_tamil(text: str) -> bool:
    return any("\u0b80" <= ch <= "\u0bff" for ch in text or "")


@dataclass(frozen=True)
class TwilioRuntimeConfig:
    account_sid: str
    auth_token: str
    phone_number: str
    package_available: bool = True

    @property
    def missing_fields(self) -> List[str]:
        missing: List[str] = []
        if not self.account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not self.auth_token:
            missing.append("TWILIO_AUTH_TOKEN")
        if not self.phone_number:
            missing.append("TWILIO_PHONE_NUMBER")
        return missing

    @property
    def ready(self) -> bool:
        return self.package_available and not self.missing_fields

    @property
    def blocker_reason(self) -> str:
        if not self.package_available:
            return "twilio_dependency_missing"
        if self.missing_fields:
            return "missing_credentials:" + ",".join(self.missing_fields)
        return ""


def load_twilio_config() -> TwilioRuntimeConfig:
    return TwilioRuntimeConfig(
        account_sid=(settings.TWILIO_ACCOUNT_SID or "").strip(),
        auth_token=(settings.TWILIO_AUTH_TOKEN or "").strip(),
        phone_number=(settings.TWILIO_PHONE_NUMBER or "").strip(),
        package_available=True,
    )


def get_twilio_health() -> Dict[str, Any]:
    config = load_twilio_config()
    return {
        "status": "ready" if config.ready else "blocked_by_credentials",
        "configured": config.ready,
        "missing_fields": config.missing_fields,
        "package_available": config.package_available,
        "from_number_present": bool(config.phone_number),
        "blocker_reason": config.blocker_reason,
        "required_env_vars": [
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_PHONE_NUMBER",
        ],
    }


def build_blocked_result(
    *,
    tool_name: str,
    phone_number: str,
    reason: str,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "status": "blocked_by_credentials",
        "reason": reason,
        "tool_name": tool_name,
        "phone_number": phone_number,
        "call_sid": None,
        "sid": None,
        "remote_call": False,
        "remote_sms": False,
        "configured": False,
        "message": message or "Twilio credentials are not available; no phone call was placed.",
    }


def _twilio_post(
    *,
    account_sid: str,
    auth_token: str,
    endpoint: str,
    data: Dict[str, Any],
    timeout_seconds: float = 20.0,
) -> Dict[str, Any]:
    url = f"{TWILIO_API_BASE}/Accounts/{account_sid}/{endpoint}"
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, data=data, auth=(account_sid, auth_token))
        response.raise_for_status()
        return response.json()


def _build_one_way_voice_message(audio_message: str) -> str:
    """Twilio currently delivers one-way alert calls.

    We strip interactive prompts that imply live response capture because the
    current Twilio delivery path does not yet include Gather/webhook handling.
    """
    sanitized = INTERACTIVE_PROMPT_PATTERN.sub("", audio_message or "").strip()
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    closing = (
        "CareerOS-இல் முழு விவரங்களையும் direct apply link-ஐயும் பார்க்கலாம். "
        "பிரியாவிடை."
        if TAMIL_HINT_PATTERN.search(sanitized) or _looks_tamil(sanitized)
        else "Please open CareerOS for the full match details and direct apply link. Goodbye."
    )
    if not sanitized:
        sanitized = "This is a CareerOS opportunity alert."
    if closing.lower() not in sanitized.lower():
        sanitized = f"{sanitized} {closing}".strip()
    return sanitized


def place_voice_call(phone_number: str, audio_message: str) -> Dict[str, Any]:
    config = load_twilio_config()
    if not config.ready:
        logger.warning("Twilio voice call blocked: %s", config.blocker_reason)
        return build_blocked_result(
            tool_name="make_call",
            phone_number=phone_number,
            reason=config.blocker_reason,
            message="Twilio credentials are not configured; call blocked.",
        )

    rendered_message = _build_one_way_voice_message(audio_message)
    twiml = (
        "<Response>"
        f"<Say>{html.escape(rendered_message)}</Say>"
        "<Pause length=\"1\"/>"
        "</Response>"
    )
    try:
        payload = _twilio_post(
            account_sid=config.account_sid,
            auth_token=config.auth_token,
            endpoint="Calls.json",
            data={"To": phone_number, "From": config.phone_number, "Twiml": twiml},
        )
        return {
            "call_sid": payload.get("sid"),
            "status": payload.get("status", "queued"),
            "phone_number": phone_number,
            "remote_call": True,
            "configured": True,
            "delivery_mode": "one_way_voice_alert",
            "rendered_message": rendered_message,
            "twilio_response": payload,
        }
    except httpx.HTTPStatusError as exc:
        logger.error("Twilio call failed with HTTP %s: %s", exc.response.status_code, exc)
        if exc.response.status_code in (401, 403):
            return build_blocked_result(
                tool_name="make_call",
                phone_number=phone_number,
                reason=f"http_{exc.response.status_code}: {exc.response.text}",
                message="Twilio authorization failed; call blocked.",
            )
        return {
            "call_sid": None,
            "status": "failed",
            "phone_number": phone_number,
            "remote_call": True,
            "configured": True,
            "error": f"http_{exc.response.status_code}: {exc.response.text}",
        }
    except Exception as exc:
        logger.error("Twilio call failed: %s", exc)
        return {
            "call_sid": None,
            "status": "failed",
            "phone_number": phone_number,
            "remote_call": True,
            "configured": True,
            "error": str(exc),
        }


def send_sms(phone_number: str, message: str) -> Dict[str, Any]:
    config = load_twilio_config()
    if not config.ready:
        logger.warning("Twilio SMS blocked: %s", config.blocker_reason)
        result = build_blocked_result(
            tool_name="send_sms",
            phone_number=phone_number,
            reason=config.blocker_reason,
            message="Twilio credentials are not configured; SMS blocked.",
        )
        result["sid"] = None
        return result

    try:
        payload = _twilio_post(
            account_sid=config.account_sid,
            auth_token=config.auth_token,
            endpoint="Messages.json",
            data={"To": phone_number, "From": config.phone_number, "Body": message},
        )
        return {
            "sid": payload.get("sid"),
            "status": payload.get("status", "queued"),
            "phone_number": phone_number,
            "remote_sms": True,
            "configured": True,
            "twilio_response": payload,
        }
    except httpx.HTTPStatusError as exc:
        logger.error("Twilio SMS failed with HTTP %s: %s", exc.response.status_code, exc)
        if exc.response.status_code in (401, 403):
            result = build_blocked_result(
                tool_name="send_sms",
                phone_number=phone_number,
                reason=f"http_{exc.response.status_code}: {exc.response.text}",
                message="Twilio authorization failed; SMS blocked.",
            )
            result["sid"] = None
            return result
        return {
            "sid": None,
            "status": "failed",
            "phone_number": phone_number,
            "remote_sms": True,
            "configured": True,
            "error": f"http_{exc.response.status_code}: {exc.response.text}",
        }
    except Exception as exc:
        logger.error("Twilio SMS failed: %s", exc)
        return {
            "sid": None,
            "status": "failed",
            "phone_number": phone_number,
            "remote_sms": True,
            "configured": True,
            "error": str(exc),
        }
