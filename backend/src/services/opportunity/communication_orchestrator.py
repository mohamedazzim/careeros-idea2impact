"""RC3.1 Communication Orchestrator.

The Alert Agent decides. This orchestrator delivers.
Supports VOICE_CALL, WHATSAPP, EMAIL, DASHBOARD_ONLY channels.
Tracks decision_reason, decision_confidence, delivery attempts, provider latency.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select

from src.db.session import async_session
from src.models.jobs import CommunicationRequest
from src.services.opportunity.conversation_context import get_opportunity_conversation_context_builder
from src.services.opportunity.outcome_intelligence import get_outcome_intelligence_service
from src.services.opportunity.pipedream_adapter import get_pipedream_adapter
from src.services.opportunity.conversational_outbound_call_service import (
    get_elevenlabs_conversational_outbound_call_service,
)
from src.runtime.workers.distributed_lock_manager import get_lock_manager


CHANNEL_MAP = {
    "CALL": "VOICE_CALL",
    "VOICE": "VOICE_CALL",
    "VOICE_CALL": "VOICE_CALL",
    "WHATSAPP": "WHATSAPP",
    "EMAIL": "EMAIL",
    "DASHBOARD": "DASHBOARD_ONLY",
    "DASHBOARD_ONLY": "DASHBOARD_ONLY",
    "PUSH_NOTIFICATION": "PUSH_NOTIFICATION",
    "SMS": "SMS",
    "LINKEDIN": "LINKEDIN",
}

ROUTING_MATRIX = {
    "VOICE_CALL": {"requires_phone": True, "provider": "elevenlabs_convai", "priority": 1, "mode": "conversation_agent"},
    "WHATSAPP": {"requires_phone": True, "provider": "pipedream", "priority": 2},
    "EMAIL": {"requires_phone": False, "provider": "pipedream", "priority": 3},
    "SMS": {"requires_phone": True, "provider": "twilio", "priority": 4},
    "DASHBOARD_ONLY": {"requires_phone": False, "provider": "career_os", "priority": 5},
    "LINKEDIN": {"requires_phone": False, "provider": "future", "priority": 6},
    "PUSH_NOTIFICATION": {"requires_phone": False, "provider": "future", "priority": 7},
}

VOICE_DELIVERY_LOCK_TTL_SECONDS = 600
VOICE_ACTIVE_STATUSES = {"started", "in_progress"}


class CommunicationOrchestrator:
    def _channel(self, decision: str) -> str:
        return CHANNEL_MAP.get((decision or "DASHBOARD_ONLY").upper(), "DASHBOARD_ONLY")

    def _decision_payload(self, opportunity: Dict[str, Any], decision: str) -> tuple[str, Dict[str, Any], float]:
        factors = {
            "match_score": opportunity.get("overall_score"),
            "freshness_score": opportunity.get("freshness_score"),
            "opportunity_priority_score": opportunity.get("opportunity_priority_score"),
            "urgency_score": opportunity.get("urgency_score"),
            "lifecycle_state": opportunity.get("lifecycle_state"),
            "apply_url_present": bool(opportunity.get("source_url") or opportunity.get("apply_url")),
            "domain": opportunity.get("career_domain"),
            "career_family": opportunity.get("career_family"),
        }
        reason = (
            f"{decision} selected by CareerOS Alert Agent from match={factors['match_score']}, "
            f"freshness={factors['freshness_score']}, priority={factors['opportunity_priority_score']}."
        )
        confidence = 0.9 if decision in ("CALL", "VOICE_CALL") else 0.75
        return reason, factors, confidence

    def _pipedream_payload(
        self,
        *,
        user_id: str,
        opportunity: Dict[str, Any],
        context: Dict[str, Any],
        channel: str,
        correlation_id: str,
    ) -> Dict[str, Any]:
        return {
            "correlation_id": correlation_id,
            "channel": channel,
            "user_profile": {
                "user_id": user_id,
            },
            "job_information": context.get("job", {}),
            "match_intelligence": context.get("match_intelligence", {}),
            "urgency_intelligence": context.get("urgency_intelligence", {}),
            "salary_intelligence": context.get("salary_intelligence", {}),
            "deadline_intelligence": {
                "deadline": opportunity.get("deadline"),
                "freshness_score": opportunity.get("freshness_score"),
            },
            "skill_gap_intelligence": {
                "matched_skills": context.get("match_intelligence", {}).get("matched_skills", []),
                "missing_skills": context.get("match_intelligence", {}).get("missing_skills", []),
            },
            "language_preferences": context.get("language_preferences", {}),
            "career_memory_summary": context.get("career_memory_summary", []),
        }

    async def deliver(
        self,
        *,
        user_id: str,
        opportunity: Dict[str, Any],
        decision: str,
        phone_number: Optional[str] = None,
        communication_request_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        channel = self._channel(decision)
        routing = ROUTING_MATRIX.get(channel, ROUTING_MATRIX["DASHBOARD_ONLY"])
        job_id = int(opportunity.get("job_id") or 0) or None
        correlation_id = str(uuid.uuid4())
        decision_reason, decision_factors, decision_confidence = self._decision_payload(opportunity, decision)

        t0 = time.time()
        async with async_session() as db:
            request: CommunicationRequest | None = None
            if communication_request_id is not None:
                request = (await db.execute(
                    select(CommunicationRequest).where(CommunicationRequest.id == communication_request_id)
                )).scalar_one_or_none()
                if request is not None:
                    correlation_id = request.correlation_id or correlation_id

            if request is not None and request.communication_status in VOICE_ACTIVE_STATUSES:
                existing_result = dict(request.communication_result or {})
                return {
                    "correlation_id": correlation_id,
                    "communication_request_id": request.id,
                    "channel": channel,
                    "routing": routing,
                    "webhook_status": request.webhook_status or "skipped_voice_call",
                    "pipedream_response": request.pipedream_response or {"reason": "voice_call_already_started"},
                    "context_uid": None,
                    "outbound_call_mode": "conversation_agent",
                    "provider": "elevenlabs_convai",
                    "delivery_status": request.communication_status,
                    "provider_status": existing_result.get("provider_status", "delivery_in_progress"),
                    "conversation_id": existing_result.get("conversation_id"),
                    "call_sid": existing_result.get("call_sid"),
                    "call_status": existing_result.get("call_status", request.communication_status),
                    "voice_session_id": existing_result.get("voice_session_id"),
                    "agent_id_configured": existing_result.get("agent_id_configured"),
                    "agent_phone_number_id_configured": existing_result.get("agent_phone_number_id_configured"),
                    "dynamic_variables_present": existing_result.get("dynamic_variables_present"),
                    "provider_latency": 0.0,
                    "webhook_latency": 0.0,
                    "duplicate_suppressed": True,
                }

            if request is None:
                request = CommunicationRequest(
                    correlation_id=correlation_id,
                    user_id=user_id,
                    job_id=job_id,
                    opportunity_id=str(opportunity.get("id") or ""),
                    channel=channel,
                    communication_status="pending",
                    communication_provider=routing["provider"],
                    decision_reason=decision_reason,
                    decision_factors=decision_factors,
                    decision_confidence=decision_confidence,
                    pipedream_request={},
                )
                db.add(request)
                await db.flush()
                # Persist the communication request before any external provider work.
                # This guarantees the dashboard and audit trail keep the alert record
                # even if ElevenLabs or Twilio fails later in the flow.
                await db.commit()
            else:
                request.channel = channel
                request.communication_status = "pending"
                request.communication_provider = routing["provider"]
                request.decision_reason = decision_reason
                request.decision_factors = decision_factors
                request.decision_confidence = decision_confidence
                await db.commit()

            context = {}
            context_row = None
            try:
                context_row = await get_opportunity_conversation_context_builder().build(
                    db,
                    user_id=user_id,
                    opportunity=opportunity,
                )
                context = context_row.conversation_context
            except Exception as exc:
                # Keep the delivery pipeline alive even if context assembly fails.
                # The alert row is already committed above, so we can continue with
                # a reduced payload and still preserve runtime evidence.
                context = {}
                context_row = None

            if channel != "VOICE_CALL":
                pipedream_payload = self._pipedream_payload(
                    user_id=user_id,
                    opportunity=opportunity,
                    context=context,
                    channel=channel,
                    correlation_id=correlation_id,
                )

                request.pipedream_request = pipedream_payload
                await db.commit()

                webhook_status, webhook_response = await get_pipedream_adapter().send_with_retry(
                    pipedream_payload, correlation_id=correlation_id,
                )
                request.webhook_status = webhook_status
                request.pipedream_response = webhook_response
            else:
                webhook_status = "skipped_voice_call"
                webhook_response = {"reason": "voice_call_uses_conversational_transport"}
                request.pipedream_request = {
                    "skipped": True,
                    "reason": "voice_call_uses_conversational_transport",
                    "correlation_id": correlation_id,
                }
                request.webhook_status = webhook_status
                request.pipedream_response = webhook_response

            result: Dict[str, Any] = {
                "correlation_id": correlation_id,
                "communication_request_id": request.id,
                "channel": channel,
                "routing": routing,
                "webhook_status": webhook_status,
                "pipedream_response": webhook_response,
                "context_uid": context_row.context_uid if context_row else None,
            }

            if channel == "VOICE_CALL":
                delivery_lock_key = self._delivery_lock_key(request)
                lock_mgr = get_lock_manager()
                lease = await lock_mgr.acquire(
                    delivery_lock_key,
                    worker_id="communication_orchestrator",
                    ttl=VOICE_DELIVERY_LOCK_TTL_SECONDS,
                )
                if not lease:
                    existing_result = dict(request.communication_result or {})
                    return {
                        **result,
                        "delivery_status": request.communication_status or "duplicate_suppressed",
                        "provider_status": existing_result.get("provider_status", "delivery_lock_active"),
                        "duplicate_suppressed": True,
                    }

                try:
                    request.communication_status = "started"
                    request.communication_provider = "elevenlabs_convai"
                    request.communication_result = {
                        **(request.communication_result or {}),
                        "status": "started",
                        "delivery_status": "started",
                        "provider_status": "dispatching",
                        "provider": "elevenlabs_convai",
                    }
                    await db.commit()

                    voice_agent = get_elevenlabs_conversational_outbound_call_service()
                    call_result = await voice_agent.initiate_call(
                        db,
                        communication_request_id=request.id,
                        user_id=user_id,
                        job_id=job_id,
                        opportunity=opportunity,
                        intelligence=context,
                        phone_number=phone_number or "",
                    )
                    voice_status = call_result.get("call_status", "started")
                    request.communication_provider = "elevenlabs_convai"
                    request.communication_status = voice_status if voice_status != "started" else "started"
                    request.communication_result = call_result
                    request.delivery_attempts = 1 if phone_number else 0
                    result.update({
                        "outbound_call_mode": "conversation_agent",
                        "provider": "elevenlabs_convai",
                        "delivery_status": request.communication_status,
                        "conversation_id": call_result.get("conversation_id"),
                        "call_sid": call_result.get("call_sid"),
                        "call_status": call_result.get("call_status"),
                        "voice_session_id": call_result.get("voice_session_id"),
                        "agent_id_configured": call_result.get("agent_id_configured"),
                        "agent_phone_number_id_configured": call_result.get("agent_phone_number_id_configured"),
                        "dynamic_variables_present": call_result.get("dynamic_variables_present"),
                    })
                finally:
                    await lock_mgr.release(delivery_lock_key)
            else:
                status = "queued" if channel in {"WHATSAPP", "EMAIL"} else "delivered"
                request.communication_provider = "pipedream" if webhook_status == "delivered" else "career_os"
                request.communication_status = status if webhook_status != "failed" else "failed"
                request.communication_result = {
                    "message": "Communication request prepared for delivery.",
                    "channel": channel,
                }
                request.delivery_attempts = 1 if webhook_status == "delivered" else 0
                result.update({
                    "delivery_status": request.communication_status,
                    "communication_result": request.communication_result,
                })

            provider_latency = time.time() - t0
            result["provider_latency"] = provider_latency
            result["webhook_latency"] = provider_latency

            await get_outcome_intelligence_service().record_event(
                db,
                user_id=user_id,
                job_id=job_id,
                communication_request_id=request.id,
                status="NOTIFIED" if request.communication_status in {"sent", "delivered", "partial", "queued", "initiated", "started"} else "IGNORED",
                channel=channel,
                data=result,
            )
            await get_outcome_intelligence_service().refresh_metrics(db, user_id=user_id)
            await db.commit()
            return result

    @staticmethod
    def _delivery_lock_key(request: CommunicationRequest) -> str:
        return f"opp_call_delivery:{request.id or request.correlation_id}"

    @staticmethod
    def _find_provider_value(key: str, *payloads: Any) -> Optional[str]:
        for payload in payloads:
            if isinstance(payload, dict):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
                nested = CommunicationOrchestrator._find_provider_value(key, *payload.values())
                if nested:
                    return nested
            elif isinstance(payload, list):
                nested = CommunicationOrchestrator._find_provider_value(key, *payload)
                if nested:
                    return nested
        return None


def get_communication_orchestrator() -> CommunicationOrchestrator:
    return CommunicationOrchestrator()
