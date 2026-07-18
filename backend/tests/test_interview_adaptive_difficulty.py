"""
Tests for adaptive difficulty engine — real-time difficulty adaptation.

Phase 4D: Adaptive difficulty progression validation.
"""
import pytest
from src.services.interview.adaptive_difficulty_service import (
    AdaptiveDifficultyService,
    DIFFICULTY_LEVELS,
    LEVEL_INDICES,
)


@pytest.fixture
def svc():
    return AdaptiveDifficultyService()


class TestAdaptiveDifficulty:
    def test_difficulty_levels_ordered(self, svc):
        assert DIFFICULTY_LEVELS == ["beginner", "intermediate", "advanced", "senior", "staff"]
        assert LEVEL_INDICES["beginner"] == 0
        assert LEVEL_INDICES["intermediate"] == 1
        assert LEVEL_INDICES["advanced"] == 2
        assert LEVEL_INDICES["senior"] == 3
        assert LEVEL_INDICES["staff"] == 4

    def test_compute_initial_default(self, svc):
        result = svc.compute_initial_level()
        assert result == "intermediate"

    def test_compute_initial_from_ats_beginner(self, svc):
        result = svc.compute_initial_level(ats_data={"overall_score": 30})
        assert result == "beginner"

    def test_compute_initial_from_ats_intermediate(self, svc):
        result = svc.compute_initial_level(ats_data={"overall_score": 50})
        assert result == "intermediate"

    def test_compute_initial_from_ats_advanced(self, svc):
        result = svc.compute_initial_level(ats_data={"overall_score": 65})
        assert result == "advanced"

    def test_compute_initial_from_ats_senior(self, svc):
        result = svc.compute_initial_level(ats_data={"overall_score": 78})
        assert result == "senior"

    def test_compute_initial_from_ats_staff(self, svc):
        result = svc.compute_initial_level(ats_data={"overall_score": 92})
        assert result == "staff"

    def test_compute_initial_from_ai_readiness(self, svc):
        result = svc.compute_initial_level(
            ai_readiness={"overall_score": 85}
        )
        assert result == "senior"

    def test_compute_initial_from_architecture_maturity(self, svc):
        result = svc.compute_initial_level(
            architecture_maturity={"overall_score": 80}
        )
        assert result == "senior"

    def test_compute_initial_multiple_signals_averaged(self, svc):
        result = svc.compute_initial_level(
            ats_data={"overall_score": 55},
            ai_readiness={"overall_score": 65},
            architecture_maturity={"overall_score": 60},
        )
        assert result in DIFFICULTY_LEVELS

    def test_adapt_no_history(self, svc):
        result = svc.adapt("intermediate", [])
        assert result["level"] == "intermediate"
        assert result["changed"] is False
        assert result["reason"] == "no_history"

    def test_adapt_insufficient_history(self, svc):
        result = svc.adapt("intermediate", [{"score": 90}])
        assert result["changed"] is False
        assert result["reason"] == "stable"

    def test_adapt_escalation(self, svc):
        result = svc.adapt("intermediate", [
            {"score": 85}, {"score": 88}
        ])
        assert result["level"] == "advanced"
        assert result["changed"] is True
        assert result["reason"] == "high_performance"

    def test_adapt_demotion(self, svc):
        result = svc.adapt("advanced", [
            {"score": 30}, {"score": 25}
        ])
        assert result["level"] == "intermediate"
        assert result["changed"] is True
        assert result["reason"] == "low_performance"

    def test_adapt_contradiction_escalation(self, svc):
        result = svc.adapt("intermediate", [
            {"score": 60, "contradiction_detected": True},
            {"score": 65, "contradiction_detected": True},
        ])
        assert result["level"] == "advanced"
        assert result["reason"] == "contradiction_pressure"

    def test_adapt_no_escalation_at_staff(self, svc):
        result = svc.adapt("staff", [
            {"score": 90}, {"score": 95}
        ])
        assert result["level"] == "staff"

    def test_adapt_stable(self, svc):
        result = svc.adapt("intermediate", [
            {"score": 60}, {"score": 65}
        ])
        assert result["changed"] is False
        assert result["reason"] == "stable"
