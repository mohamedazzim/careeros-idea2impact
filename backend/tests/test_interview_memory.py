"""
Tests for interview memory service — session state and longitudinal history.

Phase 4D: Interview memory persistence validation.
"""
import pytest
import time
from src.services.interview.interview_memory_service import (
    InterviewMemoryService,
    SessionState,
    QuestionRecord,
)


@pytest.fixture
def mem():
    svc = InterviewMemoryService()
    yield svc


class TestInterviewMemory:
    def test_create_session(self, mem):
        session = mem.create_session("s1", "technical", "intermediate")
        assert session.session_id == "s1"
        assert session.interview_type == "technical"
        assert session.difficulty_level == "intermediate"
        assert session.questions == []
        assert session.current_question_index == 0
        assert "s1" in mem.sessions

    def test_get_session(self, mem):
        mem.create_session("s1", "coding", "advanced")
        session = mem.get_session("s1")
        assert session is not None
        assert session.interview_type == "coding"

    def test_get_nonexistent_session(self, mem):
        assert mem.get_session("nonexistent") is None

    def test_add_question(self, mem):
        mem.create_session("s1", "technical")
        mem.add_question("s1", {
            "question": "What is CAP theorem?",
            "score": 80,
            "confidence": 0.75,
            "difficulty_level": "intermediate",
            "interview_type": "technical",
        })
        session = mem.get_session("s1")
        assert session.current_question_index == 1
        assert session.total_score == 80
        assert session.confidence_progression == [0.75]

    def test_add_question_with_weaknesses(self, mem):
        mem.create_session("s1", "technical")
        mem.add_question("s1", {
            "question": "Q1",
            "score": 60,
            "weaknesses": ["technical_depth"],
        })
        session = mem.get_session("s1")
        assert session.weakness_tracker.get("technical_depth") == 1

    def test_add_question_weakness_list_of_dicts(self, mem):
        mem.create_session("s1", "technical")
        mem.add_question("s1", {
            "question": "Q1",
            "score": 50,
            "weaknesses": [{"dimension": "architecture_reasoning"}],
        })
        session = mem.get_session("s1")
        assert session.weakness_tracker.get("architecture_reasoning") == 1

    def test_add_question_adaptation_tracking(self, mem):
        mem.create_session("s1", "technical", "intermediate")
        mem.add_question("s1", {
            "question": "Q1",
            "score": 85,
            "difficulty_level": "advanced",
        })
        session = mem.get_session("s1")
        assert session.difficulty_level == "advanced"
        assert len(session.adaptation_history) == 1
        assert session.adaptation_history[0]["from"] == "intermediate"
        assert session.adaptation_history[0]["to"] == "advanced"

    def test_close_session(self, mem):
        mem.create_session("s1", "technical", "intermediate")
        mem.add_question("s1", {
            "question": "Q1", "score": 80, "confidence": 0.8,
            "weaknesses": ["communication_clarity"],
            "difficulty_level": "intermediate",
            "interview_type": "technical",
        })
        mem.add_question("s1", {
            "question": "Q2", "score": 65, "confidence": 0.6,
            "weaknesses": ["communication_clarity", "tradeoff_awareness"],
            "difficulty_level": "intermediate",
            "interview_type": "technical",
        })

        summary = mem.close_session("s1")
        assert summary["questions_asked"] == 2
        assert summary["final_difficulty"] == "intermediate"
        assert summary["average_score"] == 72.5
        assert summary["confidence_trend"] == [0.8, 0.6]
        assert summary["weaknesses_detected"]["communication_clarity"] == 2

        assert "s1" not in mem.sessions
        assert len(mem.past_sessions) == 1

    def test_close_nonexistent_session(self, mem):
        result = mem.close_session("nonexistent")
        assert "error" in result

    def test_get_past_sessions_filtered(self, mem):
        mem.create_session("s1", "technical")
        mem.add_question("s1", {
            "question": "Q1", "score": 70,
            "difficulty_level": "intermediate", "interview_type": "technical",
        })
        mem.close_session("s1")

        mem.create_session("s2", "behavioral")
        mem.add_question("s2", {
            "question": "Q1", "score": 70,
            "difficulty_level": "intermediate", "interview_type": "behavioral",
        })
        mem.close_session("s2")

        tech = mem.get_past_sessions(interview_type="technical")
        assert len(tech) == 1
        assert tech[0]["interview_type"] == "technical"

    def test_weakness_progression(self, mem):
        mem.create_session("s1", "technical")
        mem.add_question("s1", {
            "question": "Q1", "score": 60,
            "weaknesses": ["scalability_reasoning"],
            "difficulty_level": "intermediate", "interview_type": "technical",
        })
        mem.close_session("s1")

        mem.create_session("s2", "technical")
        mem.add_question("s2", {
            "question": "Q2", "score": 55,
            "weaknesses": ["scalability_reasoning"],
            "difficulty_level": "intermediate", "interview_type": "technical",
        })
        mem.close_session("s2")

        prog = mem.get_weakness_progression()
        assert "scalability_reasoning" in prog
        assert len(prog["scalability_reasoning"]) == 2

    def test_get_improvement_progression(self, mem):
        mem.create_session("s1", "technical")
        mem.add_question("s1", {
            "question": "Q1", "score": 40,
            "weaknesses": ["rag_understanding"],
            "difficulty_level": "intermediate", "interview_type": "technical",
        })
        mem.close_session("s1")

        history = mem.get_improvement_progression("rag_understanding")
        assert len(history) == 1
        assert history[0]["session_id"] == "s1"

    def test_past_sessions_max_limit(self, mem):
        for i in range(25):
            sid = f"s{i}"
            mem.create_session(sid, "technical")
            mem.add_question(sid, {
                "question": f"Q{i}", "score": 70,
                "difficulty_level": "intermediate", "interview_type": "technical",
            })
            mem.close_session(sid)
        assert len(mem.past_sessions) == mem.max_past_sessions

    def test_create_session_with_metadata(self, mem):
        session = mem.create_session("s1", "technical", metadata={
            "has_ats": True, "candidate_id": "c123"
        })
        assert session.metadata["has_ats"] is True
        assert session.metadata["candidate_id"] == "c123"

    def test_add_question_creates_session_if_missing(self, mem):
        mem.add_question("auto_create", {
            "question": "Q1", "score": 70,
            "difficulty_level": "intermediate", "interview_type": "system_design",
        })
        session = mem.get_session("auto_create")
        assert session is not None
        assert session.interview_type == "system_design"
