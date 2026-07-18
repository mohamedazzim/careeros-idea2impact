"""
Tests for runtime safety services — caps, throttling, state validation.

Phase 4D Hardening: Runtime safety validation tests.
"""
import pytest
import time
from src.services.interview.interview_safety_service import (
    InterviewSafetyService,
    reset_interview_safety_service,
)
from src.services.interview.interview_state_validator import (
    InterviewStateValidator,
    InterviewStatus,
    StateValidationResult,
    reset_interview_state_validator,
)
from src.services.interview.interview_concurrency_service import (
    InterviewConcurrencyService,
    TokenBudget,
    reset_interview_concurrency_service,
)


@pytest.fixture(autouse=True)
def reset_all():
    reset_interview_safety_service()
    reset_interview_state_validator()
    reset_interview_concurrency_service()
    yield
    reset_interview_safety_service()
    reset_interview_state_validator()
    reset_interview_concurrency_service()


class TestInterviewSafety:
    @pytest.fixture
    def safety(self):
        return InterviewSafetyService()

    def test_session_cap_allowed(self, safety):
        import asyncio
        result = asyncio.run(safety.check_session_cap(10))
        assert result["allowed"] is True
        assert "utilization" in result

    def test_session_cap_high_pressure(self, safety):
        import asyncio
        result = asyncio.run(safety.check_session_cap(45))
        assert result["allowed"] is True
        assert "warning" in result or "utilization" in result

    def test_session_cap_reached(self, safety):
        import asyncio
        safety.session_cap = 3
        result = asyncio.run(safety.check_session_cap(3))
        assert result["allowed"] is False
        assert result["degraded"] is True

    def test_question_cap_allowed(self, safety):
        result = safety.check_question_cap(5)
        assert result["allowed"] is True
        assert result["remaining"] > 0

    def test_question_cap_reached(self, safety):
        safety.question_cap = 5
        result = safety.check_question_cap(5)
        assert result["allowed"] is False

    def test_question_cap_nearing(self, safety):
        safety.question_cap = 20
        result = safety.check_question_cap(19)
        assert result["allowed"] is True
        assert "warning" in result

    def test_escalation_cap_allowed(self, safety):
        result = safety.check_escalation_cap([
            {"from": "beginner", "to": "intermediate"},
        ])
        assert result["allowed"] is True

    def test_escalation_cap_reached(self, safety):
        safety.escalation_cap = 2
        result = safety.check_escalation_cap([
            {"from": "beginner", "to": "intermediate"},
            {"from": "intermediate", "to": "advanced"},
        ])
        assert result["allowed"] is False

    def test_token_budget_allowed(self, safety):
        result = safety.check_token_budget(50000)
        assert result["allowed"] is True

    def test_token_budget_exhausted(self, safety):
        safety.token_budget = 1000
        result = safety.check_token_budget(1000)
        assert result["allowed"] is False
        assert result["degraded"] is True

    def test_token_budget_critical(self, safety):
        safety.token_budget = 1000
        result = safety.check_token_budget(950)
        assert result["degraded"] is True
        assert result["severity"] == "critical"

    def test_forced_degradation_normal(self, safety):
        result = safety.forced_degradation_mode(0.3)
        assert result["mode"] == "normal"

    def test_forced_degradation_reduced(self, safety):
        result = safety.forced_degradation_mode(0.8)
        assert result["mode"] == "reduced"

    def test_forced_degradation_critical(self, safety):
        result = safety.forced_degradation_mode(0.95)
        assert result["mode"] == "critical"
        assert result["skip_feedback"] is True


