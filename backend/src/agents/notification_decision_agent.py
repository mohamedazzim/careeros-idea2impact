"""Phase 5 — Notification Decision Agent.

Decides whether to notify the user, which channel to use,
and what message to deliver. Governed by confidence thresholds.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.agents.agent_observability import get_agent_observability


@dataclass
class NotificationDecisionState:
    decision_run_id: str
    user_id: str
    opportunity_id: str
    should_notify: bool = False
    channel: str = "voice"
    notification_message: str = ""
    confidence: float = 0.5
    suppression_reason: Optional[str] = None
    reasoning_chain: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = "active"


class NotificationDecisionAgent:
    AGENT_NAME = "notification_decision"

    def __init__(self):
        self.observability = get_agent_observability()

    async def decide(
        self,
        user_id: str,
        opportunity: Dict[str, Any],
        score_data: Optional[Dict[str, Any]] = None,
        urgency: float = 0.0,
        governance_passed: bool = True,
    ) -> NotificationDecisionState:
        t0 = time.time()
        opp_id = opportunity.get("id", opportunity.get("opportunity_id", ""))
        state = NotificationDecisionState(
            decision_run_id=str(uuid.uuid4()),
            user_id=user_id,
            opportunity_id=opp_id,
        )

        try:
            fit_score = (score_data or {}).get("overall_score", 0)
            confidence = (score_data or {}).get("confidence", 0.5)
            voice_call_threshold = getattr(settings, 'OPPORTUNITY_VOICE_CALL_MIN_SCORE', 80.0)
            gov_block_threshold = getattr(settings, 'OPPORTUNITY_GOVERNANCE_BLOCK_SCORE', 94.0)

            if not governance_passed:
                state.should_notify = False
                state.suppression_reason = "governance_blocked"
                state.reasoning_chain.append("Blocked: governance validation failed")
                self.observability.record_suppression("governance_blocked")
            elif confidence < settings.ORCHESTRATION_MIN_CONFIDENCE_FOR_ACTION:
                state.should_notify = False
                state.suppression_reason = "low_confidence"
                state.reasoning_chain.append(
                    f"Suppressed: confidence {confidence:.2f} < {settings.ORCHESTRATION_MIN_CONFIDENCE_FOR_ACTION}"
                )
                self.observability.record_suppression("low_confidence")
            elif fit_score < settings.OPPORTUNITY_MIN_SCORE_FOR_ACTION:
                state.should_notify = False
                state.suppression_reason = "below_alert_threshold"
                state.reasoning_chain.append(
                    f"Suppressed: fit {fit_score:.2f} < {settings.OPPORTUNITY_MIN_SCORE_FOR_ACTION} (alert)"
                )
                self.observability.record_suppression("below_alert_threshold")
            elif fit_score >= gov_block_threshold:
                state.should_notify = False
                state.suppression_reason = "governance_block_score_reached"
                state.reasoning_chain.append(
                    f"Blocked: governance score threshold {gov_block_threshold} reached (fit={fit_score:.2f})"
                )
                self.observability.record_suppression("governance_block_score")
            elif urgency < settings.VOICE_NOTIFICATION_MIN_URGENCY:
                state.should_notify = False
                state.suppression_reason = "low_urgency"
                state.reasoning_chain.append(
                    f"Suppressed: urgency {urgency:.2f} < {settings.VOICE_NOTIFICATION_MIN_URGENCY}"
                )
                self.observability.record_suppression("low_urgency")
            else:
                state.should_notify = True
                state.confidence = confidence
                if fit_score >= voice_call_threshold:
                    state.channel = "voice"
                    state.notification_message = self._craft_message(opportunity, fit_score, urgency)
                    state.reasoning_chain.append(
                        f"Voice call triggered: fit={fit_score:.2f} >= {voice_call_threshold}, urgency={urgency:.2f}, confidence={confidence:.2f}"
                    )
                    self.observability.record_autonomous_action("notification_decision", "voice_call_triggered")
                else:
                    state.channel = "voicemail"
                    state.notification_message = self._craft_message(opportunity, fit_score, urgency)
                    state.reasoning_chain.append(
                        f"Alert triggered: fit={fit_score:.2f} (below voice threshold {voice_call_threshold}), urgency={urgency:.2f}, confidence={confidence:.2f}"
                    )
                    self.observability.record_autonomous_action("notification_decision", "alert_triggered")

            state.status = "completed"
            self.observability.record_agent_execution(self.AGENT_NAME, "completed")
        except Exception as exc:
            state.errors.append(str(exc))
            state.status = "failed"
            self.observability.record_agent_execution(self.AGENT_NAME, "failed")

        self.observability.record_agent_latency(self.AGENT_NAME, time.time() - t0)
        return state

    def _craft_message(self, opportunity: Dict[str, Any], fit_score: float, urgency: float) -> str:
        title = opportunity.get("title", "an opportunity")
        company = opportunity.get("company", "")
        company_str = f" at {company}" if company else ""
        return (
            f"High-priority opportunity detected: {title}{company_str}. "
            f"Match score: {fit_score}%. Urgency: {urgency * 100:.0f}%. "
            "Review immediately."
        )


# ── Singleton ────────────────────────────────────────────────────────

_agent: Optional[NotificationDecisionAgent] = None


def get_notification_decision_agent() -> NotificationDecisionAgent:
    global _agent
    if _agent is None:
        _agent = NotificationDecisionAgent()
    return _agent


def reset_notification_decision_agent() -> None:
    global _agent
    _agent = None
