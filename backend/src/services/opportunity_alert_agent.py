"""Autonomous, rule-driven Opportunity Alert Agent.

CALL_CANDIDATE decisions route through AlertActionService and are allowed to
proceed directly when the runtime configuration permits voice delivery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.opportunity_alert import OpportunityAlert
from src.schemas.opportunity_alert import OpportunityAlertRequest, OpportunityAlertResponse
from src.core.config import settings

logger = logging.getLogger(__name__)

CALL_CANDIDATE = "CALL_CANDIDATE"
CALL_CANDIDATE_HIGH_PRIORITY = "CALL_CANDIDATE_HIGH_PRIORITY"
STORE_NOTIFICATION = "STORE_NOTIFICATION"
IGNORE_OPPORTUNITY = "IGNORE_OPPORTUNITY"
CALL_ACTIONS = {CALL_CANDIDATE, CALL_CANDIDATE_HIGH_PRIORITY}


@dataclass(frozen=True)
class AlertDecision:
    action: str
    reason: str


class OpportunityAlertDecisionEngine:
    """Deterministic decision engine for scored opportunities."""

    @staticmethod
    def decide(match_score: float, hours_since_posted: float) -> AlertDecision:
        from src.agents.opportunity_alert_agent import is_call_eligible
        if match_score >= 92 and hours_since_posted <= 72:
            if not is_call_eligible(match_score):
                return AlertDecision(
                    STORE_NOTIFICATION,
                    "Exceptional match score but below call threshold",
                )
            return AlertDecision(
                CALL_CANDIDATE_HIGH_PRIORITY,
                "Exceptional match score and posting is within the 72-hour high-priority window",
            )
        if match_score >= 85 and hours_since_posted <= 32:
            if not is_call_eligible(match_score):
                return AlertDecision(
                    STORE_NOTIFICATION,
                    "High match score but below call threshold",
                )
            return AlertDecision(CALL_CANDIDATE, "High match score and recent posting")
        if match_score >= 70:
            freshness_reason = (
                "posting is outside the eligible call window"
                if match_score >= 85
                else "match score is below the call threshold"
            )
            return AlertDecision(STORE_NOTIFICATION, f"Relevant opportunity, but {freshness_reason}")
        return AlertDecision(IGNORE_OPPORTUNITY, "Match score is below the notification threshold")


class OpportunityAlertAgentService:
    async def evaluate(
        self,
        request: OpportunityAlertRequest,
        db: AsyncSession,
    ) -> OpportunityAlertResponse:
        hours_since_posted = self._hours_since(request.job_posted_at)
        decision = OpportunityAlertDecisionEngine.decide(request.match_score, hours_since_posted)

        # Route through AlertActionService for delivery and audit logging.
        webhook_status: Optional[str] = None
        provider_response: Optional[Dict[str, Any]] = None
        call_sid: Optional[str] = None
        called = False

        if decision.action in CALL_ACTIONS:
            try:
                from src.services.opportunity.alert_action_service import get_alert_action_service
                action_result = await get_alert_action_service().process_decision(
                    user_id=request.candidate_id,
                    job_id=0,
                    opportunity={
                        "id": str(request.candidate_id),
                        "title": request.job_title,
                        "company": request.company,
                        "overall_score": request.match_score,
                        "source_url": str(request.application_url),
                    },
                    decision="CALL",
                    decision_reason=decision.reason,
                    decision_scores={"match_score": request.match_score},
                    decision_confidence=0.9 if "HIGH" in decision.action else 0.75,
                    dry_run=False,
                    phone_number=request.phone_number,
                )
                webhook_status = action_result.provider_status
                called = action_result.delivery_status not in {
                    "blocked_by_threshold",
                    "blocked_no_phone",
                    "blocked_missing_provider",
                    "duplicate_suppressed",
                    "service_error",
                }
            except Exception as exc:
                logger.warning("Alert action service routing failed: %s", exc)
                webhook_status = "service_error"

        alert = OpportunityAlert(
            candidate_id=request.candidate_id,
            job_title=request.job_title,
            company=request.company,
            match_score=request.match_score,
            hours_since_posted=hours_since_posted,
            decision=decision.action,
            reason=decision.reason,
            called=called,
            call_sid=call_sid,
            webhook_status=webhook_status,
            provider_response=provider_response,
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)

        logger.info(
            "Opportunity alert decision completed",
            extra={
                "operation": "opportunity_alert_decision",
                "alert_id": alert.id,
                "candidate_id": request.candidate_id,
                "decision": decision.action,
                "match_score": request.match_score,
                "hours_since_posted": hours_since_posted,
                "webhook_status": webhook_status,
            },
        )
        return OpportunityAlertResponse(
            alert_id=alert.id,
            action=decision.action,
            reason=decision.reason,
            match_score=request.match_score,
            hours_since_posted=hours_since_posted,
            called=called,
            call_sid=call_sid,
            webhook_status=webhook_status,
        )

    @staticmethod
    def _hours_since(job_posted_at: datetime) -> float:
        posted_at = job_posted_at
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - posted_at.astimezone(timezone.utc)).total_seconds() / 3600
        return round(max(0.0, hours), 2)

    @staticmethod
    def _extract_call_sid(provider_response: Optional[Dict[str, Any]]) -> Optional[str]:
        if not provider_response:
            return None
        for key in ("call_sid", "callSid", "sid"):
            value = provider_response.get(key)
            if isinstance(value, str) and value:
                return value
        body = provider_response.get("body")
        if isinstance(body, dict):
            return OpportunityAlertAgentService._extract_call_sid(body)
        return None


_service: Optional[OpportunityAlertAgentService] = None


def get_opportunity_alert_agent_service() -> OpportunityAlertAgentService:
    global _service
    if _service is None:
        _service = OpportunityAlertAgentService()
    return _service
