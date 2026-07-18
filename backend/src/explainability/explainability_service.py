"""Phase 5 — Explainability System.

Every autonomous action must expose reasoning chains, evidence chains,
confidence chains, and governance decisions. No opaque autonomy allowed.
"""

from typing import Any, Dict, List, Optional


class ReasoningChainBuilder:

    def build(self, action: Dict[str, Any], scoring: Optional[Dict[str, Any]] = None) -> List[str]:
        chain = [f"Action: {action.get('action_type', 'unknown')}"]
        if scoring and scoring.get("overall_score"):
            chain.append(f"Fit score: {scoring['overall_score']}/100")
        if action.get("urgency"):
            chain.append(f"Urgency: {action['urgency']}")
        return chain


class EvidenceChainBuilder:

    def build(self, action: Dict[str, Any], scoring: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not scoring or not scoring.get("dimension_scores"):
            return []
        evidence = []
        for dim, info in scoring["dimension_scores"].items():
            for cite in info.get("citations", []):
                evidence.append({"dimension": dim, "evidence": cite})
        return evidence


class ConfidenceChainBuilder:

    def build(self, confidence: float, adjustments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        return {
            "initial_confidence": confidence,
            "adjustments": adjustments or [],
            "final_confidence": confidence,
        }


class GovernanceExplainer:

    def explain(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "verdict": decision.get("verdict", "unknown"),
            "rules_checked": decision.get("checks_performed", []),
            "penalty_applied": decision.get("penalty_applied", 0),
        }


class ExplainabilityService:

    def __init__(self):
        self.reasoning = ReasoningChainBuilder()
        self.evidence = EvidenceChainBuilder()
        self.confidence = ConfidenceChainBuilder()
        self.governance = GovernanceExplainer()

    def explain_action(self, action_data: Dict[str, Any], scoring: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "why_happened": self.reasoning.build(action_data, scoring),
            "evidence": self.evidence.build(action_data, scoring),
            "confidence_breakdown": self.confidence.build(action_data.get("confidence", 0.5)),
            "governance_summary": action_data.get("governance", {}),
        }


_svc: Optional[ExplainabilityService] = None

def get_explainability_service() -> ExplainabilityService:
    global _svc
    if _svc is None:
        _svc = ExplainabilityService()
    return _svc
