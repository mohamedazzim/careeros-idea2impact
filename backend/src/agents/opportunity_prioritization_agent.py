"""Phase 5 — Opportunity Prioritization Agent.

Ranks opportunities by composite score (fit × urgency × confidence).
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.agent_observability import get_agent_observability


@dataclass
class PrioritizationState:
    prioritization_run_id: str
    user_id: str
    ranked_opportunities: List[Dict[str, Any]] = field(default_factory=list)
    priority_scores: Dict[str, float] = field(default_factory=dict)
    reasoning_chain: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = "active"


class OpportunityPrioritizationAgent:
    AGENT_NAME = "opportunity_prioritization"

    def __init__(self):
        self.observability = get_agent_observability()

    async def prioritize(
        self,
        user_id: str,
        scored_opportunities: List[Dict[str, Any]],
        urgency_data: Optional[Dict[str, Any]] = None,
    ) -> PrioritizationState:
        t0 = time.time()
        state = PrioritizationState(
            prioritization_run_id=str(uuid.uuid4()),
            user_id=user_id,
        )

        try:
            for opp in scored_opportunities:
                fit_score = opp.get("overall_score", 0)
                urgency = opp.get("urgency_score", 0)
                confidence = opp.get("confidence", 0.5)
                priority = (fit_score * 0.6) + (urgency * 0.3) + (confidence * 100 * 0.1)
                opp["priority_score"] = round(priority, 1)
                opp["priority_rank"] = 0
                state.priority_scores[opp.get("opportunity_id", "")] = round(priority, 1)

            state.ranked_opportunities = sorted(
                scored_opportunities, key=lambda o: o.get("priority_score", 0), reverse=True
            )
            for idx, opp in enumerate(state.ranked_opportunities, 1):
                opp["priority_rank"] = idx

            state.reasoning_chain.append(
                f"Ranked {len(state.ranked_opportunities)} opportunities by composite priority"
            )
            state.status = "completed"
            self.observability.record_agent_execution(self.AGENT_NAME, "completed")
        except Exception as exc:
            state.errors.append(str(exc))
            state.status = "failed"
            self.observability.record_agent_execution(self.AGENT_NAME, "failed")

        self.observability.record_agent_latency(self.AGENT_NAME, time.time() - t0)
        return state


# ── Singleton ────────────────────────────────────────────────────────

_agent: Optional[OpportunityPrioritizationAgent] = None


def get_opportunity_prioritization_agent() -> OpportunityPrioritizationAgent:
    global _agent
    if _agent is None:
        _agent = OpportunityPrioritizationAgent()
    return _agent


def reset_opportunity_prioritization_agent() -> None:
    global _agent
    _agent = None
