"""
Opportunity Alert Agent — safety-gated notification pipeline.

Evaluates opportunity urgency and match quality and routes ALL decisions
through AlertActionService. No outbound calls/emails occur without
explicit human approval via the approval center.

Previously this agent directly dispatched Twilio calls and ElevenLabs
voice synthesis. That code is retained below as DEAD CODE for reference.
"""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.agents.agent_observability import get_agent_observability
from src.core.config import settings

logger = logging.getLogger(__name__)
from src.observability.langsmith import traceable


@dataclass
class AlertState:
    alert_id: str
    user_id: str
    opportunity_id: str
    job_title: str
    company: str
    match_score: float
    urgency_score: float
    should_alert: bool = False
    channel: str = "none"
    voice_script: Optional[str] = None
    sms_body: Optional[str] = None
    call_sid: Optional[str] = None
    elevenlabs_result: Optional[Dict[str, Any]] = None
    twilio_result: Optional[Dict[str, Any]] = None
    delivery_status: str = "pending"
    failure_reason: Optional[str] = None
    latency_ms: float = 0.0


def is_call_eligible(match_score: Optional[float]) -> bool:
    """Return True only when the normalized score meets the CALL threshold."""
    if match_score is None:
        return False
    try:
        score = float(match_score)
    except (TypeError, ValueError):
        return False
    # Normalize 0–1 to 0–100
    if 0.0 <= score <= 1.0:
        score *= 100
    return score >= settings.CALL_ALERT_MIN_MATCH_SCORE


class OpportunityAlertAgent:
    AGENT_NAME = "opportunity_alert"

    def __init__(self):
        self.observability = get_agent_observability()

    @traceable(name="opportunity_alert_agent", metadata={"candidate_id_masked": True})
    async def evaluate_and_alert(
        self,
        user_id: str,
        opportunity: Dict[str, Any],
        phone_number: Optional[str] = None,
    ) -> AlertState:
        t0 = time.monotonic()
        score = opportunity.get("overall_score", 0)
        urgency = opportunity.get("urgency_score", 0)
        freshness_score = float(opportunity.get("freshness_score", 0) or 0)
        priority_score = float(opportunity.get("opportunity_priority_score", 0) or 0)
        job_id = int(opportunity.get("job_id") or 0)
        lifecycle_state = str(opportunity.get("lifecycle_state") or "NEW").upper()
        apply_url = str(opportunity.get("source_url") or opportunity.get("apply_url") or "")

        state = AlertState(
            alert_id=str(uuid.uuid4()),
            user_id=user_id,
            opportunity_id=opportunity.get("id", ""),
            job_title=opportunity.get("title", ""),
            company=opportunity.get("company", ""),
            match_score=score,
            urgency_score=urgency,
        )

        notification_check = await self._notification_allowed(user_id, job_id, "voice")
        decision = self._decide_channel(
            score, freshness_score, priority_score,
            lifecycle_state, apply_url, notification_check,
        )

        # All decisions route through AlertActionService.
        # CALL/EMAIL/WHATSAPP create delivery records directly when eligible.
        # DASHBOARD_ONLY creates a dashboard notification record.
        # IGNORE/NONE store the decision only.
        try:
            from src.services.opportunity.alert_action_service import get_alert_action_service
            action_result = await get_alert_action_service().process_decision(
                user_id=user_id,
                job_id=job_id,
                opportunity=opportunity,
                decision=decision,
                decision_reason=(
                    f"match={score:.1f}, freshness={freshness_score:.1f}, "
                    f"priority={priority_score:.1f}, lifecycle={lifecycle_state}"
                ),
                decision_scores={
                    "match_score": score,
                    "freshness_score": freshness_score,
                    "opportunity_priority_score": priority_score,
                    "urgency_score": urgency,
                },
                decision_confidence=0.9 if decision == "CALL" else 0.75,
                dry_run=False,
                phone_number=phone_number,
            )
            state.should_alert = decision in {"CALL", "EMAIL", "WHATSAPP"}
            state.channel = decision.lower()
            state.delivery_status = action_result.delivery_status
            state.failure_reason = action_result.reason
        except Exception as exc:
            logger.warning("Alert action service failed for %s: %s", decision, exc)
            state.should_alert = False
            state.channel = decision.lower()
            state.delivery_status = "service_error"
            state.failure_reason = f"alert_action_service: {str(exc)[:256]}"

        state.latency_ms = round((time.monotonic() - t0) * 1000, 2)
        self.observability.record_agent_execution(self.AGENT_NAME, state.delivery_status)
        self.observability.record_agent_latency(self.AGENT_NAME, state.latency_ms / 1000)
        return state

    async def _notification_allowed(self, user_id: str, job_id: int, channel: str) -> Dict[str, Any]:
        if not job_id:
            return {"allowed": False, "reason": "missing_job_id"}
        caps = {"voice": 1, "whatsapp": 2, "email": 3, "dashboard": 10_000}
        from src.db.session import async_session
        from src.db.repositories.domain_repositories import OpportunityNotificationRepository
        async with async_session() as db:
            repo = OpportunityNotificationRepository(db)
            if await repo.has_applied(user_id, job_id):
                return {"allowed": False, "reason": "already_applied"}
            count = await repo.channel_send_count(user_id, job_id, channel)
            if count >= caps.get(channel, 1):
                return {"allowed": False, "reason": f"{channel}_cap_reached"}
        return {"allowed": True, "reason": "allowed"}

    def _decide_channel(
        self,
        score: float,
        freshness_score: float,
        priority_score: float,
        lifecycle_state: str,
        apply_url: str,
        notification_check: Dict[str, Any],
    ) -> str:
        if lifecycle_state in {"APPLIED", "INTERVIEWING", "OFFERED", "HIRED", "EXPIRED"}:
            return "NONE"
        if not apply_url:
            return "NONE"
        if not notification_check.get("allowed", False):
            return "NONE"
        if score >= settings.CALL_ALERT_MIN_MATCH_SCORE and is_call_eligible(score):
            return "CALL"
        if score >= 50:
            return "EMAIL"
        if score >= 35:
            return "DASHBOARD_ONLY"
        return "NONE"


_alert_agent: Optional[OpportunityAlertAgent] = None


def get_opportunity_alert_agent() -> OpportunityAlertAgent:
    global _alert_agent
    if _alert_agent is None:
        _alert_agent = OpportunityAlertAgent()
    return _alert_agent

