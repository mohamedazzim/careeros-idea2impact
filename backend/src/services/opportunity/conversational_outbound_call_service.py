"""Conversational outbound opportunity call initiation for ElevenLabs ConvAI.

This service builds the live-agent payload used by the CareerOS Opportunity
Engagement Agent and starts the outbound call through either the existing
Make/webhook bridge or the direct ElevenLabs API.
"""

from __future__ import annotations

import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID as UUIDType

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.user import User
from src.observability.tracing import trace_async
from src.services.opportunity.conversation_retrieval_agent import get_conversation_retrieval_agent
from src.services.opportunity.voice_opportunity_agent import get_voice_opportunity_agent

logger = logging.getLogger(__name__)

ELEVENLABS_CONVAI_OUTBOUND_URL = "https://api.elevenlabs.io/v1/convai/twilio/outbound-call"


def _mask_phone_number(phone_number: str) -> str:
    digits = "".join(ch for ch in (phone_number or "") if ch.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item).strip() for item in value if item is not None and str(item).strip())
    return str(value).strip()


def _normalize_phone_number(phone_number: Any) -> str:
    raw = _safe_text(phone_number)
    if not raw:
        return ""
    if any(ch.isalpha() for ch in raw):
        return ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 10:
        return ""
    return f"+{digits}"


def _phone_digits(phone_number: Any) -> str:
    return "".join(ch for ch in _safe_text(phone_number) if ch.isdigit())


def _matches_sender_number(phone_number: str) -> bool:
    candidate_digits = _phone_digits(phone_number)
    if not candidate_digits:
        return False
    sender_candidates = [
        settings.TWILIO_PHONE_NUMBER,
        settings.TWILIO_TEST_PHONE_NUMBER,
    ]
    for sender in sender_candidates:
        sender_digits = _phone_digits(sender)
        if sender_digits and sender_digits == candidate_digits:
            return True
    return False


def _is_missing_to_number_error(error_text: str) -> bool:
    normalized = (error_text or "").lower()
    return "no 'to' number is specified" in normalized or "missing to number" in normalized


@dataclass(frozen=True)
class OutboundRecipientResolution:
    phone_number: str
    source: str
    reason: str = ""


def resolve_outbound_recipient_number(request_phone_number: Optional[str] = None) -> OutboundRecipientResolution:
    """Resolve an explicit outbound recipient number without ever using sender numbers."""
    requested = _normalize_phone_number(request_phone_number)
    fallback = _normalize_phone_number(settings.OUTBOUND_TEST_TO_NUMBER)

    if requested:
        if _matches_sender_number(requested):
            requested = ""
        else:
            return OutboundRecipientResolution(requested, "request_phone_number")

    if fallback:
        if _matches_sender_number(fallback):
            return OutboundRecipientResolution("", "OUTBOUND_TEST_TO_NUMBER", "sender_number_rejected")
        return OutboundRecipientResolution(fallback, "OUTBOUND_TEST_TO_NUMBER")

    return OutboundRecipientResolution("", "missing", "missing_recipient_number")