class TestStateValidator:
    @pytest.fixture
    def validator(self):
        return InterviewStateValidator()

    def test_valid_transition_init_to_active(self, validator):
        result = validator.validate_transition("init", "active")
        assert result.valid is True

    def test_valid_transition_active_to_evaluating(self, validator):
        result = validator.validate_transition("active", "evaluating")
        assert result.valid is True

    def test_invalid_transition_closed_to_active(self, validator):
        result = validator.validate_transition("closed", "active")
        assert result.valid is False

    def test_invalid_transition_completed_to_evaluating(self, validator):
        result = validator.validate_transition("completed", "evaluating")
        assert result.valid is False

    def test_invalid_unknown_status(self, validator):
        result = validator.validate_transition("nonexistent", "active")
        assert result.valid is False

    def test_question_progression_valid(self, validator):
        result = validator.validate_question_progression(3, 10)
        assert result.valid is True

    def test_question_progression_negative(self, validator):
        result = validator.validate_question_progression(-1, 10)
        assert result.valid is False

    def test_question_progression_exceeds_max(self, validator):
        result = validator.validate_question_progression(5, 4)
        assert result.valid is False

    def test_question_progression_cap_hit(self, validator):
        result = validator.validate_question_progression(5, 5, new_question=True)
        assert result.valid is False

    def test_evaluation_not_duplicate(self, validator):
        questions = [{"question": "What is CAP?", "score": 0}]
        result = validator.validate_evaluation_not_duplicate(questions, "Different question?")
        assert result.valid is True

    def test_evaluation_duplicate_scored(self, validator):
        questions = [{"question": "What is CAP?", "score": 75, "weaknesses": ["depth"]}]
        result = validator.validate_evaluation_not_duplicate(questions, "What is CAP?")
        assert result.valid is False

    def test_session_active_valid(self, validator):
        result = validator.validate_session_active("active")
        assert result.valid is True

    def test_session_closed_invalid(self, validator):
        result = validator.validate_session_active("closed")
        assert result.valid is False

    def test_adaptation_limit_allowed(self, validator):
        result = validator.validate_adaptation_limit([
            {"from": "beginner", "to": "intermediate"},
        ], 2)
        assert result.valid is True

    def test_adaptation_limit_reached(self, validator):
        result = validator.validate_adaptation_limit([
            {"from": "beginner", "to": "intermediate"},
            {"from": "intermediate", "to": "advanced"},
        ], 2)
        assert result.valid is False

    def test_session_not_orphaned(self, validator):
        result = validator.validate_session_not_orphaned(time.time(), 3600)
        assert result.valid is True

    def test_session_orphaned(self, validator):
        result = validator.validate_session_not_orphaned(time.time() - 4000, 3600)
        assert result.valid is False


class TestTokenBudget:
    def test_initial_budget(self):
        budget = TokenBudget(10000)
        assert budget.max_tokens == 10000
        assert budget.used == 0

    def test_consume_within_budget(self):
        budget = TokenBudget(10000)
        assert budget.consume(5000) is True
        assert budget.used == 5000
        assert budget.remaining() == 5000
        assert budget.utilization() == 0.5

    def test_consume_exceeds_budget(self):
        budget = TokenBudget(100)
        assert budget.consume(150) is False
        assert budget.used == 0

    def test_can_consume(self):
        budget = TokenBudget(1000)
        assert budget.can_consume(500) is True
        assert budget.can_consume(600) is True
        budget.consume(800)
        assert budget.can_consume(300) is False

    def test_reset(self):
        budget = TokenBudget(1000)
        budget.consume(800)
        budget.reset()
        assert budget.used == 0
        assert budget.utilization() == 0.0


class TestConcurrencyService:
    @pytest.fixture
    def concurrency(self):
        return InterviewConcurrencyService()

    def test_initial_state(self, concurrency):
        assert concurrency.token_budget.used == 0
        assert concurrency.token_utilization() == 0.0

    def test_check_token_budget(self, concurrency):
        assert concurrency.check_token_budget(50000) is True

    def test_consume_tokens(self, concurrency):
        assert concurrency.consume_tokens(100000) is True
        assert concurrency.token_utilization() > 0.0

    def test_throttle_no_throttle(self, concurrency):
        assert concurrency.throttle_if_needed() is None

    def test_throttle_high_utilization(self, concurrency):
        concurrency.token_budget.used = concurrency.token_budget.max_tokens - 100
        result = concurrency.throttle_if_needed()
        assert result is not None

    def test_reset_budget(self, concurrency):
        concurrency.consume_tokens(100000)
        concurrency.reset_budget()
        assert concurrency.token_utilization() == 0.0

    def test_active_operations(self, concurrency):
        import asyncio
        ops = asyncio.run(concurrency.active_operations())
        assert "evaluation_queue" in ops
        assert "question_queue" in ops
        assert "feedback_queue" in ops
