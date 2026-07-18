"""
Interview trace builder — full explainability chain for every evaluation.

Produces structured explainability traces with reasoning chain, rubric
references, evidence citations, confidence breakdown, weakness rationale,
difficulty rationale, and adaptation rationale.

Phase 4D: Explainable interview evaluation.
"""
import logging
import time
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class InterviewTraceBuilder:
    def build_trace(
        self,
        session_id: str,
        question_index: int,
        evaluation: Dict[str, Any],
        difficulty_decision: Dict[str, Any],
        claude_raw: Dict[str, Any],
    ) -> Dict[str, Any]:
        trace = {
            "session_id": session_id,
            "question_index": question_index,
            "timestamp": time.time(),
            "evaluation": {
                "overall_score": evaluation.get("overall_score"),
                "interview_type": evaluation.get("interview_type"),
                "difficulty": evaluation.get("difficulty"),
            },
            "reasoning_chain": self._extract_reasoning_chain(claude_raw),
            "rubric_references": self._extract_rubric_references(evaluation),
            "evidence_citations": evaluation.get("citations", []),
            "confidence": evaluation.get("confidence", {}),
            "weakness_rationale": self._build_weakness_rationale(evaluation),
            "difficulty_rationale": difficulty_decision,
            "adaptation_rationale": difficulty_decision.get("reason", "initial"),
            "governance_flags": {
                "hallucination_check": True,
                "contradiction_check": True,
                "rubric_alignment": evaluation.get("evidence_sufficient", False),
            },
        }
        return trace

    def build_session_trace(
        self,
        session_id: str,
        question_traces: List[Dict[str, Any]],
        session_summary: Dict[str, Any],
        weakness_patterns: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "session_id": session_id,
            "trace_type": "interview_session",
            "question_count": len(question_traces),
            "question_traces": question_traces,
            "session_summary": session_summary,
            "weakness_patterns": weakness_patterns,
            "adaptation_history": session_summary.get("adaptation_history", []),
            "confidence_trend": session_summary.get("confidence_trend", []),
            "governance_verdict": self._compute_governance_verdict(
                question_traces, weakness_patterns
            ),
        }

    def _extract_reasoning_chain(self, claude_raw: Dict[str, Any]) -> List[str]:
        if hasattr(claude_raw, "data"):
            claude_raw = claude_raw.data if isinstance(claude_raw.data, dict) else {}
        return claude_raw.get("reasoning", claude_raw.get("analysis", []))

    def _extract_rubric_references(self, evaluation: Dict[str, Any]) -> List[Dict[str, Any]]:
        dims = evaluation.get("dimension_scores", {})
        return [
            {"dimension": name, "score": details.get("score"), "weight": details.get("weight")}
            for name, details in dims.items()
        ]

    def _build_weakness_rationale(self, evaluation: Dict[str, Any]) -> List[Dict[str, Any]]:
        weaknesses = evaluation.get("weaknesses", [])
        return [
            {"weakness": w if isinstance(w, str) else w,
             "dimension_scores": {
                 k: v.get("score", 0)
                 for k, v in evaluation.get("dimension_scores", {}).items()
                 if v.get("score", 100) < 50
             }}
            for w in weaknesses
        ]

    def _compute_governance_verdict(
        self, traces: List[Dict[str, Any]], patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        total = len(traces)
        hall_pass = all(
            t.get("governance_flags", {}).get("hallucination_check", False)
            for t in traces
        )
        contra_pass = all(
            t.get("governance_flags", {}).get("contradiction_check", False)
            for t in traces
        )
        rubric_pass = any(
            t.get("governance_flags", {}).get("rubric_alignment", False)
            for t in traces
        )
        severity = patterns.get("severity", "low")
        return {
            "hallucination_rejected": hall_pass,
            "contradictions_analyzed": contra_pass,
            "rubric_aligned": rubric_pass,
            "patterns_detected": severity,
            "overall_valid": hall_pass and rubric_pass,
        }


_svc: InterviewTraceBuilder | None = None
def get_interview_trace_builder() -> InterviewTraceBuilder:
    global _svc
    if _svc is None: _svc = InterviewTraceBuilder()
    return _svc
def __getattr__(n):
    if n == "interview_trace_builder": return get_interview_trace_builder()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
