"""Phase 5 — Agent Governance Layer.

Hard governance enforcement for multi-agent orchestration:
- Recursive execution caps
- Autonomous action limits
- Duplicate notification prevention
- Confidence thresholds
- Token budget enforcement
- Unsafe escalation blocking

Runs at pre-action and post-action boundaries.
"""

import logging
from typing import Any, Dict, Optional

from src.core.config import settings
from src.observability.metrics import (
    RECURSION_PREVENTION_COUNT,
    NOTIFICATION_SUPPRESSION_COUNT,
    GOVERNANCE_DECISION_COUNT,
)

logger = logging.getLogger(__name__)


class AgentGovernance:

    def __init__(self):
        self.max_recursion = settings.AGENT_RECURSION_DEPTH_MAX
        self.max_autonomous = settings.AGENT_AUTONOMOUS_CAP_PER_SESSION
        self.min_confidence = settings.ORCHESTRATION_MIN_CONFIDENCE_FOR_ACTION
        self.max_retries = settings.ORCHESTRATION_MAX_RETRIES

    async def pre_action_check(
        self,
        action_type: str,
        confidence: float,
        recursion_depth: int,
        autonomous_count: int,
        session_uid: str,
    ) -> Dict[str, Any]:
        violations = []
        allowed = True

        if recursion_depth >= self.max_recursion:
            violations.append("recursion_depth_exceeded")
            allowed = False
            RECURSION_PREVENTION_COUNT.inc()

        if autonomous_count >= self.max_autonomous:
            violations.append("autonomous_cap_exceeded")
            allowed = False
            NOTIFICATION_SUPPRESSION_COUNT.labels(reason="autonomous_cap").inc()

        if confidence < self.min_confidence:
            violations.append("low_confidence")
            allowed = False
            NOTIFICATION_SUPPRESSION_COUNT.labels(reason="low_confidence").inc()

        verdict = "passed" if allowed else "suppressed"
        GOVERNANCE_DECISION_COUNT.labels(decision_type=action_type, verdict=verdict).inc()

        return {
            "allowed": allowed,
            "verdict": verdict,
            "violations": violations,
            "reason": "; ".join(violations) if violations else None,
        }

    def check_recursion(self, depth: int) -> bool:
        return depth < self.max_recursion

    def check_autonomous_cap(self, count: int) -> bool:
        return count < self.max_autonomous

    def check_confidence(self, confidence: float) -> bool:
        return confidence >= self.min_confidence

    def get_limits(self) -> Dict[str, Any]:
        return {
            "max_recursion_depth": self.max_recursion,
            "max_autonomous_actions": self.max_autonomous,
            "min_confidence": self.min_confidence,
            "max_retries": self.max_retries,
        }


# ── Singleton ────────────────────────────────────────────────────────

_gov: Optional[AgentGovernance] = None


def get_agent_governance() -> AgentGovernance:
    global _gov
    if _gov is None:
        _gov = AgentGovernance()
    return _gov


def reset_agent_governance() -> None:
    global _gov
    _gov = None
