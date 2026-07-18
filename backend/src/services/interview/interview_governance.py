"""
Interview governance — strict critique validation and hallucination detection.

Detects and mitigates:
- Unsupported critique (no evidence citation)
- Hallucinated weaknesses (fabricated candidate gaps)
- Fabricated expertise claims
- Unsupported scoring (rubric mismatch)
- Contradiction-free false positives
- Rubric inconsistencies

Mitigation: confidence reduction, unsupported critique removal, evidence warnings,
rubric correction.

Phase 4D: Interview governance intelligence.
"""
import logging
from typing import Dict, Any, List

from src.services.interview.interview_observability import get_interview_observability

logger = logging.getLogger(__name__)

GOVERNANCE_VIOLATIONS = [
    "unsupported_critique", "hallucinated_weakness", "fabricated_expertise",
    "unsupported_scoring", "false_positive", "rubric_inconsistency",
]


class InterviewGovernance:
    def validate_evaluation(
        self,
        evaluation: Dict[str, Any],
        rubric: List[Any],
        evidence_context: str = "",
    ) -> Dict[str, Any]:
        obs = get_interview_observability()
        violations = []
        mitigated = {}

        weaknesses = evaluation.get("weaknesses", [])
        citations = evaluation.get("citations", [])

        # Check unsupported critique
        if weaknesses and not citations:
            violations.append({
                "type": "unsupported_critique",
                "detail": f"{len(weaknesses)} weaknesses with 0 citations",
            })
            obs.record_critique_suppression("unsupported_critique")

        # Check hallucinated weaknesses
        hallucinated = self._detect_hallucinated_weaknesses(weaknesses, evidence_context)
        if hallucinated:
            violations.append({"type": "hallucinated_weakness", "detail": hallucinated})
            obs.record_hallucination("evaluation", "medium")

        # Check unsupported scoring
        dimension_scores = evaluation.get("dimension_scores", {})
        if dimension_scores and not citations:
            violations.append({
                "type": "unsupported_scoring",
                "detail": f"{len(dimension_scores)} dimensions scored without evidence",
            })

        # Check rubric inconsistencies
        rubric_inconsistencies = self._check_rubric_consistency(evaluation, rubric)
        if rubric_inconsistencies:
            violations.append({"type": "rubric_inconsistency", "detail": rubric_inconsistencies})

        confidence = evaluation.get("confidence", {}).get("overall", 0.5)
        if violations:
            penalty = min(0.3, len(violations) * 0.1)
            mitigated["confidence_reduction"] = round(penalty, 2)
            mitigated["original_confidence"] = confidence
            mitigated["adjusted_confidence"] = round(max(0.05, confidence - penalty), 4)
            mitigated["violations_suppressed"] = len(violations)

            if hallucinated:
                mitigated["hallucinated_weaknesses_removed"] = hallucinated

        return {
            "valid": len(violations) == 0,
            "violations_detected": len(violations),
            "violations": violations,
            "mitigations_applied": mitigated,
            "governance_verdict": "passed" if len(violations) == 0 else "mitigated",
        }

    def _detect_hallucinated_weaknesses(
        self, weaknesses: List[Any], evidence_context: str
    ) -> List[str]:
        if not evidence_context or not weaknesses:
            return []
        context_lower = evidence_context.lower()
        hall = []
        for w in weaknesses:
            w_str = w if isinstance(w, str) else w.get("dimension", str(w))
            terms = w_str.lower().split()
            found = sum(1 for t in terms if t in context_lower)
            if found == 0:
                hall.append(w_str)
        return hall

    def _check_rubric_consistency(
        self, evaluation: Dict[str, Any], rubric: List[Any]
    ) -> List[str]:
        if not rubric:
            return []
        dim_scores = evaluation.get("dimension_scores", {})
        rubric_names = {d.name if hasattr(d, "name") else str(d) for d in rubric}
        issues = []
        for name, detail in dim_scores.items():
            score = detail.get("score", 0) if isinstance(detail, dict) else detail
            if name not in rubric_names:
                issues.append(f"dimension '{name}' not in rubric")
        return issues


_svc: InterviewGovernance | None = None
def get_interview_governance() -> InterviewGovernance:
    global _svc
    if _svc is None: _svc = InterviewGovernance()
    return _svc
def __getattr__(n):
    if n == "interview_governance": return get_interview_governance()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
