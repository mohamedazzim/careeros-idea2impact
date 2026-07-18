"""
Tests for interview rubric service — structured evaluation rubrics.

Phase 4D: Rubric evaluation strategy validation.
"""
import pytest
from src.services.interview.interview_rubric_service import (
    InterviewRubricService,
    RubricDimension,
)


@pytest.fixture
def svc():
    return InterviewRubricService()


class TestRubricService:
    def test_technical_rubric_dimensions(self, svc):
        rubrics = svc.get_technical_rubric()
        names = {r.name for r in rubrics}
        assert "technical_depth" in names
        assert "problem_solving" in names
        assert "architecture_reasoning" in names
        assert "tradeoff_awareness" in names
        assert "production_realism" in names
        assert "communication_clarity" in names
        assert len(rubrics) == 6

    def test_coding_rubric_dimensions(self, svc):
        rubrics = svc.get_coding_rubric()
        names = {r.name for r in rubrics}
        assert "algorithmic_thinking" in names
        assert "code_quality" in names
        assert "edge_case_handling" in names
        assert "testing_approach" in names
        assert "optimization_reasoning" in names
        assert "language_proficiency" in names
        assert len(rubrics) == 6

    def test_system_design_rubric_dimensions(self, svc):
        rubrics = svc.get_system_design_rubric()
        names = {r.name for r in rubrics}
        assert "scalability_reasoning" in names
        assert "architecture_decomposition" in names
        assert "fault_tolerance" in names
        assert "observability_reasoning" in names
        assert "async_orchestration" in names
        assert "governance_reasoning" in names
        assert "deployment_reasoning" in names
        assert "tradeoff_reasoning" in names
        assert len(rubrics) == 8

    def test_ai_engineering_rubric_dimensions(self, svc):
        rubrics = svc.get_ai_engineering_rubric()
        names = {r.name for r in rubrics}
        assert "rag_understanding" in names
        assert "vector_db_reasoning" in names
        assert "orchestration_reasoning" in names
        assert "governance_understanding" in names
        assert "mcp_understanding" in names
        assert "langgraph_understanding" in names
        assert "inference_optimization" in names
        assert "production_ai" in names
        assert len(rubrics) == 8

    def test_behavioral_rubric_dimensions(self, svc):
        rubrics = svc.get_behavioral_rubric()
        names = {r.name for r in rubrics}
        assert "leadership_signals" in names
        assert "conflict_resolution" in names
        assert "collaboration_patterns" in names
        assert "growth_mindset" in names
        assert "impact_communication" in names
        assert "stakeholder_management" in names
        assert "failure_response" in names
        assert len(rubrics) == 7

    def test_rubric_dimension_attributes(self, svc):
        dims = svc.get_technical_rubric()
        td = dims[0]
        assert td.name == "technical_depth"
        assert td.weight > 0
        assert td.evidence_required is True
        assert td.score_range == (0, 100)

    def test_score_dimension_by_name(self, svc):
        dim = RubricDimension("test_dim", "test desc", 1.0)
        result = svc.score_dimension(dim, {"test_dim": 75, "citations": []})
        assert result["dimension"] == "test_dim"
        assert result["score"] == 75
        assert result["weight"] == 1.0

    def test_score_dimension_clamped(self, svc):
        dim = RubricDimension("test_dim", "test", 1.0)
        result = svc.score_dimension(dim, {"test_dim": 150, "citations": []})
        assert result["score"] == 100

    def test_score_dimension_negative_clamped(self, svc):
        dim = RubricDimension("test_dim", "test", 1.0)
        result = svc.score_dimension(dim, {"test_dim": -10, "citations": []})
        assert result["score"] == 0

    def test_score_dimension_with_citations(self, svc):
        dim = RubricDimension("test_dim", "test", 1.0)
        result = svc.score_dimension(dim, {
            "test_dim": 80,
            "citations": [
                {"dimension": "test_dim", "passage": "evidence"},
                {"dimension": "test_dim", "passage": "evidence2"},
            ],
        })
        assert result["evidence_quality"] == 1.0
        assert result["evidence_sufficient"] is True

    def test_score_dimension_insufficient_citations(self, svc):
        dim = RubricDimension("test_dim", "test", 1.0)
        result = svc.score_dimension(dim, {
            "test_dim": 80,
            "citations": [],
        })
        assert result["evidence_quality"] == 0.0
        assert result["evidence_sufficient"] is False

    def test_compute_weighted_score(self, svc):
        rubrics = [
            RubricDimension("a", "desc", 2.0),
            RubricDimension("b", "desc", 1.0),
        ]
        scores = {"a": 80.0, "b": 40.0}
        result = svc.compute_weighted_score(rubrics, scores)
        expected = (80 * 2.0 + 40 * 1.0) / 3.0
        assert result["overall_score"] == pytest.approx(expected, 0.1)
        assert result["dimension_count"] == 2
        assert "per_dimension" in result

    def test_compute_weighted_score_single_dimension(self, svc):
        rubrics = [RubricDimension("only", "desc", 1.0)]
        scores = {"only": 90.0}
        result = svc.compute_weighted_score(rubrics, scores)
        assert result["overall_score"] == 90.0

    def test_all_rubrics_have_weights(self, svc):
        for getter in [
            svc.get_technical_rubric,
            svc.get_coding_rubric,
            svc.get_system_design_rubric,
            svc.get_ai_engineering_rubric,
            svc.get_behavioral_rubric,
        ]:
            rubrics = getter()
            for r in rubrics:
                assert r.weight > 0, f"{r.name} has weight <= 0"

    def test_all_dimensions_have_descriptions(self, svc):
        for getter in [
            svc.get_technical_rubric,
            svc.get_coding_rubric,
            svc.get_system_design_rubric,
            svc.get_ai_engineering_rubric,
            svc.get_behavioral_rubric,
        ]:
            rubrics = getter()
            for r in rubrics:
                assert len(r.description) > 5, f"{r.name} has short description"
