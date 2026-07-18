"""Phase 5 — Deadline Urgency Agent.

Extracts deadlines from opportunities and computes urgency scores.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.agents.agent_observability import get_agent_observability


@dataclass
class UrgencyState:
    urgency_run_id: str
    user_id: str
    urgency_scores: Dict[str, float] = field(default_factory=dict)
    approaching_deadlines: List[Dict[str, Any]] = field(default_factory=list)
    reasoning_chain: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = "active"


class DeadlineUrgencyAgent:
    AGENT_NAME = "deadline_urgency"

    def __init__(self):
        self.observability = get_agent_observability()

    async def evaluate(
        self, user_id: str, opportunities: List[Dict[str, Any]]
    ) -> UrgencyState:
        t0 = time.time()
        state = UrgencyState(urgency_run_id=str(uuid.uuid4()), user_id=user_id)

        try:
            for opp in opportunities:
                opp_id = opp.get("id", opp.get("opportunity_id", ""))
                urgency = self._compute_urgency(opp)
                state.urgency_scores[opp_id] = urgency
                if urgency >= settings.VOICE_NOTIFICATION_MIN_URGENCY:
                    state.approaching_deadlines.append({
                        "opportunity_id": opp_id,
                        "title": opp.get("title", ""),
                        "urgency": urgency,
                        "deadline": opp.get("deadline", "unknown"),
                    })
                state.reasoning_chain.append(f"{opp.get('title', 'Unknown')}: urgency={urgency:.2f}")

            state.status = "completed"
            self.observability.record_agent_execution(self.AGENT_NAME, "completed")
        except Exception as exc:
            state.errors.append(str(exc))
            state.status = "failed"
            self.observability.record_agent_execution(self.AGENT_NAME, "failed")

        self.observability.record_agent_latency(self.AGENT_NAME, time.time() - t0)
        return state

    def _compute_urgency(self, opportunity: Dict[str, Any]) -> float:
        score = 0.0
        if deadline := opportunity.get("deadline"):
            try:
                dt = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
                days_remaining = (dt - datetime.utcnow()).days
                if days_remaining <= 1:
                    score += 0.6
                elif days_remaining <= 3:
                    score += 0.4
                elif days_remaining <= 7:
                    score += 0.2
                elif days_remaining <= 14:
                    score += 0.1
            except (ValueError, TypeError):
                pass

        app_urgency = opportunity.get("application_urgency", 0)
        if isinstance(app_urgency, (int, float)):
            score += app_urgency / 100 * 0.3

        market_demand = opportunity.get("market_demand", 0)
        if isinstance(market_demand, (int, float)):
            score += market_demand / 100 * 0.1

        return min(round(score, 2), 1.0)


# ── Singleton ────────────────────────────────────────────────────────

_agent: Optional[DeadlineUrgencyAgent] = None


def get_deadline_urgency_agent() -> DeadlineUrgencyAgent:
    global _agent
    if _agent is None:
        _agent = DeadlineUrgencyAgent()
    return _agent


def reset_deadline_urgency_agent() -> None:
    global _agent
    _agent = None
