"""
Interview state validator — impossible-state detection and race-condition prevention.

Validates:
- Impossible state transitions (completed→active, closed→evaluating, etc.)
- Invalid progression states (question_index out of bounds, missing questions)
- Orphaned sessions (Redis/DB drift detection)
- Duplicate evaluations (same question evaluated twice in one session)
- Race-condition prevention (evaluate on already-closed session)

Phase 4D Hardening: State validation boundaries.
"""
import logging
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class InterviewStatus(str, Enum):
    INIT = "init"
    ACTIVE = "active"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    CLOSED = "closed"
    ERROR = "error"
    ORPHANED = "orphaned"


VALID_TRANSITIONS: Dict[InterviewStatus, List[InterviewStatus]] = {
    InterviewStatus.INIT: [InterviewStatus.ACTIVE, InterviewStatus.ERROR],
    InterviewStatus.ACTIVE: [InterviewStatus.EVALUATING, InterviewStatus.CLOSED, InterviewStatus.ERROR],
    InterviewStatus.EVALUATING: [InterviewStatus.ACTIVE, InterviewStatus.CLOSED, InterviewStatus.ERROR],
    InterviewStatus.ERROR: [InterviewStatus.ACTIVE, InterviewStatus.CLOSED],
    InterviewStatus.COMPLETED: [InterviewStatus.CLOSED],
    InterviewStatus.CLOSED: [],
    InterviewStatus.ORPHANED: [],
}

IMMUTABLE_STATES = {InterviewStatus.COMPLETED, InterviewStatus.CLOSED, InterviewStatus.ORPHANED}


class StateValidationResult:
    def __init__(self, valid: bool, error: Optional[str] = None, warnings: List[str] = None):
        self.valid = valid
        self.error = error
        self.warnings = warnings or []

    def __bool__(self):
        return self.valid


class InterviewStateValidator:
    def validate_transition(
        self, current_status: str, target_status: str
    ) -> StateValidationResult:
        try:
            cur = InterviewStatus(current_status)
            target = InterviewStatus(target_status)
        except ValueError:
            return StateValidationResult(False, f"Unknown status: {current_status} or {target_status}")

        if cur in IMMUTABLE_STATES:
            return StateValidationResult(
                False,
                f"Cannot transition from immutable state '{cur.value}' to '{target.value}'"
            )

        allowed = VALID_TRANSITIONS.get(cur, [])
        if target not in allowed:
            return StateValidationResult(
                False,
                f"Invalid transition: '{cur.value}' → '{target.value}'. Allowed: {[a.value for a in allowed]}"
            )

        return StateValidationResult(True)

    def validate_question_progression(
        self, current_index: int, max_questions: int, new_question: bool = False
    ) -> StateValidationResult:
        warnings = []
        if current_index < 0:
            return StateValidationResult(False, f"Negative question index: {current_index}")
        if max_questions > 0 and current_index > max_questions:
            return StateValidationResult(False, f"Question index {current_index} exceeds max {max_questions}")
        if new_question and current_index >= max_questions:
            return StateValidationResult(False, f"Question cap ({max_questions}) reached")
        if current_index == 0 and max_questions > 0 and not new_question:
            warnings.append("No questions asked yet")
        return StateValidationResult(True, warnings=warnings)

    def validate_evaluation_not_duplicate(
        self, session_questions: List[Dict[str, Any]], question_text: str
    ) -> StateValidationResult:
        for q in session_questions:
            if isinstance(q, dict):
                existing = q.get("question", "")
                if existing and existing.strip() == question_text.strip():
                    if q.get("score", 0) > 0 or q.get("weaknesses"):
                        return StateValidationResult(
                            False,
                            f"Duplicate evaluation for question already scored: '{question_text[:60]}'"
                        )
                    warnings = [f"Re-evaluating previously unanswered question: '{question_text[:60]}'"]
                    return StateValidationResult(True, warnings=warnings)
        return StateValidationResult(True)

    def validate_session_active(self, status: str) -> StateValidationResult:
        if status in ["closed", "completed"]:
            return StateValidationResult(False, f"Cannot operate on {status} session")
        return StateValidationResult(True)

    def validate_adaptation_limit(
        self, adaptation_history: List[Dict[str, Any]], escalation_cap: int
    ) -> StateValidationResult:
        escalations = sum(
            1 for a in adaptation_history
            if isinstance(a, dict) and a.get("to") != a.get("from")
        )
        if escalations >= escalation_cap:
            return StateValidationResult(
                False, f"Escalation cap ({escalation_cap}) reached: {escalations} changes"
            )
        warnings = []
        if escalations >= escalation_cap * 0.75:
            warnings.append(f"Nearing escalation cap: {escalations}/{escalation_cap}")
        return StateValidationResult(True, warnings=warnings)

    def validate_session_not_orphaned(
        self, created_at: float, orphan_ttl: int
    ) -> StateValidationResult:
        import time
        age = time.time() - created_at
        if age > orphan_ttl:
            return StateValidationResult(False, f"Session orphaned: age {age:.0f}s > TTL {orphan_ttl}s")
        return StateValidationResult(True)


_svc: InterviewStateValidator | None = None
def get_interview_state_validator() -> InterviewStateValidator:
    global _svc
    if _svc is None: _svc = InterviewStateValidator()
    return _svc
def reset_interview_state_validator() -> None:
    global _svc; _svc = None
def __getattr__(name: str):
    if name == "interview_state_validator": return get_interview_state_validator()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
