"""
Tests for interview persistence service — Redis + PostgreSQL session storage.

Phase 4D Hardening: Persistence validation tests.
"""
import pytest
import time
from src.services.interview.interview_persistence_service import (
    InterviewPersistenceService,
    SessionState,
    reset_interview_persistence_service,
)


@pytest.fixture(autouse=True)
def reset_svc():
    reset_interview_persistence_service()
    yield
    reset_interview_persistence_service()


@pytest.fixture
def svc():
    return InterviewPersistenceService()


class TestSessionSerialization:
    def test_serialize_deserialize_roundtrip(self, svc):
        session = SessionState(
            session_id="test_sid",
            interview_type="technical",
            difficulty_level="advanced",
            current_question_index=3,
            total_score=240.0,
            confidence_progression=[0.7, 0.8, 0.75],
            weakness_tracker={"scalability": 2},
            adaptation_history=[{"from": "intermediate", "to": "advanced"}],
            metadata={"has_ats": True},
        )
        data = {
            "session_id": session.session_id,
            "interview_type": session.interview_type,
            "difficulty_level": session.difficulty_level,
            "current_question_index": str(session.current_question_index),
            "total_score": str(session.total_score),
            "confidence_progression": '[0.7, 0.8, 0.75]',
            "weakness_tracker": '{"scalability": 2}',
            "adaptation_history": '[{"from": "intermediate", "to": "advanced"}]',
            "metadata": '{"has_ats": true}',
            "status": session.status,
            "created_at": str(session.created_at),
            "db_id": "None",
        }
        restored = svc._deserialize_session(data)
        assert restored.session_id == "test_sid"
        assert restored.interview_type == "technical"
        assert restored.difficulty_level == "advanced"
        assert restored.current_question_index == 3
        assert restored.total_score == 240.0
        assert restored.confidence_progression == [0.7, 0.8, 0.75]
        assert restored.weakness_tracker == {"scalability": 2}

    def test_deserialize_with_missing_fields(self, svc):
        restored = svc._deserialize_session({})
        assert restored.session_id == ""
        assert restored.interview_type == "technical"
        assert restored.difficulty_level == "intermediate"
        assert restored.current_question_index == 0

    def test_deserialize_invalid_json(self, svc):
        data = {
            "session_id": "bad",
            "interview_type": "technical",
            "difficulty_level": "intermediate",
            "current_question_index": "0",
            "total_score": "0.0",
            "confidence_progression": "not_json",
            "weakness_tracker": "{bad",
            "adaptation_history": "also_bad",
            "metadata": "nope",
            "status": "active",
            "created_at": "0",
            "db_id": "None",
        }
        restored = svc._deserialize_session(data)
        assert restored.confidence_progression == []
        assert restored.weakness_tracker == {}
        assert restored.adaptation_history == []
        assert restored.metadata == {}

    def test_session_key_prefix(self, svc):
        key = svc._session_key("abc123")
        assert "session:" in key
        assert "abc123" in key

    def test_questions_key_prefix(self, svc):
        key = svc._questions_key("abc123")
        assert "questions:" in key
        assert "abc123" in key

    def test_json_list_null(self):
        assert InterviewPersistenceService._json_list("null") == []
        assert InterviewPersistenceService._json_list("") == []

    def test_json_dict_null(self):
        assert InterviewPersistenceService._json_dict("null") == {}
        assert InterviewPersistenceService._json_dict("") == {}


class TestSessionState:
    def test_session_state_defaults(self):
        session = SessionState(session_id="s1", interview_type="coding")
        assert session.difficulty_level == "intermediate"
        assert session.questions == []
        assert session.current_question_index == 0
        assert session.total_score == 0.0
        assert session.status == "active"
        assert session.db_id is None

    def test_session_state_created_at(self):
        t0 = time.time()
        session = SessionState(session_id="s1", interview_type="technical")
        assert session.created_at >= t0
