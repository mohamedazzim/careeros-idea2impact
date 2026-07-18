"""Twilio MCP runtime harness.

By default this validates Twilio configuration and the blocked state only.
Set TWILIO_LIVE_CALL=true and provide TWILIO_TEST_PHONE_NUMBER to place a real
call through the MCP path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.opportunity_alert_agent import OpportunityAlertAgent
from src.core.config import settings
from src.services.mcp.twilio_adapter import get_twilio_health
from src.services.mcp.twilio_mcp_service import get_twilio_mcp_service


async def _run_live_call(phone_number: str) -> Dict[str, Any]:
    service = get_twilio_mcp_service()
    call_result = await service.make_call(
        phone_number=phone_number,
        audio_message="CareerOS opportunity alert test call.",
    )

    agent = OpportunityAlertAgent()
    alert_state = await agent.evaluate_and_alert(
        user_id="twilio-harness-user",
        opportunity={
            "id": "twilio-harness-opportunity",
            "title": "Harnessed Opportunity",
            "company": "CareerOS",
            "overall_score": 92,
            "urgency_score": 0.91,
        },
        phone_number=phone_number,
    )

    return {
        "call_result": call_result,
        "alert_status": alert_state.delivery_status,
        "call_sid": alert_state.call_sid,
        "notification_status": alert_state.delivery_status,
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-call", action="store_true", help="Place a real Twilio call when configured.")
    parser.add_argument("--phone-number", default=os.getenv("TWILIO_TEST_PHONE_NUMBER", ""), help="Destination number for a live test call.")
    parser.add_argument("--simulate-missing-credentials", action="store_true", help="Force the blocked-by-credentials branch for proof capture.")
    args = parser.parse_args()

    if args.simulate_missing_credentials:
        settings.TWILIO_ACCOUNT_SID = ""
        settings.TWILIO_AUTH_TOKEN = ""
        settings.TWILIO_PHONE_NUMBER = ""

    health = get_twilio_health()
    summary: Dict[str, Any] = {
        "twilio_health": health,
        "required_env_vars": health["required_env_vars"],
    }

    if not health["configured"]:
        summary["runtime_proof"] = "BLOCKED_BY_CREDENTIALS"
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 2

    if not args.live_call:
        summary["runtime_proof"] = "CONFIGURED_BUT_LIVE_CALL_NOT_REQUESTED"
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if not args.phone_number:
        summary["runtime_proof"] = "BLOCKED_BY_TEST_DESTINATION"
        summary["message"] = "Set TWILIO_TEST_PHONE_NUMBER or pass --phone-number to place a real call."
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 3

    live_result = await _run_live_call(args.phone_number)
    summary["runtime_proof"] = "LIVE_CALL_ATTEMPTED"
    summary["live_result"] = live_result
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
