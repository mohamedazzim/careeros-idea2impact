"""
Tests for weakness pattern detection — longitudinal pattern identification.

Phase 4D: Weakness-pattern detection methodology validation.
"""
import pytest
from src.services.interview.weakness_pattern_service import WeaknessPatternService


@pytest.fixture
def svc():
    return WeaknessPatternService()


class TestWeaknessPatternDetection:
    def test_detect_no_patterns_empty(self, svc):
        result = svc.detect_patterns([], [])
        assert result["total_patterns_detected"] == 0
        assert result["severity"] == "low"

    def test_detect_repeated_weak_areas(self, svc):
        session_history = [
            {"weaknesses_detected": {"scalability": 3, "architecture": 2}},
            {"weaknesses_detected": {"scalability": 2}},
        ]
        question_history = [
            {"weaknesses": ["scalability"]},
            {"weaknesses": ["scalability"]},
        ]
        result = svc.detect_patterns(session_history, question_history)
        assert result["total_patterns_detected"] >= 1
        classified = result["pattern_classification"]
        assert len(classified["scalability_weaknesses"]) > 0

    def test_classify_architecture_gaps(self, svc):
        session_history = [
            {"weaknesses_detected": {"architecture_design": 3}},
            {"weaknesses_detected": {"architecture_design": 2}},
        ]
        result = svc.detect_patterns(session_history, [])
        classified = result["pattern_classification"]
        assert len(classified["architecture_gaps"]) > 0

    def test_classify_ai_engineering_gaps(self, svc):
        session_history = [
            {"weaknesses_detected": {"rag_understanding": 3, "vector_search": 2}},
            {"weaknesses_detected": {"langgraph": 2}},
        ]
        result = svc.detect_patterns(session_history, [])
        classified = result["pattern_classification"]
        assert len(classified["ai_engineering_gaps"]) > 0

    def test_classify_communication_weaknesses(self, svc):
        session_history = [
            {"weaknesses_detected": {"communication_clarity": 3}},
            {"weaknesses_detected": {"articulation": 2}},
        ]
        result = svc.detect_patterns(session_history, [])
        classified = result["pattern_classification"]
        assert len(classified["communication_weaknesses"]) > 0

    def test_classify_scalability_weaknesses(self, svc):
        session_history = [
            {"weaknesses_detected": {"scale_planning": 3, "optimization": 2}},
        ]
        result = svc.detect_patterns(session_history, [])
        classified = result["pattern_classification"]
        assert len(classified["scalability_weaknesses"]) > 0

    def test_classify_repeated_contradictions(self, svc):
        session_history = [
            {"weaknesses_detected": {"contradiction_in_claims": 3}},
            {"weaknesses_detected": {"inconsistency": 2}},
        ]
        result = svc.detect_patterns(session_history, [])
        classified = result["pattern_classification"]
        assert len(classified["repeated_contradictions"]) > 0

    def test_question_history_weakness_dicts(self, svc):
        question_history = [
            {"weaknesses": [{"dimension": "scalability"}, {"dimension": "testing"}]},
            {"weaknesses": ["scalability"]},
            {"weaknesses": [{"dimension": "testing"}]},
        ]
        result = svc.detect_patterns([], question_history)
        assert result["total_patterns_detected"] >= 1

    def test_minimum_count_threshold(self, svc):
        session_history = [
            {"weaknesses_detected": {"single_issue": 1}},
        ]
        result = svc.detect_patterns(session_history, [])
        assert result["total_patterns_detected"] == 0

    def test_severity_low(self, svc):
        session_history = [
            {"weaknesses_detected": {"pattern_a": 2}},
        ]
        result = svc.detect_patterns(session_history, [])
        assert result["severity"] == "low"

    def test_severity_medium(self, svc):
        session_history = [
            {"weaknesses_detected": {"a": 2, "b": 2}},
        ]
        result = svc.detect_patterns(session_history, [])
        assert result["severity"] in ["low", "medium"]

    def test_severity_high(self, svc):
        session_history = [
            {"weaknesses_detected": {"a": 2, "b": 2, "c": 2, "d": 2, "e": 2, "f": 2}},
        ]
        result = svc.detect_patterns(session_history, [])
        assert result["severity"] == "high"

    def test_raw_weakness_counts(self, svc):
        session_history = [
            {"weaknesses_detected": {"a": 5, "b": 3}},
            {"weaknesses_detected": {"a": 2}},
        ]
        result = svc.detect_patterns(session_history, [])
        assert result["raw_weakness_counts"]["a"] == 7
        assert result["raw_weakness_counts"]["b"] == 3

    def test_mixed_session_and_question(self, svc):
        session_history = [
            {"weaknesses_detected": {"architecture": 3}},
        ]
        question_history = [
            {"weaknesses": ["communication"]},
            {"weaknesses": ["communication"]},
        ]
        result = svc.detect_patterns(session_history, question_history)
        classified = result["pattern_classification"]
        assert len(classified["architecture_gaps"]) > 0
        assert len(classified["communication_weaknesses"]) > 0
