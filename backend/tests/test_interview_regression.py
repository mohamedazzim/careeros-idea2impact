"""
Interview intelligence regression benchmarks — integration validation.

Phase 4D: Comprehensive regression benchmark across all interview components.
Validates: orchestration flow, rubric scoring, governance rejection,
confidence calibration, weakness detection, memory persistence, and
explainability trace construction.
"""
import os
import pytest
import time

from src.services.interview.interview_memory_service import reset_interview_memory_service
from src.services.interview.interview_observability import reset_interview_observability
from src.services.interview.adaptive_difficulty_service import AdaptiveDifficultyService
from src.services.interview.interview_orchestrator import InterviewOrchestrator
from src.services.interview.interview_rubric_service import InterviewRubricService
from src.services.interview.interview_governance import InterviewGovernance
from src.services.interview.interview_confidence_engine import InterviewConfidenceEngine
from src.services.interview.weakness_pattern_service import WeaknessPatternService
from src.services.interview.interview_trace_builder import InterviewTraceBuilder


@pytest.fixture(autouse=True)
def reset_all():
    reset_interview_memory_service()
    reset_interview_observability()
    yield
    reset_interview_memory_service()
    reset_interview_observability()


class TestRegressionBenchmarks:

    def test_rubric_service_instantiation_latency(self):
        start = time.monotonic()
        for _ in range(100):
            svc = InterviewRubricService()
            svc.get_technical_rubric()
            svc.get_coding_rubric()
            svc.get_system_design_rubric()
            svc.get_ai_engineering_rubric()
            svc.get_behavioral_rubric()
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"Rubric instantiation too slow: {elapsed:.3f}s"

    def test_memory_service_crud_latency(self):
        start = time.monotonic()
        for i in range(100):
            from src.services.interview.interview_memory_service import InterviewMemoryService
            mem = InterviewMemoryService()
            mem.create_session(f"s{i}", "technical")
            mem.add_question(f"s{i}", {"question": f"Q{i}", "score": 70,
                                        "difficulty_level": "intermediate",
                                        "interview_type": "technical"})
            mem.close_session(f"s{i}")
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"Memory CRUD too slow: {elapsed:.3f}s"

    def test_governance_rejects_unsupported_critique(self):
        gov = InterviewGovernance()
        evaluation = {"weaknesses": ["weak_a", "weak_b"], "citations": [],
                      "dimension_scores": {}}
        result = gov.validate_evaluation(evaluation, [], "some context")
        assert not result["valid"]
        assert result["violations_detected"] > 0

    def test_governance_passes_valid_evaluation(self):
        gov = InterviewGovernance()
        evaluation = {"weaknesses": ["needs improvement"],
                      "citations": [{"dimension": "x", "passage": "needs improvement evidence"}],
                      "dimension_scores": {"x": {"score": 50}},
                      "confidence": {"overall": 0.8}}
        result = gov.validate_evaluation(evaluation, [], "needs improvement candidate evidence")
        assert result["valid"]

    def test_confidence_engine_produces_realistic_scores(self):
        engine = InterviewConfidenceEngine()
        for score in [0, 30, 50, 70, 90, 100]:
            result = engine.calibrate({"score": score, "difficulty_level": "intermediate"})
            assert 0.0 <= result["overall"] <= 1.0

    def test_difficulty_adaptation_never_overshoots(self):
        svc = AdaptiveDifficultyService()
        result = svc.adapt("staff", [{"score": 99}, {"score": 98}])
        assert result["level"] == "staff"
        assert not result["changed"]

    def test_difficulty_adaptation_never_undershoots(self):
        svc = AdaptiveDifficultyService()
        result = svc.adapt("beginner", [{"score": 1}, {"score": 2}])
        assert result["level"] == "beginner"
        assert not result["changed"]

    def test_weakness_detection_single_occurrence_ignored(self):
        svc = WeaknessPatternService()
        result = svc.detect_patterns([
            {"weaknesses_detected": {"single": 1}}
        ], [])
        assert result["total_patterns_detected"] == 0

    def test_weakness_detection_multiple_occurrences_detected(self):
        svc = WeaknessPatternService()
        result = svc.detect_patterns([
            {"weaknesses_detected": {"architecture_gap": 3}},
            {"weaknesses_detected": {"architecture_gap": 2}},
        ], [])
        classified = result["pattern_classification"]
        assert len(classified["architecture_gaps"]) > 0

    def test_trace_builder_produces_complete_explainability(self):
        builder = InterviewTraceBuilder()
        evaluation = {
            "overall_score": 72.0,
            "interview_type": "system_design",
            "difficulty": "senior",
            "dimension_scores": {
                "scalability_reasoning": {"score": 75, "weight": 1.5},
                "architecture_decomposition": {"score": 68, "weight": 1.5},
            },
            "citations": [{"dimension": "scalability_reasoning", "passage": "discussed sharding"}],
            "confidence": {"overall": 0.72},
            "weaknesses": ["deployment_reasoning", "governance_reasoning"],
            "evidence_sufficient": True,
        }
        difficulty = {"level": "senior", "changed": False, "reason": "stable"}
        claude_raw = {}

        trace = builder.build_trace("reg_session", 5, evaluation, difficulty, claude_raw)
        assert trace["session_id"] == "reg_session"
        assert trace["question_index"] == 5
        assert trace["evaluation"]["overall_score"] == 72.0
        assert trace["evaluation"]["interview_type"] == "system_design"
        assert trace["evaluation"]["difficulty"] == "senior"
        assert len(trace["rubric_references"]) == 2
        assert len(trace["evidence_citations"]) == 1
        assert trace["confidence"]["overall"] == 0.72
        assert len(trace["weakness_rationale"]) == 2
        assert trace["difficulty_rationale"]["reason"] == "stable"
        assert trace["adaptation_rationale"] == "stable"
        assert "governance_flags" in trace

    def test_all_difficulty_levels_mapped_correctly(self):
        svc = AdaptiveDifficultyService()
        levels = ["beginner", "intermediate", "advanced", "senior", "staff"]
        for level in levels:
            result = svc.adapt(level, [])
            assert result["level"] == level

    def test_rubric_weighted_scoring_math(self):
        svc = InterviewRubricService()
        rubrics = svc.get_technical_rubric()
        scores = {d.name: 50.0 for d in rubrics}
        result = svc.compute_weighted_score(rubrics, scores)
        assert result["overall_score"] == pytest.approx(50.0, 0.5)

    def test_confidence_penalty_reduces_overall(self):
        engine = InterviewConfidenceEngine()
        clean = engine.calibrate({"score": 80, "difficulty_level": "advanced"})
        penalized = engine.calibrate(
            {"score": 80, "difficulty_level": "advanced"},
            contradictions={"contradictions_detected": True, "severity": "critical"},
        )
        assert penalized["overall"] < clean["overall"]

    @pytest.mark.integration
    @pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "true",
        reason="Requires network access for model loading in CI",
    )
    @pytest.mark.asyncio
    async def test_full_interview_pipeline_regression(self):
        """Integration test: full interview lifecycle with all components."""
        from unittest.mock import patch

        orch = InterviewOrchestrator()

        with patch.object(orch, "_extract_question", return_value={
            "question": "What is the CAP theorem?", "question_id": "q1",
        }):
            init = await orch.initialize_session("technical", resume_text="Python engineer, 5 years")
            assert init is not None

            q1 = await orch.generate_next_question(init["session_id"])
            assert "CAP" in q1["question"]

        with patch.object(orch, "_run_claude_evaluation", return_value={
            "technical_depth": 75, "problem_solving": 70,
            "architecture_reasoning": 65, "tradeoff_awareness": 60,
            "production_realism": 55, "communication_clarity": 80,
            "citations": [{"dimension": "technical_depth", "passage": "evidence"}],
        }):
            eval_result = await orch.evaluate_answer(init["session_id"], "Q1", "Good answer")
            assert "evaluation" in eval_result
            assert "governance" in eval_result
            assert "trace" in eval_result

        close_result = await orch.close_session(init["session_id"])
        assert "session_summary" in close_result
        assert close_result["session_summary"]["questions_asked"] > 0
