"""
Tests for interview confidence engine — per-question/session confidence calibration.

Phase 4D: Confidence calibration validation.
"""
import pytest
from src.services.interview.interview_confidence_engine import InterviewConfidenceEngine


@pytest.fixture
def engine():
    return InterviewConfidenceEngine()


class TestConfidenceEngine:
    def test_calibrate_default(self, engine):
        result = engine.calibrate(
            evaluation_outputs={"score": 60, "difficulty_level": "intermediate"},
        )
        assert "overall" in result
        assert 0.0 <= result["overall"] <= 1.0
        assert "evidence_score" in result
        assert "consistency_score" in result
        assert "difficulty_alignment" in result
        assert "contradiction_penalty" in result

    def test_calibrate_with_explicit_base(self, engine):
        result = engine.calibrate(
            evaluation_outputs={"score": 60, "difficulty_level": "intermediate"},
            base_confidence=0.9,
        )
        assert result["base_confidence"] == 0.9

    def test_calibrate_with_citations(self, engine):
        result = engine.calibrate(
            evaluation_outputs={
                "score": 80,
                "difficulty_level": "advanced",
                "citations": [{"passage": "evidence"}],
                "claims": [
                    {"evidence_citations": ["cite1"]},
                    {"evidence_citations": ["cite2"]},
                ],
            },
        )
        assert result["evidence_score"] > 0.3

    def test_calibrate_no_citations_low_evidence(self, engine):
        result = engine.calibrate(
            evaluation_outputs={
                "score": 80,
                "difficulty_level": "advanced",
                "citations": [],
                "claims": [{"evidence_citations": None}, {"evidence_citations": None}],
            },
        )
        assert result["evidence_score"] <= 0.5

    def test_calibrate_consistency_with_history(self, engine):
        result = engine.calibrate(
            evaluation_outputs={"score": 70, "difficulty_level": "intermediate"},
            answer_history=[
                {"confidence": 0.7},
                {"confidence": 0.72},
                {"confidence": 0.68},
            ],
        )
        assert result["consistency_score"] > 0.8

    def test_calibrate_no_history(self, engine):
        result = engine.calibrate(
            evaluation_outputs={"score": 70, "difficulty_level": "intermediate"},
            answer_history=[],
        )
        assert result["consistency_score"] == 0.7

    def test_calibrate_with_contradictions(self, engine):
        result = engine.calibrate(
            evaluation_outputs={"score": 70, "difficulty_level": "intermediate"},
            contradictions={
                "contradictions_detected": True,
                "severity": "high",
            },
        )
        assert result["contradiction_penalty"] > 0.05
        assert result["overall"] < 0.7

    def test_calibrate_contradiction_no_penalty(self, engine):
        result = engine.calibrate(
            evaluation_outputs={"score": 70, "difficulty_level": "intermediate"},
            contradictions={
                "contradictions_detected": True,
                "severity": "none",
            },
        )
        assert result["contradiction_penalty"] == 0.0

    def test_calibrate_contradiction_critical(self, engine):
        result = engine.calibrate(
            evaluation_outputs={"score": 50, "difficulty_level": "beginner"},
            contradictions={
                "contradictions_detected": True,
                "severity": "critical",
            },
        )
        assert result["contradiction_penalty"] >= 0.25
        assert result["overall"] >= 0.05

    def test_difficulty_alignment_perfect(self, engine):
        result = engine.calibrate(
            evaluation_outputs={"score": 60, "difficulty_level": "intermediate"},
        )
        assert result["difficulty_alignment"] > 0.7

    def test_difficulty_alignment_mismatch(self, engine):
        result = engine.calibrate(
            evaluation_outputs={"score": 10, "difficulty_level": "staff"},
        )
        assert result["difficulty_alignment"] < 0.5

    def test_overall_range(self, engine):
        for score in [0, 25, 50, 75, 100]:
            for level in ["beginner", "intermediate", "advanced", "senior", "staff"]:
                result = engine.calibrate(
                    evaluation_outputs={"score": score, "difficulty_level": level},
                )
                assert 0.0 <= result["overall"] <= 1.0, f"score={score}, level={level}"

    def test_calibrate_with_claims_no_citations(self, engine):
        result = engine.calibrate(
            evaluation_outputs={
                "score": 50,
                "difficulty_level": "intermediate",
                "claims": [
                    {"evidence_citations": None},
                    {"evidence_citations": ["cite1"]},
                ],
            },
        )
        assert 0.4 <= result["evidence_score"] <= 0.6
