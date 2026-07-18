"""Phase 5 — Urgency Engine.

Deadline proximity, market demand, and application urgency scoring.
"""

from datetime import datetime
from typing import Any, Dict, Optional


class UrgencyEngine:

    URGENCY_KEYWORDS = ["urgent", "immediate", "asap", "closing soon", "immediate hire", "fast-fill"]
    URGENCY_THRESHOLD_HIGH = 7
    URGENCY_THRESHOLD_MEDIUM = 14

    def evaluate(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        scores = {}
        scores["deadline_pressure"] = self._deadline_pressure(opportunity)
        scores["application_urgency"] = self._application_urgency(opportunity)
        scores["market_demand_signal"] = self._market_demand(opportunity)

        overall = (scores["deadline_pressure"] * 0.5 + scores["application_urgency"] * 0.35 + scores["market_demand_signal"] * 0.15)
        factors = [f"{k}: {v:.2f}" for k, v in scores.items()]

        return {
            "urgency_score": round(overall, 2),
            "component_scores": scores,
            "factors": factors,
            "opportunity_id": opportunity.get("id", ""),
        }

    def _deadline_pressure(self, opp: Dict[str, Any]) -> float:
        deadline = opp.get("deadline")
        if not deadline:
            return 0.1
        try:
            dt = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
            days = (dt - datetime.utcnow()).days
            if days <= 0:
                return 1.0
            if days <= self.URGENCY_THRESHOLD_HIGH:
                return 0.85
            if days <= self.URGENCY_THRESHOLD_MEDIUM:
                return 0.55
            if days <= 30:
                return 0.25
            return 0.05
        except (ValueError, TypeError):
            return 0.1

    def _application_urgency(self, opp: Dict[str, Any]) -> float:
        desc = (opp.get("description", "") or "")[:500].lower()
        title = opp.get("title", "").lower()
        text = title + " " + desc
        hits = sum(1 for kw in self.URGENCY_KEYWORDS if kw in text)
        return min(1.0, 0.15 + hits * 0.2)

    def _market_demand(self, opp: Dict[str, Any]) -> float:
        return 0.4


_engine: Optional[UrgencyEngine] = None

def get_urgency_engine() -> UrgencyEngine:
    global _engine
    if _engine is None:
        _engine = UrgencyEngine()
    return _engine
