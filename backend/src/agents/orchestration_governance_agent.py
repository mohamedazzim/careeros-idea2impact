"""Phase 5 — Orchestration Governance Agent.

Enforces autonomous action caps, recursion depth limits,
duplicate notification prevention, and confidence thresholds.
Runs at two points: pre-action (reject) and post-action (validate).
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.agents.agent_observability import get_agent_observability


@dataclass
class GovernanceState:
    governance_run_id: str
    session_uid: str
    verdict: str = "passed"
    suppressed_actions: List[Dict[str, Any]] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    recursion_depth: int = 0
    autonomous_count: int = 0
    reasoning_chain: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = "active"


class OrchestrationGovernanceAgent:
    AGENT_NAME = "orchestration_governance"

    def __init__(self):
        self.observability = get_agent_observability()
        self.max_autonomous = settings.AGENT_AUTONOMOUS_CAP_PER_SESSION
        self.max_recursion = settings.AGENT_RECURSION_DEPTH_MAX
        self.min_confidence = settings.ORCHESTRATION_MIN_CONFIDENCE_FOR_ACTION

    async def validate(
        self,
        session_uid: str,
        autonomous_count: int = 0,
        recursion_depth: int = 0,
        action_confidence: float = 0.0,
        action_type: str = "",
        opportunity_id: str = "",
    ) -> GovernanceState:
        t0 = time.time()
        state = GovernanceState(
            governance_run_id=str(uuid.uuid4()),
            session_uid=session_uid,
            recursion_depth=recursion_depth,
            autonomous_count=autonomous_count,
        )

        try:
            if recursion_depth > self.max_recursion:
                state.verdict = "suppressed"
                state.suppressed_actions.append({
                    "reason": "recursion_depth_exceeded",
                    "depth": recursion_depth,
                    "max": self.max_recursion,
                })
                state.reasoning_chain.append(f"Recursion limit: {recursion_depth} > {self.max_recursion}")
                self.observability.record_recursion_prevention()

            if autonomous_count >= self.max_autonomous:
                state.verdict = "suppressed"
                state.suppressed_actions.append({
                    "reason": "autonomous_cap_exceeded",
                    "count": autonomous_count,
                    "max": self.max_autonomous,
                })
                state.reasoning_chain.append(f"Autonomous cap: {autonomous_count} >= {self.max_autonomous}")
                self.observability.record_suppression("autonomous_cap")

            if action_confidence < self.min_confidence:
                state.verdict = "suppressed"
                state.suppressed_actions.append({
                    "reason": "low_confidence",
                    "confidence": action_confidence,
                    "threshold": self.min_confidence,
                })
                state.reasoning_chain.append(
                    f"Confidence too low: {action_confidence:.2f} < {self.min_confidence}"
                )
                self.observability.record_suppression("low_confidence")

            from src.memory.orchestration_memory import get_orchestration_memory
            memory = get_orchestration_memory()
            already_notified = await memory.notification_already_sent(session_uid, opportunity_id)
            if already_notified and action_type == "notification":
                state.verdict = "suppressed"
                state.suppressed_actions.append({"reason": "duplicate_notification"})
                state.reasoning_chain.append("Duplicate notification prevented")
                self.observability.record_suppression("duplicate")

            state.decisions.append({
                "type": "orchestration_governance",
                "verdict": state.verdict,
                "checks_performed": [
                    f"recursion: {recursion_depth}/{self.max_recursion}",
                    f"autonomous: {autonomous_count}/{self.max_autonomous}",
                    f"confidence: {action_confidence:.2f}/{self.min_confidence}",
                ],
            })

            self.observability.record_governance_decision("orchestration", state.verdict)
            state.status = "completed"
            self.observability.record_agent_execution(self.AGENT_NAME, "completed")
        except Exception as exc:
            state.errors.append(str(exc))
            state.status = "failed"
            self.observability.record_agent_execution(self.AGENT_NAME, "failed")

        self.observability.record_agent_latency(self.AGENT_NAME, time.time() - t0)
        return state


# ── Singleton ────────────────────────────────────────────────────────

_agent: Optional[OrchestrationGovernanceAgent] = None


def get_orchestration_governance_agent() -> OrchestrationGovernanceAgent:
    global _agent
    if _agent is None:
        _agent = OrchestrationGovernanceAgent()
    return _agent


def reset_orchestration_governance_agent() -> None:
    global _agent
    _agent = None
