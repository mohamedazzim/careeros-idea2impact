"""Phase 7 — Live AI Interview State Machine.

Finite-state machine for real-time interview sessions with transitions
for question flow, interruptions, mode switching, and session lifecycle.
"""

import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class InterviewStage(str, Enum):
    IDLE = "idle"
    WELCOME = "welcome"
    INTRO = "intro"
    QUESTION_DELIVERY = "question_delivery"
    USER_SPEAKING = "user_speaking"
    AI_THINKING = "ai_thinking"
    FOLLOW_UP = "follow_up"
    EVALUATION = "evaluation"
    TRANSITIONING = "transitioning"
    CODING = "coding"
    WHITEBOARD = "whiteboard"
    CLOSING = "closing"
    INTERRUPTED = "interrupted"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


VALID_TRANSITIONS: Dict[InterviewStage, Set[InterviewStage]] = {
    InterviewStage.IDLE: {InterviewStage.WELCOME, InterviewStage.ERROR},
    InterviewStage.WELCOME: {InterviewStage.INTRO, InterviewStage.ERROR},
    InterviewStage.INTRO: {InterviewStage.QUESTION_DELIVERY, InterviewStage.ERROR},
    InterviewStage.QUESTION_DELIVERY: {InterviewStage.USER_SPEAKING, InterviewStage.CODING, InterviewStage.WHITEBOARD, InterviewStage.INTERRUPTED, InterviewStage.PAUSED, InterviewStage.ERROR},
    InterviewStage.USER_SPEAKING: {InterviewStage.AI_THINKING, InterviewStage.INTERRUPTED, InterviewStage.PAUSED, InterviewStage.ERROR},
    InterviewStage.AI_THINKING: {InterviewStage.FOLLOW_UP, InterviewStage.EVALUATION, InterviewStage.INTERRUPTED, InterviewStage.ERROR},
    InterviewStage.FOLLOW_UP: {InterviewStage.QUESTION_DELIVERY, InterviewStage.USER_SPEAKING, InterviewStage.EVALUATION, InterviewStage.TRANSITIONING, InterviewStage.INTERRUPTED, InterviewStage.ERROR},
    InterviewStage.EVALUATION: {InterviewStage.TRANSITIONING, InterviewStage.CLOSING, InterviewStage.INTERRUPTED, InterviewStage.ERROR},
    InterviewStage.TRANSITIONING: {InterviewStage.QUESTION_DELIVERY, InterviewStage.CLOSING, InterviewStage.ERROR},
    InterviewStage.CODING: {InterviewStage.AI_THINKING, InterviewStage.INTERRUPTED, InterviewStage.PAUSED, InterviewStage.ERROR},
    InterviewStage.WHITEBOARD: {InterviewStage.AI_THINKING, InterviewStage.INTERRUPTED, InterviewStage.PAUSED, InterviewStage.ERROR},
    InterviewStage.CLOSING: {InterviewStage.COMPLETED, InterviewStage.ERROR},
    InterviewStage.INTERRUPTED: {InterviewStage.QUESTION_DELIVERY, InterviewStage.USER_SPEAKING, InterviewStage.AI_THINKING, InterviewStage.PAUSED, InterviewStage.ERROR},
    InterviewStage.PAUSED: {InterviewStage.QUESTION_DELIVERY, InterviewStage.USER_SPEAKING, InterviewStage.CLOSING, InterviewStage.ERROR},
    InterviewStage.COMPLETED: set(),
    InterviewStage.ERROR: {InterviewStage.IDLE, InterviewStage.PAUSED, InterviewStage.CLOSING},
}


@dataclass
class InterviewState:
    session_uid: str
    interview_type: str  # technical, behavioral, coding, system_design, hr
    stage: InterviewStage = InterviewStage.IDLE
    current_question_index: int = 0
    total_questions: int = 0
    current_question: Optional[str] = None
    last_user_transcript: str = ""
    last_ai_response: str = ""
    interruption_count: int = 0
    scores: List[float] = field(default_factory=list)
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    follow_up_depth: int = 0
    max_follow_ups: int = 3
    mode: str = "voice"  # voice, text, multimodal
    started_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def transition_to(self, target: InterviewStage) -> bool:
        if target in VALID_TRANSITIONS.get(self.stage, set()):
            old = self.stage
            self.stage = target
            self.last_activity_at = time.time()
            logger.debug(f"State transition: {old.value} → {target.value} (session={self.session_uid})")
            return True
        logger.warning(f"Invalid transition: {self.stage.value} → {target.value}")
        return False


class InterviewStateMachine:
    """Manages interview state transitions with governance, interruption, and pause support."""

    def __init__(self):
        self._sessions: Dict[str, InterviewState] = {}
        self._transition_history: Dict[str, List[tuple]] = {}

    def create_session(self, session_uid: str, interview_type: str, **kwargs) -> InterviewState:
        """Create a new interview session state."""
        state = InterviewState(
            session_uid=session_uid,
            interview_type=interview_type,
            **kwargs,
        )
        self._sessions[session_uid] = state
        self._transition_history[session_uid] = [(time.time(), InterviewStage.IDLE.value, InterviewStage.IDLE.value)]
        return state

    def get_state(self, session_uid: str) -> Optional[InterviewState]:
        return self._sessions.get(session_uid)

    def transition(self, session_uid: str, target: InterviewStage) -> bool:
        """Attempt a state transition."""
        state = self._sessions.get(session_uid)
        if not state:
            logger.warning(f"No session found: {session_uid}")
            return False
        if state.transition_to(target):
            self._transition_history.setdefault(session_uid, []).append(
                (time.time(), state.stage.value, target.value)
            )
            return True
        return False

    def force_transition(self, session_uid: str, target: InterviewStage) -> bool:
        """Force a transition (for admin override)."""
        state = self._sessions.get(session_uid)
        if not state:
            return False
        state.stage = target
        state.last_activity_at = time.time()
        self._transition_history.setdefault(session_uid, []).append(
            (time.time(), "FORCED", target.value)
        )
        return True

    def interrupt(self, session_uid: str) -> bool:
        """Handle user interruption."""
        state = self._sessions.get(session_uid)
        if not state:
            return False
        state.interruption_count += 1
        state.last_activity_at = time.time()
        prev = state.stage
        self.force_transition(session_uid, InterviewStage.INTERRUPTED)
        logger.info(f"Interruption in session {session_uid} (stage={prev.value}, count={state.interruption_count})")
        return True

    def pause(self, session_uid: str) -> bool:
        state = self._sessions.get(session_uid)
        if not state or state.stage in (InterviewStage.COMPLETED, InterviewStage.ERROR):
            return False
        return self.force_transition(session_uid, InterviewStage.PAUSED)

    def resume(self, session_uid: str, target: InterviewStage = InterviewStage.QUESTION_DELIVERY) -> bool:
        state = self._sessions.get(session_uid)
        if not state or state.stage != InterviewStage.PAUSED:
            return False
        return self.force_transition(session_uid, target)

    def get_transition_history(self, session_uid: str) -> List[tuple]:
        return self._transition_history.get(session_uid, [])

    def remove_session(self, session_uid: str):
        self._sessions.pop(session_uid, None)
        self._transition_history.pop(session_uid, None)


# ── Singleton ────────────────────────────────────────────────────────

_sm: Optional[InterviewStateMachine] = None


def get_interview_state_machine() -> InterviewStateMachine:
    global _sm
    if _sm is None:
        _sm = InterviewStateMachine()
    return _sm
