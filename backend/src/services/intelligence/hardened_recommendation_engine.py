"""
Hardened recommendation engine — impact-aware ranking, feasibility scoring,
effort-vs-impact matrix, recommendation deduplication, and contradiction detection.

Builds on the base RecommendationEngine with post-Claude hardening.

Stateless, async-safe, governance-ready.
"""
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional

from src.services.intelligence.recommendation_engine import get_recommendation_engine
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)

# Effort levels mapped to numeric cost
EFFORT_MAP = {"low": 0.3, "medium": 0.6, "high": 0.9}
IMPACT_MAP = {"low": 0.25, "medium": 0.55, "high": 0.85}


class HardenedRecommendationEngine:
    """Post-processed recommendation engine with prioritization hardening."""

    async def generate(
        self,
        ats_score: Any = "",
        match_score: Any = "",
        strengths: Any = "",
        weaknesses: Any = "",
        skill_gaps: Any = "",
        achievement_analysis: Any = "",
        contradictions: Optional[Dict] = None,
        context: str = "",
    ) -> Dict[str, Any]:
        """Generate hardened recommendations with all post-processing."""

        base_engine = get_recommendation_engine()
        raw_response = await base_engine.generate(
            ats_score=ats_score,
            match_score=match_score,
            strengths=strengths,
            weaknesses=weaknesses,
            skill_gaps=skill_gaps,
            achievement_analysis=achievement_analysis,
            context=context,
        )

        # ── Post-processing hardening ───────────────────────────────

        # 1. Deduplicate recommendations
        deduped = self._deduplicate(raw_response)

        # 2. Score impact-aware ranking
        scored = self._rank_by_impact(deduped)

        # 3. Compute effort-vs-impact
        evi = self._compute_effort_vs_impact(scored)

        # 4. Detect and suppress contradictions
        if contradictions:
            suppressed, reason = self._suppress_contradictory(
                scored, contradictions
            )
        else:
            suppressed, reason = scored, None

        # 5. Compute recommendation confidence calibration
        calibrated = self._calibrate_confidence(suppressed, contradictions, raw_response)

        result = {
            "raw_recommendations": raw_response.model_dump(),
            "processed": {
                "total_raw": self._count_recommendations(raw_response),
                "deduplicated_to": len(scored),
                "suppressed_due_to_contradiction": len(scored) - len(suppressed),
                "suppression_reason": reason,
                "ranked_recommendations": calibrated,
                "effort_vs_impact_summary": {
                    "high_impact_low_effort": evi.get("quick_wins", 0),
                    "high_impact_high_effort": evi.get("strategic_bets", 0),
                    "low_impact_low_effort": evi.get("fill_ins", 0),
                    "low_impact_high_effort": evi.get("time_sinks", 0),
                },
            },
            "contradiction_impact": bool(contradictions),
        }

        return result

    def _deduplicate(self, response: StructuredResponse) -> List[Dict[str, Any]]:
        """Deduplicate recommendations by content hash."""
        data = response.data
        items = []
        if isinstance(data, dict):
            for key in ("recommendations", "items", "results", "recommendation"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            if not items:
                items = [data]

        seen = set()
        unique = []
        for item in (items if isinstance(items, list) else [items]):
            h = hashlib.sha256(
                json.dumps(item, default=str, sort_keys=True).encode()
            ).hexdigest()
            if h not in seen:
                seen.add(h)
                unique.append(item)

        return unique

    def _rank_by_impact(self, items: List[Dict]) -> List[Dict]:
        """Rank recommendations by impact score (feasibility-aware)."""
        scored = []
        for item in items:
            if not isinstance(item, dict):
                scored.append(item)
                continue
            priority = str(item.get("priority", "medium")).lower()
            impact = str(item.get("impact", "medium")).lower()
            effort = str(item.get("effort", "medium")).lower()
            ps = {"high": 3, "medium": 2, "low": 1}.get(priority, 2)
            im = IMPACT_MAP.get(impact, 0.55)
            ef = EFFORT_MAP.get(effort, 0.6)
            item["_impact_score"] = round(ps * im / max(ef, 0.01), 4)
            scored.append(item)

        scored.sort(
            key=lambda x: x.get("_impact_score", 0) if isinstance(x, dict) else 0,
            reverse=True,
        )
        return scored

    def _compute_effort_vs_impact(self, items: List[Dict]) -> Dict[str, int]:
        """Build effort-vs-impact 2x2 matrix counts."""
        matrix = {"quick_wins": 0, "strategic_bets": 0, "fill_ins": 0, "time_sinks": 0}
        for item in items:
            if not isinstance(item, dict):
                continue
            impact = str(item.get("impact", "medium")).lower()
            effort = str(item.get("effort", "medium")).lower()
            high_impact = impact in ("high", "critical")
            low_effort = effort == "low"
            if high_impact and low_effort:
                matrix["quick_wins"] += 1
            elif high_impact and not low_effort:
                matrix["strategic_bets"] += 1
            elif not high_impact and low_effort:
                matrix["fill_ins"] += 1
            else:
                matrix["time_sinks"] += 1
        return matrix

    def _suppress_contradictory(
        self, items: List[Dict], contradictions: Dict
    ) -> tuple:
        """Suppress recommendations that conflict with detected contradictions."""
        if not contradictions.get("contradictions_detected"):
            return items, None

        suppressed = []
        contradiction_keywords = set()
        for cat in contradictions.get("contradictions", []):
            for signal in cat.get("signals", []):
                words = signal.get("detail", "").lower().split()
                contradiction_keywords.update(words)

        for item in items:
            if not isinstance(item, dict):
                suppressed.append(item)
                continue
            item_text = json.dumps(item, default=str).lower()
            if any(kw in item_text for kw in contradiction_keywords if len(kw) > 3):
                continue
            suppressed.append(item)

        reason = (
            f"Suppressed {len(items) - len(suppressed)} recommendations "
            f"due to contradiction conflicts"
            if len(suppressed) < len(items) else None
        )
        return suppressed, reason

    def _calibrate_confidence(
        self,
        items: List[Dict],
        contradictions: Optional[Dict],
        raw_response: StructuredResponse,
    ) -> List[Dict]:
        """Calibrate recommendation confidence based on contradiction signals."""
        con_signal_count = sum(
            len(cat["signals"])
            for cat in (contradictions or {}).get("contradictions", [])
        )
        penalty = min(0.5, con_signal_count * 0.08)

        for item in items:
            if isinstance(item, dict) and "confidence" in item:
                original = float(item["confidence"])
                item["confidence"] = round(max(0.1, original - penalty), 4)
                item["confidence_penalty"] = round(penalty, 4)
        return items

    def _count_recommendations(self, response: StructuredResponse) -> int:
        data = response.data
        if isinstance(data, dict):
            for key in ("recommendations", "items", "results", "recommendation"):
                if key in data and isinstance(data[key], list):
                    return len(data[key])
        return 1


_engine: Optional[HardenedRecommendationEngine] = None
def get_hardened_recommendation_engine() -> HardenedRecommendationEngine:
    global _engine
    if _engine is None: _engine = HardenedRecommendationEngine()
    return _engine
def __getattr__(name: str):
    if name == "hardened_recommendation_engine": return get_hardened_recommendation_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
