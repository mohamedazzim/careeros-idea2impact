"""Phase 5 — Prioritization Engine.

Composite priority ranking: fit × urgency × confidence weighted.
"""

from typing import Any, Dict, List, Optional



class PrioritizationEngine:

    FIT_WEIGHT = 0.50
    URGENCY_WEIGHT = 0.35
    CONFIDENCE_WEIGHT = 0.15

    def rank(self, scored_opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for opp in scored_opportunities:
            fit = opp.get("overall_score", 0) / 100.0
            urgency = opp.get("urgency_score", 0)
            confidence = opp.get("confidence", 0.5)
            priority = (
                fit * self.FIT_WEIGHT
                + urgency * self.URGENCY_WEIGHT
                + confidence * self.CONFIDENCE_WEIGHT
            )
            opp["priority_score"] = round(priority * 100, 1)
            opp["priority_rank"] = 0

        ranked = sorted(scored_opportunities, key=lambda o: o.get("priority_score", 0), reverse=True)
        for idx, opp in enumerate(ranked, 1):
            opp["priority_rank"] = idx

        return ranked

    def top_n(self, opportunities: List[Dict[str, Any]], n: int = 5) -> List[Dict[str, Any]]:
        ranked = self.rank(opportunities)
        return ranked[:n]

    def above_threshold(
        self, opportunities: List[Dict[str, Any]], threshold: float = 70.0
    ) -> List[Dict[str, Any]]:
        ranked = self.rank(opportunities)
        return [o for o in ranked if o.get("priority_score", 0) >= threshold]


_engine: Optional[PrioritizationEngine] = None

def get_prioritization_engine() -> PrioritizationEngine:
    global _engine
    if _engine is None:
        _engine = PrioritizationEngine()
    return _engine
