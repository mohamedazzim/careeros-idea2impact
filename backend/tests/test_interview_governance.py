"""
Tests for interview governance — hallucination detection and critique validation.

Phase 4D: Interview governance strategy validation.
"""
import pytest
from src.services.interview.interview_governance import InterviewGovernance


@pytest.fixture
def gov():
    return InterviewGovernance()


class TestInterviewGovernance:
    def test_validate_clean_evaluation(self, gov):
        rubric = []
        evaluation = {
            "weaknesses": ["weak_area"],
            "citations": [{"passage": "evidence about weak_area"}],
            "dimension_scores": {"technical_depth": {"score": 70}},
            "confidence": {"overall": 0.85},
        }
        result = gov.validate_evaluation(evaluation, rubric, "candidate evidence about weak_area")
        assert result["valid"] is True
        assert result["violations_detected"] == 0
        assert result["governance_verdict"] == "passed"

    def test_detect_unsupported_critique(self, gov):
        evaluation = {
            "weaknesses": ["weak1", "weak2", "weak3"],
            "citations": [],
            "dimension_scores": {},
        }
        result = gov.validate_evaluation(evaluation, [], "")
        assert result["valid"] is False
        violations = {v["type"] for v in result["violations"]}
        assert "unsupported_critique" in violations

    def test_detect_hallucinated_weaknesses(self, gov):
        evaluation = {
            "weaknesses": [
                "quantum_computing_expertise",
                "neural_interface_design",
            ],
            "citations": [],
        }
        evidence = "The candidate has experience in Python, Django, and AWS."
        result = gov.validate_evaluation(evaluation, [], evidence)
        assert result["valid"] is False
        mitigated = result.get("mitigations_applied", {})
        assert mitigated.get("hallucinated_weaknesses_removed")

    def test_detect_unsupported_scoring(self, gov):
        evaluation = {
            "dimension_scores": {"scalability": 85, "architecture": 70},
            "citations": [],
            "weaknesses": [],
        }
        result = gov.validate_evaluation(evaluation, [], "")
        assert not result["valid"]
        violations = {v["type"] for v in result["violations"]}
        assert "unsupported_scoring" in violations

    def test_detect_rubric_inconsistency(self, gov):
        from src.services.interview.interview_rubric_service import RubricDimension
        rubric = [RubricDimension("technical_depth", "...", 1.0)]
        evaluation = {
            "dimension_scores": {
                "technical_depth": {"score": 80},
                "made_up_dimension": {"score": 95},
            },
            "citations": [],
            "weaknesses": [],
        }
        result = gov.validate_evaluation(evaluation, rubric, "")
        violations = {v["type"] for v in result["violations"]}
        assert "rubric_inconsistency" in violations

    def test_confidence_reduction_on_violations(self, gov):
        evaluation = {
            "weaknesses": ["weak1", "weak2"],
            "citations": [],
            "dimension_scores": {},
            "confidence": {"overall": 0.85},
        }
        result = gov.validate_evaluation(evaluation, [], "")
        mitigated = result["mitigations_applied"]
        assert mitigated["original_confidence"] == 0.85
        assert mitigated["adjusted_confidence"] < 0.85
        assert mitigated["violations_suppressed"] > 0

    def test_hallucinated_detection_exact_match(self, gov):
        evaluation = {"weaknesses": ["python"]}
        evidence = "Candidate has strong Python experience with python projects"
        result = gov.validate_evaluation(evaluation, [], evidence)
        mitigated = result.get("mitigations_applied", {})
        assert "python" not in str(mitigated.get("hallucinated_weaknesses_removed", []))

    def test_no_false_positives_on_clean_data(self, gov):
        from src.services.interview.interview_rubric_service import RubricDimension
        rubric = [RubricDimension("technical_depth", "desc", 1.0)]
        evaluation = {
            "weaknesses": ["could improve architecture reasoning"],
            "citations": [{"dimension": "technical_depth", "passage": "good answer"}],
            "dimension_scores": {"technical_depth": {"score": 75}},
            "confidence": {"overall": 0.8},
        }
        evidence = "The candidate demonstrated architecture reasoning"
        result = gov.validate_evaluation(evaluation, rubric, evidence)
        assert result["valid"] is True

    def test_empty_evaluation_passes(self, gov):
        evaluation = {"weaknesses": [], "citations": [], "dimension_scores": {}}
        result = gov.validate_evaluation(evaluation, [], "")
        assert result["valid"] is True

    def test_governance_verdict_mitigated(self, gov):
        evaluation = {
            "weaknesses": ["fabricated_gap"],
            "citations": [],
            "dimension_scores": {"a": {"score": 50}},
            "confidence": {"overall": 0.7},
        }
        result = gov.validate_evaluation(evaluation, [], "")
        assert result["governance_verdict"] == "mitigated"
