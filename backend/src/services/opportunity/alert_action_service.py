"""Alert Action Service — bridges alert decisions to delivery.

CALL decisions trigger outbound delivery immediately.
EMAIL and WHATSAPP continue through the communication pipeline.
DASHBOARD_ONLY creates a dashboard notification record.
IGNORE/NONE record the decision only.

Safety rules:
- dry_run=True: record decision + simulate delivery path, never send outbound
- CALL auto-triggers when match_score >= CALL_ALERT_MIN_MATCH_SCORE
- EMAIL/WHATSAPP follow the configured communication path
- Provider health checked before delivery attempt
- All actions audited via AlertDecisionAudit
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from src.core.config import settings
from src.db.session import async_session
from src.models.approvals import Approval
from src.models.jobs import AlertDecisionAudit, CommunicationRequest
from src.runtime.workers.distributed_lock_manager import get_lock_manager

logger = logging.getLogger(__name__)

ACTIONABLE_DECISIONS = {"CALL", "EMAIL", "WHATSAPP"}
DASHBOARD_DECISIONS = {"DASHBOARD_ONLY"}
SUPPRESSED_DECISIONS = {"IGNORE", "NONE"}

CHANNEL_LABELS = {
    "CALL": "phone_call",
    "EMAIL": "email",
    "WHATSAPP": "whatsapp",
    "DASHBOARD_ONLY": "dashboard",
    "IGNORE": "none",
    "NONE": "none",
}

CALL_DISPATCH_LOCK_TTL_SECONDS = 600
CALL_DUPLICATE_TERMINAL_STATUSES = {
    "failed",
    "cancelled",
    "skipped_duplicate",
    "blocked_missing_provider",
    "blocked_no_phone",
    "blocked_missing_config",
    "service_error",
    "partial",
}

APPROVAL_CHANNEL_MAP = {
    "CALL": "PHONE_ALERT",
    "EMAIL": "EMAIL",
    "WHATSAPP": "EMAIL",
    "DASHBOARD_ONLY": "APPLICATION_PACKAGE",
}


@dataclass
class ActionResult:
    decision: str
    communication_request_id: Optional[int] = None
    delivery_status: str = "pending"
    provider_status: str = "awaiting_delivery"
    dry_run: bool = False
    reason: str = ""
    audit_id: Optional[int] = None


class AlertActionService:
    """Single entry point for alert decision → delivery pipeline."""

    async def process_decision(
        self,
        *,
        user_id: str,
        job_id: int,
        opportunity: Dict[str, Any],
        decision: str,
        decision_reason: str = "",
        decision_scores: Optional[Dict[str, Any]] = None,
        decision_confidence: float = 0.75,
        dry_run: bool = False,
        phone_number: Optional[str] = None,
    ) -> ActionResult:
        t0 = time.monotonic()
        decision = (decision or "NONE").upper()

        audit_id = await self._write_audit(
            user_id=user_id,
            job_id=job_id,
            decision=decision,
            reason=decision_reason,
            scores=decision_scores,
            confidence=decision_confidence,
        )

        if decision in SUPPRESSED_DECISIONS:
            return ActionResult(
                decision=decision,
                delivery_status="suppressed",
                provider_status="no_action",
                dry_run=dry_run,
                reason=decision_reason or f"decision_{decision.lower()}",
                audit_id=audit_id,
            )

        if decision in DASHBOARD_DECISIONS:
            cr_id = await self._create_communication_request(
                user_id=user_id,
                job_id=job_id,
                opportunity=opportunity,
                channel="DASHBOARD_ONLY",
                decision_reason=decision_reason,
                decision_confidence=decision_confidence,
            )
            return ActionResult(
                decision=decision,
                communication_request_id=cr_id,
                delivery_status="delivered_to_dashboard",
                provider_status="dashboard_visible",
                dry_run=dry_run,
                reason="Dashboard notification created",
                audit_id=audit_id,
            )

        if decision in ACTIONABLE_DECISIONS:
            cr_id: Optional[int] = None
            if decision == "CALL":
                from src.agents.opportunity_alert_agent import is_call_eligible
                match_score = (opportunity or {}).get("overall_score")
                if not is_call_eligible(match_score):
                    return ActionResult(
                        decision="CALL",
                        delivery_status="blocked_by_threshold",
                        provider_status="match_score_below_call_threshold",
                        dry_run=dry_run,
                        reason=(
                            f"CALL blocked: match_score={match_score} "
                            f"below threshold {settings.CALL_ALERT_MIN_MATCH_SCORE}"
                        ),
                        audit_id=audit_id,
                    )

                duplicate = await self._check_duplicate_call(
                    user_id=user_id, job_id=job_id
                )
                if duplicate:
                    return ActionResult(
                        decision=decision,
                        delivery_status="duplicate_suppressed",
                        provider_status="cooldown_active",
                        dry_run=dry_run,
                        reason=f"Duplicate CALL suppressed: {duplicate}",
                        audit_id=audit_id,
                    )

                lock_key = self._build_call_lock_key(user_id=user_id, job_id=job_id)
                lock_mgr = get_lock_manager()
                lease = await lock_mgr.acquire(
                    lock_key,
                    worker_id="alert_action_service",
                    ttl=CALL_DISPATCH_LOCK_TTL_SECONDS,
                )
                if not lease:
                    return ActionResult(
                        decision=decision,
                        delivery_status="duplicate_suppressed",
                        provider_status="dispatch_lock_active",
                        dry_run=dry_run,
                        reason="Duplicate CALL suppressed: another dispatch is already in progress",
                        audit_id=audit_id,
                    )

                try:
                    duplicate = await self._check_duplicate_call(
                        user_id=user_id, job_id=job_id
                    )
                    if duplicate:
                        return ActionResult(
                            decision=decision,
                            delivery_status="duplicate_suppressed",
                            provider_status="cooldown_active",
                            dry_run=dry_run,
                            reason=f"Duplicate CALL suppressed: {duplicate}",
                            audit_id=audit_id,
                        )

                    call_idempotency_key = self._build_call_idempotency_key(
                        user_id=user_id,
                        job_id=job_id,
                    )
                    cr_id = await self._create_communication_request(
                        user_id=user_id,
                        job_id=job_id,
                        opportunity=opportunity,
                        channel=decision,
                        decision_reason=decision_reason,
                        decision_confidence=decision_confidence,
                        idempotency_key=call_idempotency_key,
                    )

                    from src.services.opportunity.conversational_outbound_call_service import resolve_outbound_recipient_number
                    recipient_resolution = resolve_outbound_recipient_number(phone_number)
                    resolved_phone_number = recipient_resolution.phone_number

                    is_dry_run = dry_run or settings.CALL_ALERT_DRY_RUN or settings.OUTBOUND_CALL_DRY_RUN

                    if is_dry_run:
                        if cr_id:
                            async with async_session() as db2:
                                from sqlalchemy import select as sa_select2
                                cr = (await db2.execute(
                                    sa_select2(CommunicationRequest).where(
                                        CommunicationRequest.id == cr_id
                                    )
                                )).scalar_one_or_none()
                                if cr:
                                    cr.communication_status = "dry_run"
                                    cr.communication_result = {"dry_run": True, "twilio_called": False, "elevenlabs_called": False}
                                    await db2.commit()

                        return ActionResult(
                            decision=decision,
                            communication_request_id=cr_id,
                            delivery_status="dry_run",
                            provider_status="simulated_no_provider_call",
                            dry_run=True,
                            reason=f"[DRY RUN] CALL auto-triggered: no Twilio/ElevenLabs called",
                            audit_id=audit_id,
                        )

                    if not resolved_phone_number:
                        if cr_id:
                            async with async_session() as db_cr:
                                from sqlalchemy import select as sa_select_cr
                                cr = (await db_cr.execute(
                                    sa_select_cr(CommunicationRequest).where(
                                        CommunicationRequest.id == cr_id
                                    )
                                )).scalar_one_or_none()
                                if cr:
                                    cr.communication_status = "blocked_no_phone"
                                    cr.communication_result = {
                                        "blocked": True,
                                        "reason": recipient_resolution.reason or "missing_phone_number",
                                        "source": recipient_resolution.source,
                                    }
                                    await db_cr.commit()
                        return ActionResult(
                            decision=decision,
                            communication_request_id=cr_id,
                            delivery_status="blocked_no_phone",
                            provider_status="missing_phone_number",
                            dry_run=False,
                            reason="CALL blocked: no valid outbound recipient number available for user",
                            audit_id=audit_id,
                        )

                    transport_url = (settings.PIPEDREAM_WEBHOOK_URL or "").strip()
                    api_key = (settings.ELEVENLABS_API_KEY or "").strip()
                    if not transport_url and not api_key:
                        if cr_id:
                            async with async_session() as db_cr:
                                from sqlalchemy import select as sa_select_cr
                                cr = (await db_cr.execute(
                                    sa_select_cr(CommunicationRequest).where(
                                        CommunicationRequest.id == cr_id
                                    )
                                )).scalar_one_or_none()
                                if cr:
                                    cr.communication_status = "blocked_missing_config"
                                    cr.communication_result = {
                                        "blocked": True,
                                        "reason": "missing_elevenlabs_api_key",
                                        "bridge_configured": bool(transport_url),
                                        "elevenlabs_api_key_configured": bool(api_key),
                                    }
                                    await db_cr.commit()
                        return ActionResult(
                            decision=decision,
                            communication_request_id=cr_id,
                            delivery_status="blocked_missing_config",
                            provider_status="missing_elevenlabs_api_key",
                            dry_run=False,
                            reason="CALL blocked: ElevenLabs API key or Make bridge missing",
                            audit_id=audit_id,
                        )

                    from src.services.opportunity.communication_orchestrator import get_communication_orchestrator
                    orchestrator = get_communication_orchestrator()
                    call_result = await orchestrator.deliver(
                        user_id=user_id,
                        opportunity=opportunity,
                        decision=decision,
                        phone_number=resolved_phone_number,
                        communication_request_id=cr_id,
                    )
                    delivery_status = call_result.get("delivery_status", "call_attempted")
                    provider_status = call_result.get("provider_status", "unknown")

                    if cr_id:
                        async with async_session() as db2:
                            from sqlalchemy import select as sa_select2
                            cr = (await db2.execute(
                                sa_select2(CommunicationRequest).where(
                                    CommunicationRequest.id == cr_id
                                )
                            )).scalar_one_or_none()
                            if cr:
                                cr.communication_status = delivery_status
                                cr.communication_result = call_result
                                cr.delivery_attempts = (cr.delivery_attempts or 0) + 1
                                await db2.commit()

                    return ActionResult(
                        decision=decision,
                        communication_request_id=cr_id,
                        delivery_status=delivery_status,
                        provider_status=provider_status,
                        dry_run=dry_run,
                        reason=f"CALL auto-triggered: {delivery_status}",
                        audit_id=audit_id,
                    )
                finally:
                    await lock_mgr.release(lock_key)

            cr_id = await self._create_communication_request(
                user_id=user_id,
                job_id=job_id,
                opportunity=opportunity,
                channel=decision,
                decision_reason=decision_reason,
                decision_confidence=decision_confidence,
            )
            return ActionResult(
                decision=decision,
                communication_request_id=cr_id,
                delivery_status="queued",
                provider_status="awaiting_delivery",
                dry_run=dry_run,
                reason="Communication request created",
                audit_id=audit_id,
            )

        return ActionResult(
            decision=decision,
            delivery_status="unknown_decision",
            provider_status="no_action",
            reason=f"Unhandled decision type: {decision}",
            audit_id=audit_id,
        )

    async def execute_approved_action(
        self,
        *,
        approval_id: int,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Called when human approves an alert decision in the approval center."""
        async with async_session() as db:
            from sqlalchemy import select
            approval = (await db.execute(
                select(Approval).where(Approval.id == approval_id)
            )).scalar_one_or_none()

            if not approval:
                return {"status": "error", "message": "Approval not found"}

            content = approval.draft_content or {}
            decision = content.get("decision", "NONE")
            communication_request_id = content.get("communication_request_id")
            job_id = content.get("job_id")
            phone_number = content.get("phone_number")
            opportunity = content.get("opportunity_snapshot", {})
            from src.services.opportunity.conversational_outbound_call_service import resolve_outbound_recipient_number
            recipient_resolution = resolve_outbound_recipient_number(phone_number)
            phone_number = recipient_resolution.phone_number

            if dry_run:
                return {
                    "status": "dry_run",
                    "decision": decision,
                    "message": f"[DRY RUN] Would execute {decision} delivery",
                }

            if decision in ("CALL", "EMAIL", "WHATSAPP"):
                if decision == "CALL" and not phone_number:
                    return {
                        "status": "error",
                        "decision": decision,
                        "message": "CALL blocked: no valid outbound recipient number available",
                        "phone_number_source": recipient_resolution.source,
                        "phone_number_reason": recipient_resolution.reason,
                    }
                from src.services.opportunity.communication_orchestrator import get_communication_orchestrator
                result = await get_communication_orchestrator().deliver(
                    user_id=approval.user_id,
                    opportunity=opportunity,
                    decision=decision,
                    phone_number=phone_number,
                    communication_request_id=communication_request_id,
                )

                if communication_request_id:
                    cr = (await db.execute(
                        select(CommunicationRequest).where(CommunicationRequest.id == communication_request_id)
                    )).scalar_one_or_none()
                    if cr:
                        cr.communication_status = result.get("delivery_status", "delivered")
                        cr.communication_result = result
                        cr.delivery_attempts = (cr.delivery_attempts or 0) + 1
                        await db.commit()

                return {
                    "status": "executed",
                    "decision": decision,
                    "delivery_status": result.get("delivery_status"),
                    "correlation_id": result.get("correlation_id"),
                }

            return {"status": "no_delivery_needed", "decision": decision}

    async def _create_approval(
        self,
        *,
        user_id: str,
        job_id: int,
        opportunity: Dict[str, Any],
        decision: str,
        communication_request_id: Optional[int],
        decision_reason: str,
        decision_confidence: float,
        phone_number: Optional[str] = None,
    ) -> str:
        channel = APPROVAL_CHANNEL_MAP.get(decision, "APPLICATION_PACKAGE")
        title = self._approval_title(decision, opportunity)
        draft_content = {
            "decision": decision,
            "job_id": job_id,
            "communication_request_id": communication_request_id,
            "opportunity_snapshot": {
                "id": opportunity.get("id"),
                "title": opportunity.get("title"),
                "company": opportunity.get("company"),
                "overall_score": opportunity.get("overall_score"),
                "source_url": opportunity.get("source_url") or opportunity.get("apply_url"),
            },
            "phone_number": phone_number,
            "decision_reason": decision_reason,
            "decision_scores": {
                "match_score": opportunity.get("overall_score"),
                "freshness_score": opportunity.get("freshness_score"),
                "opportunity_priority_score": opportunity.get("opportunity_priority_score"),
            },
            "decision_confidence": decision_confidence,
            "generated_by": "alert_action_service",
        }

        async with async_session() as db:
            approval = Approval(
                user_id=user_id,
                title=title,
                channel=channel,
                status="pending",
                draft_content=draft_content,
                auto_generated=True,
                confidence=decision_confidence,
            )
            db.add(approval)
            await db.flush()
            uid = approval.approval_uid
            await db.commit()
            return uid

    async def _create_communication_request(
        self,
        *,
        user_id: str,
        job_id: int,
        opportunity: Dict[str, Any],
        channel: str,
        decision_reason: str,
        decision_confidence: float,
        idempotency_key: Optional[str] = None,
    ) -> int:
        from src.services.opportunity.communication_orchestrator import CHANNEL_MAP, ROUTING_MATRIX
        mapped_channel = CHANNEL_MAP.get(channel, "DASHBOARD_ONLY")
        routing = ROUTING_MATRIX.get(mapped_channel, ROUTING_MATRIX["DASHBOARD_ONLY"])
        correlation_id = idempotency_key or str(uuid.uuid4())

        async with async_session() as db:
            if idempotency_key and mapped_channel == "VOICE_CALL":
                from sqlalchemy import desc as sa_desc, select as sa_select
                existing = (await db.execute(
                    sa_select(CommunicationRequest)
                    .where(
                        CommunicationRequest.correlation_id == correlation_id,
                        CommunicationRequest.user_id == user_id,
                        CommunicationRequest.job_id == job_id,
                        CommunicationRequest.channel == mapped_channel,
                        CommunicationRequest.communication_status.notin_(CALL_DUPLICATE_TERMINAL_STATUSES),
                    )
                    .order_by(sa_desc(CommunicationRequest.created_at))
                    .limit(1)
                )).scalar_one_or_none()
                if existing:
                    return existing.id

            cr = CommunicationRequest(
                correlation_id=correlation_id,
                user_id=user_id,
                job_id=job_id,
                opportunity_id=str(opportunity.get("id") or ""),
                channel=mapped_channel,
                communication_status="pending_approval",
                communication_provider=routing.get("provider", "career_os"),
                decision_reason=decision_reason,
                decision_factors={
                    "match_score": opportunity.get("overall_score"),
                    "freshness_score": opportunity.get("freshness_score"),
                    "opportunity_priority_score": opportunity.get("opportunity_priority_score"),
                },
                decision_confidence=decision_confidence,
            )
            db.add(cr)
            await db.flush()
            cr_id = cr.id
            await db.commit()
        return cr_id

    async def _check_duplicate_call(
        self,
        *,
        user_id: str,
        job_id: int,
    ) -> Optional[str]:
        from datetime import timedelta
        cooldown = timedelta(hours=settings.CALL_ALERT_COOLDOWN_HOURS)
        cutoff = datetime.utcnow() - cooldown
        async with async_session() as db:
            from sqlalchemy import select, or_
            stmt = (
                select(CommunicationRequest)
                .where(
                    CommunicationRequest.user_id == user_id,
                    CommunicationRequest.job_id == job_id,
                    or_(
                        CommunicationRequest.channel == "VOICE_CALL",
                        CommunicationRequest.channel == "phone_call",
                    ),
                    CommunicationRequest.communication_status.notin_(
                        [
                            "failed",
                            "cancelled",
                            "dry_run",
                            "skipped_duplicate",
                            "blocked_missing_provider",
                            "blocked_no_phone",
                            "service_error",
                            "partial",
                        ]
                    ),
                    CommunicationRequest.created_at >= cutoff,
                )
                .order_by(CommunicationRequest.created_at.desc())
                .limit(1)
            )
            existing = (await db.execute(stmt)).scalars().first()
            if existing:
                return f"recent_call_within_{settings.CALL_ALERT_COOLDOWN_HOURS}h (id={existing.id})"
        return None

    @staticmethod
    def _build_call_idempotency_key(*, user_id: str, job_id: int) -> str:
        return f"opportunity_call:{user_id}:{job_id}:VOICE_CALL"

    @staticmethod
    def _build_call_lock_key(*, user_id: str, job_id: int) -> str:
        return f"opp_call_dispatch:{user_id}:{job_id}:VOICE_CALL"

    async def _write_audit(
        self,
        *,
        user_id: str,
        job_id: int,
        decision: str,
        reason: str,
        scores: Optional[Dict[str, Any]],
        confidence: float,
    ) -> Optional[int]:
        if not job_id:
            return None
        try:
            async with async_session() as db:
                audit = AlertDecisionAudit(
                    user_id=user_id,
                    job_id=job_id,
                    decision=decision,
                    channel=CHANNEL_LABELS.get(decision, "none"),
                    reason=reason or f"decision_{decision.lower()}",
                    scores=scores,
                    decision_confidence=confidence,
                )
                db.add(audit)
                await db.flush()
                audit_id = audit.id
                await db.commit()
                return audit_id
        except Exception as exc:
            logger.warning("Audit write failed (job_id=%s): %s", job_id, exc)
            return None

    @staticmethod
    def _approval_title(decision: str, opportunity: Dict[str, Any]) -> str:
        title = opportunity.get("title", "Unknown Role")
        company = opportunity.get("company", "Unknown Company")
        score = opportunity.get("overall_score", 0)
        if decision == "CALL":
            return f"Phone Alert: {title} at {company} ({score:.0f}% match)"
        if decision == "EMAIL":
            return f"Email Outreach: {title} at {company} ({score:.0f}% match)"
        if decision == "WHATSAPP":
            return f"WhatsApp Alert: {title} at {company} ({score:.0f}% match)"
        return f"{decision}: {title} at {company}"


_alert_action_service: Optional[AlertActionService] = None


def get_alert_action_service() -> AlertActionService:
    global _alert_action_service
    if _alert_action_service is None:
        _alert_action_service = AlertActionService()
    return _alert_action_service
