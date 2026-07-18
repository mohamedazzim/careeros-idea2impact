"""RC3.1 Twilio Call Reconciliation Service.

Background job that fetches final call status from Twilio API,
updates voice_sessions, voice_outcomes, and communication_requests
with reconciled data including duration, cost, and final status.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import httpx
from sqlalchemy import select

from src.db.session import async_session
from src.models.jobs import VoiceOutcome, VoiceSession, CommunicationRequest
from src.services.mcp.twilio_adapter import load_twilio_config

logger = logging.getLogger(__name__)


async def reconcile_call_status(call_sid: str) -> Dict[str, Any]:
    """Fetch final call status from Twilio REST API."""
    config = load_twilio_config()
    if not config.ready:
        return {"status": "skipped", "reason": config.blocker_reason}

    url = f"https://api.twilio.com/2010-04-01/Accounts/{config.account_sid}/Calls/{call_sid}.json"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, auth=(config.account_sid, config.auth_token))
            resp.raise_for_status()
            data = resp.json()
            return {
                "status": data.get("status", "unknown"),
                "duration": int(data.get("duration", 0) or 0),
                "price": data.get("price"),
                "price_unit": data.get("price_unit"),
                "start_time": data.get("start_time"),
                "end_time": data.get("end_time"),
                "answered_by": data.get("answered_by"),
                "forwarded_from": data.get("forwarded_from"),
                "caller_name": data.get("caller_name"),
            }
    except httpx.HTTPStatusError as exc:
        logger.error("Twilio reconciliation HTTP %s for %s", exc.response.status_code, call_sid)
        return {"status": "reconciliation_failed", "http_status": exc.response.status_code}
    except Exception as exc:
        logger.error("Twilio reconciliation error for %s: %s", call_sid, exc)
        return {"status": "reconciliation_failed", "error": str(exc)}


async def reconcile_pending_calls(max_age_hours: int = 24) -> Dict[str, Any]:
    """Reconcile all pending/active voice sessions with Twilio.

    Finds sessions in INITIATED or CONNECTED state that are older than
    a threshold, fetches their final status from Twilio, and updates
    all related records.
    """
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    reconciled = 0
    errors = 0

    async with async_session() as db:
        result = await db.execute(
            select(VoiceSession).where(
                VoiceSession.status.in_(["INITIATED", "CONNECTED"]),
                VoiceSession.created_at < cutoff,
            )
        )
        sessions = result.scalars().all()

        for session in sessions:
            outcomes = await db.execute(
                select(VoiceOutcome).where(
                    VoiceOutcome.voice_session_id == session.id,
                    VoiceOutcome.call_sid.is_not(None),
                ).order_by(VoiceOutcome.created_at.desc())
            )
            outcome = outcomes.scalars().first()
            if not outcome or not outcome.call_sid:
                continue

            reconciliation = await reconcile_call_status(outcome.call_sid)
            if reconciliation.get("status") in ("reconciliation_failed", "skipped"):
                errors += 1
                continue

            twilio_status = reconciliation.get("status", "unknown")
            status_map = {
                "completed": "COMPLETED",
                "busy": "MISSED",
                "no-answer": "MISSED",
                "canceled": "FAILED",
                "failed": "FAILED",
                "ringing": "CONNECTED",
                "in-progress": "CONNECTED",
            }
            new_state = status_map.get(twilio_status, session.status)

            session.status = new_state
            meta = session.voice_metadata or {}
            meta["reconciliation"] = {
                "twilio_status": twilio_status,
                "duration": reconciliation.get("duration"),
                "price": reconciliation.get("price"),
                "price_unit": reconciliation.get("price_unit"),
                "start_time": reconciliation.get("start_time"),
                "end_time": reconciliation.get("end_time"),
                "reconciled_at": datetime.utcnow().isoformat(),
            }
            session.voice_metadata = meta

            outcome.data = {
                **(outcome.data or {}),
                "reconciliation": reconciliation,
            }

            comm_req_result = await db.execute(
                select(CommunicationRequest).where(
                    CommunicationRequest.id == session.communication_request_id,
                )
            )
            comm_req = comm_req_result.scalar_one_or_none()
            if comm_req:
                result_data = comm_req.communication_result or {}
                result_data["reconciliation"] = reconciliation
                comm_req.communication_result = result_data

            reconciled += 1

        await db.commit()

    return {
        "reconciled": reconciled,
        "errors": errors,
        "cutoff": cutoff.isoformat(),
    }


async def get_twilio_account_health() -> Dict[str, Any]:
    """Enhanced Twilio health check with voice capability, sender validity, region."""
    config = load_twilio_config()
    if not config.ready:
        return {
            "configured": False,
            "voice_capable": False,
            "sender_valid": False,
            "account_status": "unconfigured",
            "region": None,
            "missing_fields": config.missing_fields,
        }

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{config.account_sid}.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, auth=(config.account_sid, config.auth_token))
            resp.raise_for_status()
            data = resp.json()

        account_status = data.get("status", "unknown")
        voice_capable = data.get("voice_enabled", True)
        sender_valid = bool(config.phone_number)
        region = data.get("subresource_uris", {})
        region_info = None
        if "incoming_phone_numbers" in region:
            region_info = "active_phone_numbers_present"

        return {
            "configured": True,
            "voice_capable": voice_capable,
            "sender_valid": sender_valid,
            "account_status": account_status,
            "region": region_info,
            "from_number_masked": f"***{config.phone_number[-4:]}" if config.phone_number else None,
        }
    except Exception as exc:
        logger.error("Twilio health check failed: %s", exc)
        return {
            "configured": True,
            "voice_capable": False,
            "sender_valid": bool(config.phone_number),
            "account_status": "check_failed",
            "error": str(exc),
        }
