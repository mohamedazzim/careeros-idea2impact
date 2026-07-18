"""
Weakness pattern service — longitudinal weakness detection across sessions.

Detects repeated weak areas, contradictions, shallow reasoning patterns,
architecture gaps, AI engineering gaps, communication weaknesses,
and scalability weaknesses across multiple interviews.

Phase 4D: Longitudinal pattern detection for interview growth planning.
"""
import json
import logging
from collections import Counter
from typing import Dict, Any, List

from src.services.interview.interview_observability import get_interview_observability
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)

PATTERN_TYPES = [
    "repeated_weak_areas", "repeated_contradictions", "shallow_reasoning",
    "architecture_gaps", "ai_engineering_gaps", "communication_weaknesses",
    "scalability_weaknesses", "testing_blindness", "edge_case_blindness",
    "production_blindness",
]


class WeaknessPatternService:
    def detect_patterns(
        self,
        session_history: List[Dict[str, Any]],
        question_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        obs = get_interview_observability()
        patterns: Dict[str, int] = {}
        weakness_counter: Counter = Counter()

        for session in session_history:
            if isinstance(session, dict):
                for w, count in session.get("weaknesses_detected", {}).items():
                    weakness_counter[w] += count

        for question in question_history:
            if isinstance(question, dict) and question.get("weaknesses"):
                for w in (question["weaknesses"] if isinstance(question["weaknesses"], list) else []):
                    w_key = w if isinstance(w, str) else w.get("dimension", str(w))
                    weakness_counter[w_key] += 1

        for w_type, count in weakness_counter.most_common():
            if count >= 2:
                patterns[w_type] = count
                obs.record_weakness_pattern(w_type, count)

        # Classify patterns
        classified = {
            "repeated_weak_areas": [],
            "repeated_contradictions": [],
            "architecture_gaps": [],
            "ai_engineering_gaps": [],
            "communication_weaknesses": [],
            "scalability_weaknesses": [],
        }

        arch_kw = ["architecture", "distributed", "system_design", "fault"]
        ai_kw = ["rag", "vector", "llm", "ai", "ml", "inference", "langgraph", "mcp"]
        comm_kw = ["communication", "clarity", "articulation"]
        scale_kw = ["scalability", "scale", "performance", "optimization"]
        contra_kw = ["contradiction", "inconsistency"]

        for w_name, count in patterns.items():
            entry = {"pattern": w_name, "occurrences": count}
            lower = w_name.lower()
            if any(k in lower for k in contra_kw):
                classified["repeated_contradictions"].append(entry)
            elif any(k in lower for k in arch_kw):
                classified["architecture_gaps"].append(entry)
            elif any(k in lower for k in ai_kw):
                classified["ai_engineering_gaps"].append(entry)
            elif any(k in lower for k in comm_kw):
                classified["communication_weaknesses"].append(entry)
            elif any(k in lower for k in scale_kw):
                classified["scalability_weaknesses"].append(entry)
            else:
                classified["repeated_weak_areas"].append(entry)

        total_patterns = sum(len(v) for v in classified.values())
        return {
            "total_patterns_detected": total_patterns,
            "pattern_classification": classified,
            "raw_weakness_counts": dict(weakness_counter.most_common(20)),
            "severity": "high" if total_patterns >= 5 else "medium" if total_patterns >= 2 else "low",
        }

    async def generate_growth_plan(
        self,
        patterns: Dict[str, Any],
        strategy_data: str = "",
        learning_path: str = "",
        context: str = "",
    ) -> StructuredResponse:
        return await get_reasoning_pipeline().reason(
            query="interview growth plan",
            category="interview",
            prompt_id="interview_growth_plan",
            template_vars={
                "patterns": json.dumps(patterns, default=str),
                "strategy_data": strategy_data,
                "learning_path": learning_path,
                "context": context,
            },
        )


_svc: WeaknessPatternService | None = None
def get_weakness_pattern_service() -> WeaknessPatternService:
    global _svc
    if _svc is None: _svc = WeaknessPatternService()
    return _svc
def __getattr__(n):
    if n == "weakness_pattern_service": return get_weakness_pattern_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
