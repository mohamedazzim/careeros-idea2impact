"""
Tests for interview trace builder — explainability chain construction.

Phase 4D: Interview explainability validation.
"""
import pytest
import time
from src.services.interview.interview_trace_builder import InterviewTraceBuilder


@pytest.fixture
def builder():
    return InterviewTraceBuilder()


class TestTraceBuilder:
    def test_build_trace_basic(self, builder):
        evaluation = {
            "overall_score": 75.0,
            "interview_type": "technical",
            "difficulty": "advanced",
            "dimension_scores": {
                "technical_depth": {"score": 80, "weight": 1.5},
            },
            "citations": [{"passage": "good answer"}],
            "confidence": {"overall": 0.78},
            "weaknesses": ["architecture_reasoning"],
            "evidence_sufficient": True,
        }
        difficulty = {"level": "advanced", "changed": True, "reason": "high_performance"}
        claude_raw = {"reasoning": ["step 1", "step 2"]}

        trace = builder.build_trace("session_1", 3, evaluation, difficulty, claude_raw)

        assert trace["session_id"] == "session_1"
        assert trace["question_index"] == 3
        assert trace["evaluation"]["overall_score"] == 75.0
        assert trace["evaluation"]["interview_type"] == "technical"
        assert trace["evaluation"]["difficulty"] == "advanced"
        assert trace["reasoning_chain"] == ["step 1", "step 2"]
        assert len(trace["rubric_references"]) == 1
        assert len(trace["evidence_citations"]) == 1
        assert trace["confidence"]["overall"] == 0.78
        assert len(trace["weakness_rationale"]) == 1
        assert trace["difficulty_rationale"]["reason"] == "high_performance"
        assert trace["adaptation_rationale"] == "high_performance"

    def test_build_trace_with_data_attribute(self, builder):
        class ClaudeOutput:
            data = {"reasoning": ["s1", "s2"], "analysis": ["extra"]}
        evaluation = {"overall_score": 60, "interview_type": "coding", "difficulty": "intermediate",
                      "dimension_scores": {}, "citations": [], "confidence": {}, "weaknesses": [],
                      "evidence_sufficient": True}
        difficulty = {"level": "intermediate", "changed": False, "reason": "stable"}
        trace = builder.build_trace("s2", 1, evaluation, difficulty, ClaudeOutput())
        assert trace["reasoning_chain"] == ["s1", "s2"]

    def test_build_session_trace(self, builder):
        traces = [
            {"governance_flags": {"hallucination_check": True, "contradiction_check": True, "rubric_alignment": True}},
            {"governance_flags": {"hallucination_check": True, "contradiction_check": False, "rubric_alignment": False}},
        ]
        summary = {"adaptation_history": [{"from": "intermediate", "to": "advanced"}],
                   "confidence_trend": [0.7, 0.8]}
        patterns = {"severity": "medium"}

        result = builder.build_session_trace("sid", traces, summary, patterns)
        assert result["session_id"] == "sid"
        assert result["trace_type"] == "interview_session"
        assert result["question_count"] == 2
        assert "governance_verdict" in result
        assert result["governance_verdict"]["hallucination_rejected"] is True
        assert result["governance_verdict"]["contradictions_analyzed"] is False

    def test_extract_reasoning_chain_from_dict(self, builder):
        claude_raw = {"analysis": ["a1", "a2"]}
        result = builder._extract_reasoning_chain(claude_raw)
        assert result == ["a1", "a2"]

    def test_extract_rubric_references(self, builder):
        evaluation = {
            "dimension_scores": {
                "technical_depth": {"score": 85, "weight": 1.5},
                "problem_solving": {"score": 60, "weight": 1.5},
            },
        }
        refs = builder._extract_rubric_references(evaluation)
        assert len(refs) == 2
        assert refs[0]["dimension"] == "technical_depth"

    def test_build_weakness_rationale(self, builder):
        evaluation = {
            "weaknesses": ["poor scalability reasoning", "weak communication"],
            "dimension_scores": {
                "scalability": {"score": 30},
                "communication": {"score": 45},
                "architecture": {"score": 80},
            },
        }
        rationale = builder._build_weakness_rationale(evaluation)
        assert len(rationale) == 2
        assert rationale[0]["weakness"] == "poor scalability reasoning"

    def test_compute_governance_verdict_all_pass(self, builder):
        traces = [
            {"governance_flags": {"hallucination_check": True, "contradiction_check": True, "rubric_alignment": True}},
        ]
        verdict = builder._compute_governance_verdict(traces, {"severity": "low"})
        assert verdict["overall_valid"] is True
        assert verdict["hallucination_rejected"] is True

    def test_trace_contains_timestamp(self, builder):
        evaluation = {"overall_score": 70, "interview_type": "technical", "difficulty": "intermediate",
                      "dimension_scores": {}, "citations": [], "confidence": {}, "weaknesses": [],
                      "evidence_sufficient": True}
        difficulty = {"level": "intermediate", "changed": False, "reason": "stable"}
        claude_raw = {}
        trace = builder.build_trace("s1", 0, evaluation, difficulty, claude_raw)
        assert "timestamp" in trace
        assert trace["timestamp"] > 0