class ElevenLabsConversationalOutboundCallService:
    """Initiate a two-way ElevenLabs ConvAI outbound call."""

    def _transport_url(self) -> str:
        return (settings.PIPEDREAM_WEBHOOK_URL or "").strip()

    async def _resolve_user_name(self, db: AsyncSession, user_id: str) -> str:
        try:
            user_uuid = UUIDType(str(user_id))
        except Exception:
            return ""
        row = (await db.execute(select(User).where(User.id == user_uuid))).scalar_one_or_none()
        return (row.full_name or "") if row else ""

    def _language_code(self, intelligence: Dict[str, Any]) -> str:
        language = (
            intelligence.get("language_preferences", {}).get("language_code")
            or intelligence.get("language_preferences", {}).get("preferred_language")
            or "en"
        )
        normalized = str(language).strip().lower()
        if normalized.startswith("ta"):
            return "ta"
        return "en"

    def _build_dynamic_variables(
        self,
        *,
        user_name: str,
        opportunity: Dict[str, Any],
        intelligence: Dict[str, Any],
    ) -> Dict[str, Any]:
        job = intelligence.get("job", {})
        match = intelligence.get("match_intelligence", {})
        urgency = intelligence.get("urgency_intelligence", {})
        salary = intelligence.get("salary_intelligence", {})
        company = intelligence.get("company_intelligence", {})
        application = intelligence.get("application_intelligence", {})
        resume = intelligence.get("resume_intelligence", {})

        def pick(*values: Any) -> str:
            for value in values:
                text = _safe_text(value)
                if text:
                    return text
            return ""

        return {
            "user_name": pick(user_name, opportunity.get("user_name"), "there"),
            "job_title": pick(job.get("title"), opportunity.get("title")),
            "company": pick(job.get("company"), opportunity.get("company")),
            "company_description": pick(company.get("company_description"), opportunity.get("company_description")),
            "job_description": pick(job.get("description"), opportunity.get("description"), opportunity.get("job_description")),
            "location": pick(job.get("location"), opportunity.get("location")),
            "employment_type": pick(job.get("employment_type"), opportunity.get("employment_type")),
            "experience_level": pick(job.get("experience_level"), opportunity.get("experience_level")),
            "salary_range": pick(salary.get("salary_range"), opportunity.get("salary_range")),
            "match_score": pick(match.get("match_score"), opportunity.get("overall_score")),
            "matching_skills": pick(match.get("matched_skills"), opportunity.get("matched_skills"), opportunity.get("skills_required")),
            "missing_skills": pick(match.get("missing_skills"), opportunity.get("missing_skills"), opportunity.get("resume_gaps")),
            "recommended_skills": pick(resume.get("interview_focus_areas"), opportunity.get("recommended_skills"), opportunity.get("interview_focus_areas")),
            "deadline": pick(urgency.get("deadline"), application.get("deadline"), opportunity.get("deadline")),
            "application_url": pick(application.get("application_url"), opportunity.get("apply_url"), opportunity.get("source_url")),
            "urgency_score": pick(urgency.get("urgency_score"), opportunity.get("urgency_score")),
            "opportunity_priority_score": pick(application.get("opportunity_priority_score"), opportunity.get("opportunity_priority_score")),
            "resume_strengths": pick(resume.get("resume_strengths"), opportunity.get("resume_strengths"), opportunity.get("strengths")),
            "resume_gaps": pick(resume.get("resume_gaps"), opportunity.get("resume_gaps"), opportunity.get("gaps")),
            "interview_focus_areas": pick(resume.get("interview_focus_areas"), opportunity.get("interview_focus_areas")),
        }

    def _build_payload(
        self,
        *,
        user_id: str,
        phone_number: str,
        dynamic_variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        dynamic_variables = dict(dynamic_variables)
        dynamic_variables["phone_number"] = phone_number
        return {
            "To": phone_number,
            "to": phone_number,
            "to_number": phone_number,
            "phone_number": phone_number,
            "recipient_phone_number": phone_number,
            "destination_number": phone_number,
            "agent_id": (settings.ELEVENLABS_CONVAI_AGENT_ID or "").strip(),
            "agent_phone_number_id": (settings.ELEVENLABS_CONVAI_PHONE_NUMBER_ID or "").strip(),
            "conversation_initiation_client_data": {
                "type": "conversation_initiation_client_data",
                "dynamic_variables": dynamic_variables,
                "phone_number": phone_number,
                "user_id": user_id,
                "branch_id": None,
                "environment": settings.ENVIRONMENT,
            },
        }

    def _normalize_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return response if isinstance(response, dict) else {"raw_response": response}

    @staticmethod
    def _find_provider_value(key: str, *payloads: Any) -> Optional[str]:
        for payload in payloads:
            if isinstance(payload, dict):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
                nested = ElevenLabsConversationalOutboundCallService._find_provider_value(key, *payload.values())
                if nested:
                    return nested
            elif isinstance(payload, list):
                nested = ElevenLabsConversationalOutboundCallService._find_provider_value(key, *payload)
                if nested:
                    return nested
        return None

    @trace_async("elevenlabs_conversational_outbound_call")
    async def initiate_call(
        self,
        db: AsyncSession,
        *,
        communication_request_id: int,
        user_id: str,
        job_id: int | None,
        opportunity: Dict[str, Any],
        intelligence: Dict[str, Any],
        phone_number: str,
    ) -> Dict[str, Any]:
        transport_url = self._transport_url()
        agent_id = (settings.ELEVENLABS_CONVAI_AGENT_ID or "").strip()
        agent_phone_number_id = (settings.ELEVENLABS_CONVAI_PHONE_NUMBER_ID or "").strip()
        api_key = (settings.ELEVENLABS_API_KEY or "").strip()
        api_key_configured = bool(api_key)
        recipient_resolution = resolve_outbound_recipient_number(phone_number)
        resolved_phone_number = recipient_resolution.phone_number

        if not resolved_phone_number:
            return {
                "status": "blocked_no_phone",
                "provider": "elevenlabs_convai",
                "delivery_mode": "conversation_agent",
                "reason": recipient_resolution.reason or "missing_phone_number",
                "agent_id_configured": bool(agent_id),
                "agent_phone_number_id_configured": bool(agent_phone_number_id),
                "elevenlabs_api_key_configured": api_key_configured,
                "phone_number_source": recipient_resolution.source,
            }

        if not agent_id or not agent_phone_number_id:
            return {
                "status": "blocked_missing_config",
                "provider": "elevenlabs_convai",
                "delivery_mode": "conversation_agent",
                "reason": "missing_agent_config",
                "agent_id_configured": bool(agent_id),
                "agent_phone_number_id_configured": bool(agent_phone_number_id),
                "elevenlabs_api_key_configured": api_key_configured,
            }

        if not transport_url and not api_key_configured:
            return {
                "status": "blocked_missing_config",
                "provider": "elevenlabs_convai",
                "delivery_mode": "conversation_agent",
                "reason": "missing_elevenlabs_api_key",
                "agent_id_configured": bool(agent_id),
                "agent_phone_number_id_configured": bool(agent_phone_number_id),
                "elevenlabs_api_key_configured": False,
                "voice_session_id": None,
            }

        user_name = await self._resolve_user_name(db, user_id)
        dynamic_variables = self._build_dynamic_variables(
            user_name=user_name,
            opportunity=opportunity,
            intelligence=intelligence,
        )

        voice_agent = get_voice_opportunity_agent()
        voice_session, _ = await voice_agent.start_session(
            db,
            communication_request_id=communication_request_id,
            user_id=user_id,
            job_id=job_id,
            intelligence=intelligence,
            mode="conversation_agent",
            provider="elevenlabs_convai",
            agent_id=agent_id,
            agent_phone_number_id=agent_phone_number_id,
            dynamic_variables=dynamic_variables,
            prompt=None,
            first_message=None,
        )

        payload = self._build_payload(
            user_id=user_id,
            phone_number=resolved_phone_number,
            dynamic_variables=dynamic_variables,
        )

        masked_phone = _mask_phone_number(resolved_phone_number)
        logger.info(
            "Starting conversational opportunity call",
            extra={
                "outbound_call_mode": "conversation_agent",
                "provider": "elevenlabs_convai",
                "phone_number": masked_phone,
                "agent_id_configured": True,
                "agent_phone_number_id_configured": True,
                "elevenlabs_api_key_configured": api_key_configured,
                "transport": "webhook_bridge" if transport_url else "direct_api",
            },
        )

        if settings.CALL_ALERT_DRY_RUN or settings.OUTBOUND_CALL_DRY_RUN:
            result = {
                "status": "dry_run",
                "provider": "elevenlabs_convai",
                "delivery_mode": "conversation_agent",
                "call_status": "dry_run",
                "conversation_id": "dry_run_conversation",
                "call_sid": "dry_run_call",
                "transport": "dry_run",
                "dynamic_variables_present": bool(dynamic_variables),
                "elevenlabs_api_key_configured": api_key_configured,
                "payload": payload,
            }
            voice_session.voice_metadata = {
                **(voice_session.voice_metadata or {}),
                "transport": "dry_run",
                "payload": payload,
                "dynamic_variables": dynamic_variables,
            }
            voice_session.status = "STARTED"
            await db.flush()
            return result

        try:
            response_data: Dict[str, Any]
            if transport_url:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(transport_url, json=payload)
                try:
                    response_data = response.json()
                except ValueError:
                    response_data = {"raw_response": response.text}
                transport = "webhook_bridge"
                if response.status_code >= 400:
                    error_text = (response.text or "").strip()
                    provider_status = "provider_payload_error" if response.status_code == 400 and _is_missing_to_number_error(error_text) else "upstream_http_error"
                    reason = "bridge_missing_to_number" if provider_status == "provider_payload_error" else error_text[:500] or f"HTTP {response.status_code}"
                    voice_session.voice_provider = "elevenlabs_convai"
                    voice_session.status = "FAILED"
                    voice_session.voice_metadata = {
                        **(voice_session.voice_metadata or {}),
                        "mode": "conversation_agent",
                        "provider": "elevenlabs_convai",
                        "transport": transport,
                        "payload": payload,
                        "response": response_data,
                        "error": error_text[:500],
                        "call_status": "failed",
                        "provider_status": provider_status,
                        "started_at": datetime.utcnow().isoformat(),
                        "ended_at": datetime.utcnow().isoformat(),
                        "end_reason": "provider_payload_error" if provider_status == "provider_payload_error" else "upstream_http_error",
                        "transcript_status": "failed",
                        "dynamic_variables": dynamic_variables,
                    }
                    await db.flush()
                    logger.warning(
                        "Conversational opportunity call bridge returned HTTP error",
                        extra={
                            "outbound_call_mode": "conversation_agent",
                            "provider": "elevenlabs_convai",
                            "phone_number": masked_phone,
                            "provider_status": provider_status,
                            "reason": reason,
                        },
                    )
                    return {
                        "status": "failed",
                        "provider": "elevenlabs_convai",
                        "delivery_mode": "conversation_agent",
                        "call_status": "failed",
                        "provider_status": provider_status,
                        "reason": reason,
                        "transport": transport,
                        "dynamic_variables_present": bool(dynamic_variables),
                        "agent_id_configured": bool(agent_id),
                        "agent_phone_number_id_configured": bool(agent_phone_number_id),
                        "elevenlabs_api_key_configured": api_key_configured,
                        "payload": payload,
                        "response": response_data,
                        "voice_session_id": voice_session.id,
                    }
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        ELEVENLABS_CONVAI_OUTBOUND_URL,
                        json=payload,
                        headers={
                            "xi-api-key": api_key,
                            "Content-Type": "application/json",
                        },
                    )
                try:
                    response_data = response.json()
                except ValueError:
                    response_data = {"raw_response": response.text}
                transport = "direct_api"
                if response.status_code >= 400:
                    error_text = (response.text or "").strip()
                    provider_status = "provider_payload_error" if response.status_code == 400 and _is_missing_to_number_error(error_text) else "upstream_http_error"
                    reason = error_text[:500] or f"HTTP {response.status_code}"
                    voice_session.voice_provider = "elevenlabs_convai"
                    voice_session.status = "FAILED"
                    voice_session.voice_metadata = {
                        **(voice_session.voice_metadata or {}),
                        "mode": "conversation_agent",
                        "provider": "elevenlabs_convai",
                        "transport": transport,
                        "payload": payload,
                        "response": response_data,
                        "error": error_text[:500],
                        "call_status": "failed",
                        "provider_status": provider_status,
                        "started_at": datetime.utcnow().isoformat(),
                        "ended_at": datetime.utcnow().isoformat(),
                        "end_reason": "provider_payload_error" if provider_status == "provider_payload_error" else "upstream_http_error",
                        "transcript_status": "failed",
                        "dynamic_variables": dynamic_variables,
                    }
                    await db.flush()
                    logger.warning(
                        "Conversational opportunity call returned HTTP error",
                        extra={
                            "outbound_call_mode": "conversation_agent",
                            "provider": "elevenlabs_convai",
                            "phone_number": masked_phone,
                            "provider_status": provider_status,
                            "reason": reason,
                        },
                    )
                    return {
                        "status": "failed",
                        "provider": "elevenlabs_convai",
                        "delivery_mode": "conversation_agent",
                        "call_status": "failed",
                        "provider_status": provider_status,
                        "reason": reason,
                        "transport": transport,
                        "dynamic_variables_present": bool(dynamic_variables),
                        "agent_id_configured": bool(agent_id),
                        "agent_phone_number_id_configured": bool(agent_phone_number_id),
                        "elevenlabs_api_key_configured": api_key_configured,
                        "payload": payload,
                        "response": response_data,
                        "voice_session_id": voice_session.id,
                    }
        except Exception as exc:
            voice_session.voice_provider = "elevenlabs_convai"
            voice_session.status = "FAILED"
            voice_session.voice_metadata = {
                **(voice_session.voice_metadata or {}),
                "mode": "conversation_agent",
                "provider": "elevenlabs_convai",
                "transport": "failed",
                "payload": payload,
                "error": str(exc)[:500],
                "call_status": "failed",
                "started_at": datetime.utcnow().isoformat(),
                "ended_at": datetime.utcnow().isoformat(),
                "end_reason": "transport_error",
                "transcript_status": "failed",
                "dynamic_variables": dynamic_variables,
            }
            await db.flush()
            logger.warning(
                "Conversational opportunity call failed",
                extra={
                    "outbound_call_mode": "conversation_agent",
                    "provider": "elevenlabs_convai",
                    "phone_number": masked_phone,
                    "error": str(exc)[:200],
                },
            )
            return {
                "status": "failed",
                "provider": "elevenlabs_convai",
                "delivery_mode": "conversation_agent",
                "call_status": "failed",
                "reason": str(exc)[:500],
                "transport": "failed",
                "dynamic_variables_present": bool(dynamic_variables),
                "agent_id_configured": bool(agent_id),
                "agent_phone_number_id_configured": bool(agent_phone_number_id),
                "elevenlabs_api_key_configured": api_key_configured,
                "payload": payload,
                "voice_session_id": voice_session.id,
            }

        normalized = self._normalize_response(response_data)
        conversation_id = self._find_provider_value("conversation_id", normalized) or self._find_provider_value("conversationId", normalized)
        call_sid = self._find_provider_value("call_sid", normalized) or self._find_provider_value("callSid", normalized) or self._find_provider_value("sid", normalized)
        status = normalized.get("status") or normalized.get("call_status") or "started"

        if conversation_id:
            await get_conversation_retrieval_agent().capture_session(
                db,
                candidate_id=user_id,
                job_id=job_id,
                job_title=str(opportunity.get("title") or ""),
                company=str(opportunity.get("company") or ""),
                conversation_id=str(conversation_id),
                call_sid=call_sid,
                agent_id=agent_id,
            )

        voice_session.voice_provider = "elevenlabs_convai"
        voice_session.status = "STARTED"
        voice_session.voice_metadata = {
            **(voice_session.voice_metadata or {}),
            "mode": "conversation_agent",
            "provider": "elevenlabs_convai",
            "transport": transport,
            "payload": payload,
            "response": normalized,
            "conversation_id": conversation_id,
            "call_sid": call_sid,
            "call_status": status,
            "started_at": datetime.utcnow().isoformat(),
            "ended_at": None,
            "end_reason": None,
            "transcript_status": "pending",
            "dynamic_variables": dynamic_variables,
        }
        await db.flush()

        logger.info(
            "Conversational opportunity call initiated",
            extra={
                "outbound_call_mode": "conversation_agent",
                "provider": "elevenlabs_convai",
                "phone_number": masked_phone,
                "conversation_id": conversation_id,
                "call_sid": call_sid,
                "call_status": status,
            },
        )

        return {
            "status": "started",
            "provider": "elevenlabs_convai",
            "delivery_mode": "conversation_agent",
            "call_status": status,
            "conversation_id": conversation_id,
            "call_sid": call_sid,
            "transport": transport,
            "dynamic_variables_present": bool(dynamic_variables),
            "agent_id_configured": bool(agent_id),
            "agent_phone_number_id_configured": bool(agent_phone_number_id),
            "elevenlabs_api_key_configured": api_key_configured,
            "payload": payload,
            "response": normalized,
            "voice_session_id": voice_session.id,
        }


_service: Optional[ElevenLabsConversationalOutboundCallService] = None


def get_elevenlabs_conversational_outbound_call_service() -> ElevenLabsConversationalOutboundCallService:
    global _service
    if _service is None:
        _service = ElevenLabsConversationalOutboundCallService()
    return _service
