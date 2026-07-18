"""
Tests for interview observability — metrics emission validation.

Phase 4D: Observability metrics validation.
"""
import pytest
from src.services.interview.interview_observability import (
    InterviewObservability,
    reset_interview_observability,
)


@pytest.fixture(autouse=True)
def reset_obs():
    reset_interview_observability()
    yield
    reset_interview_observability()


@pytest.fixture
def obs():
    return InterviewObservability()


class TestInterviewObservability:
    def test_record_interview_call(self, obs):
        obs.record_interview_call("technical", "success", 250.0)

    def test_record_adaptive_transition(self, obs):
        obs.record_adaptive_transition("intermediate", "advanced", "high_performance")

    def test_record_difficulty_escalation(self, obs):
        obs.record_difficulty_escalation("technical", "senior")

    def test_record_hallucination(self, obs):
        obs.record_hallucination("technical", "high")

    def test_record_critique_suppression(self, obs):
        obs.record_critique_suppression("unsupported_critique")

    def test_record_contradiction_pressure(self, obs):
        obs.record_contradiction_pressure("behavioral", "medium")

    def test_record_rubric_confidence(self, obs):
        obs.record_rubric_confidence("technical", 0.82)

    def test_record_concurrency_pressure(self, obs):
        obs.record_concurrency_pressure(5)

    def test_record_session_token_pressure(self, obs):
        obs.record_session_token_pressure("session_abc123", 15000)

    def test_record_weakness_pattern(self, obs):
        obs.record_weakness_pattern("architecture_gaps", 3)

    def test_all_methods_smoke(self, obs):
        obs.record_interview_call("coding", "error", 500.0)
        obs.record_adaptive_transition("beginner", "intermediate", "low_performance")
        obs.record_difficulty_escalation("system_design", "staff")
        obs.record_hallucination("ai_engineering", "critical")
        obs.record_critique_suppression("hallucinated_weakness")
        obs.record_contradiction_pressure("technical", "critical")
        obs.record_rubric_confidence("coding", 0.45)
        obs.record_concurrency_pressure(20)
        obs.record_session_token_pressure("xyz_123", 50000)
        obs.record_weakness_pattern("scalability_weaknesses", 7)
