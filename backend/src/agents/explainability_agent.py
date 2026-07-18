"""Phase 5 — Explainability Agent.

Compiles reasoning chains, evidence chains, confidence chains,
and governance decisions for every autonomous action.
No opaque autonomy — every action must explain itself.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.agent_observability import get_agent_observability


@dataclass
class ExplainabilityState:
    explainability_run_id: str
    session_uid: str
    action_id: str = ""
    reasoning_chain: List[str] = field(default_factory=list)
    evidence_chain: List[Dict[str, Any]] = field(default_factory=list)
    confidence_chain: List[Dict[str, Any]] = field(default_factory=list)
    governance_decisions: List[Dict[str, Any]] = field(default_factory=list)
    final_explanation: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    status: str = "active"


class ExplainabilityAgent:
    AGENT_NAME = "explainability"

    def __init__(self):
        self.observability = get_agent_observability()

    async def compile(
        self,
        session_uid: str,
        action_data: Dict[str, Any],
        scoring_context: Optional[Dict[str, Any]] = None,
        urgency_context: Optional[Dict[str, Any]] = None,
        governance_context: Optional[Dict[str, Any]] = None,
    ) -> ExplainabilityState:
        t0 = time.time()
        state = ExplainabilityState(
            explainability_run_id=str(uuid.uuid4()),
            session_uid=session_uid,
            action_id=action_data.get("action_id", str(uuid.uuid4())),
        )

        try:
            state.reasoning_chain = self._build_reasoning_chain(action_data, scoring_context)
            state.evidence_chain = self._build_evidence_chain(action_data, scoring_context)
            state.confidence_chain = self._build_confidence_chain(action_data)
            state.governance_decisions = self._build_governance_decisions(governance_context)

            state.final_explanation = {
                "action_id": state.action_id,
                "action_type": action_data.get("action_type", "unknown"),
                "why_happened": state.reasoning_chain,
                "why_urgency": self._explain_urgency(urgency_context),
                "why_notification": self._explain_notification(action_data),
                "why_confidence": self._explain_confidence(state.confidence_chain),
                "why_prioritized": self._explain_prioritization(scoring_context),
                "why_suppressed": self._explain_suppression(action_data, governance_context),
                "evidence": state.evidence_chain,
                "governance_verdict": self._final_verdict(state.governance_decisions),
                "compiled_at": time.time(),
            }

            state.status = "completed"
            self.observability.record_agent_execution(self.AGENT_NAME, "completed")
        except Exception as exc:
            state.errors.append(str(exc))
            state.status = "failed"
            self.observability.record_agent_execution(self.AGENT_NAME, "failed")

        self.observability.record_agent_latency(self.AGENT_NAME, time.time() - t0)
        return state

    def _build_reasoning_chain(
        self, action: Dict[str, Any], scoring: Optional[Dict[str, Any]]
    ) -> List[str]:
        chain = [f"Action type: {action.get('action_type', 'unknown')}"]
        if scoring:
            chain.append(f"Fit score: {scoring.get('overall_score', 'N/A')}")
        if action.get("urgency"):
            chain.append(f"Urgency: {action.get('urgency', 'N/A')}")
        return chain

    def _build_evidence_chain(
        self, action: Dict[str, Any], scoring: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        evidence = []
        if scoring and scoring.get("dimension_scores"):
            for dim, info in scoring["dimension_scores"].items():
                for cite in info.get("citations", []):
                    evidence.append({"dimension": dim, "citation": cite})
        return evidence

    def _build_confidence_chain(self, action: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{
            "initial": action.get("confidence", 0.5),
            "adjusted": action.get("adjusted_confidence", action.get("confidence", 0.5)),
            "penalty": action.get("penalty_applied", 0.0),
        }]

    def _build_governance_decisions(
        self, governance: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not governance:
            return []
        return governance.get("decisions", [])

    def _explain_urgency(self, urgency: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not urgency:
            return {"level": "unknown", "factors": []}
        return {
            "level": "high" if urgency.get("urgency_score", 0) >= 0.6 else "normal",
            "factors": urgency.get("reasoning_chain", []),
        }

    def _explain_notification(self, action: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "triggered": action.get("should_notify", False),
            "channel": action.get("channel", "voice"),
            "message": (action.get("notification_message", "") or "")[:200],
        }

    def _explain_confidence(self, chain: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not chain:
            return {"initial": 0.5, "final": 0.5, "adjustments": []}
        return chain[0]

    def _explain_prioritization(
        self, scoring: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not scoring:
            return {"rank": "N/A", "reason": "no scoring data"}
        return {
            "rank": scoring.get("priority_rank", 0),
            "score": scoring.get("priority_score", 0),
        }

    def _explain_suppression(
        self, action: Dict[str, Any], governance: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        suppressed = governance.get("suppressed_actions", []) if governance else []
        if not suppressed:
            return None
        return {
            "reason": suppressed[0].get("reason", "unknown"),
            "detail": suppressed[0],
        }

    def _final_verdict(self, decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not decisions:
            return {"passed": True, "checks": []}
        return {
            "passed": all(d.get("verdict") == "passed" for d in decisions),
            "checks": decisions,
        }


# ── Singleton ────────────────────────────────────────────────────────

_agent: Optional[ExplainabilityAgent] = None


def get_explainability_agent() -> ExplainabilityAgent:
    global _agent
    if _agent is None:
        _agent = ExplainabilityAgent()
    return _agent


def reset_explainability_agent() -> None:
    global _agent
    _agent = None
