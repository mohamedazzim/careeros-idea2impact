"""
Interview memory service — persistent interview history and session state.

Tracks per-session and cross-session interview history:
- Prior interviews with scores
- Weakness progression over time
- Improvement progression
- Repeated failure areas
- Confidence progression
- Adaptation history

Phase 4D: Longitudinal interview intelligence.
"""
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class QuestionRecord:
    question_id: str
    question_text: str
    interview_type: str
    difficulty_level: str
    answer: str = ""
    score: float = 0.0
    confidence: float = 0.5
    rubric_scores: Dict[str, float] = field(default_factory=dict)
    contradictions_detected: bool = False
    critique: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class SessionState:
    session_id: str
    interview_type: str
    difficulty_level: str
    questions: List[Dict[str, Any]] = field(default_factory=list)
    current_question_index: int = 0
    total_score: float = 0.0
    confidence_progression: List[float] = field(default_factory=list)
    weakness_tracker: Dict[str, int] = field(default_factory=dict)
    adaptation_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class InterviewMemoryService:
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}
        self.past_sessions: List[Dict[str, Any]] = []
        self.weakness_registry: Dict[str, List[Dict[str, Any]]] = {}
        self.max_past_sessions = 20

    def create_session(
        self,
        session_id: str,
        interview_type: str,
        difficulty_level: str = "intermediate",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionState:
        session = SessionState(
            session_id=session_id,
            interview_type=interview_type,
            difficulty_level=difficulty_level,
            metadata=metadata or {},
        )
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        return self.sessions.get(session_id)

    def add_question(
        self, session_id: str, question: Dict[str, Any]
    ) -> SessionState:
        session = self.sessions.get(session_id)
        if not session:
            session = self.create_session(
                session_id,
                question.get("interview_type", "technical"),
                question.get("difficulty_level", "intermediate"),
            )
        session.questions.append(question)
        session.current_question_index = len(session.questions)

        score = question.get("score", 0)
        confidence = question.get("confidence", 0.5)
        session.total_score += score
        session.confidence_progression.append(confidence)

        if question.get("weaknesses"):
            for w in question["weaknesses"] if isinstance(question["weaknesses"], list) else []:
                w_key = w if isinstance(w, str) else w.get("dimension", str(w))
                session.weakness_tracker[w_key] = session.weakness_tracker.get(w_key, 0) + 1

        if question.get("difficulty_level") != session.difficulty_level:
            session.adaptation_history.append({
                "from": session.difficulty_level,
                "to": question.get("difficulty_level"),
                "at_question": session.current_question_index,
            })
            session.difficulty_level = question.get("difficulty_level")

        return session

    def close_session(self, session_id: str) -> Dict[str, Any]:
        session = self.sessions.pop(session_id, None)
        if not session:
            return {"error": "session_not_found"}

        summary = {
            "session_id": session.session_id,
            "interview_type": session.interview_type,
            "questions_asked": len(session.questions),
            "final_difficulty": session.difficulty_level,
            "average_score": (
                round(session.total_score / max(len(session.questions), 1), 1)
                if session.questions else 0
            ),
            "confidence_trend": session.confidence_progression,
            "weaknesses_detected": dict(session.weakness_tracker),
            "adaptation_history": session.adaptation_history,
            "duration_s": round(time.time() - session.created_at, 1),
        }

        self.past_sessions.append(summary)
        if len(self.past_sessions) > self.max_past_sessions:
            self.past_sessions = self.past_sessions[-self.max_past_sessions:]

        self._update_weakness_registry(summary)
        return summary

    def get_past_sessions(
        self, interview_type: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        sessions = self.past_sessions
        if interview_type:
            sessions = [s for s in sessions if s.get("interview_type") == interview_type]
        return sessions[-limit:]

    def get_weakness_progression(self) -> Dict[str, List[Dict[str, Any]]]:
        return dict(self.weakness_registry)

    def get_improvement_progression(
        self, weakness_type: str
    ) -> List[Dict[str, Any]]:
        return self.weakness_registry.get(weakness_type, [])

    def _update_weakness_registry(self, summary: Dict[str, Any]) -> None:
        for weakness, count in summary.get("weaknesses_detected", {}).items():
            if weakness not in self.weakness_registry:
                self.weakness_registry[weakness] = []
            self.weakness_registry[weakness].append({
                "session_id": summary["session_id"],
                "count": count,
                "date": summary.get("created_at", time.time()),
            })


_svc: InterviewMemoryService | None = None


def get_interview_memory_service() -> InterviewMemoryService:
    global _svc
    if _svc is None:
        _svc = InterviewMemoryService()
    return _svc


def reset_interview_memory_service() -> None:
    global _svc
    _svc = None


def __getattr__(name: str):
    if name == "interview_memory_service":
        return get_interview_memory_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
