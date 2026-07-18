"""
Tests for streaming readiness and coding governance boundaries.

Phase 4D Hardening: Boundary interface validation.
"""
import pytest
from src.services.interview.streaming_readiness import (
    StreamingOrchestrator,
    StreamEvent,
    StreamEventType,
    StreamToken,
    PartialCritique,
    EvaluationProgress,
)
from src.services.interview.coding_interview_governance import (
    CodingGovernance,
    SandboxConfig,
    SandboxPolicy,
    ExecutionTrace,
    ExecutionResult,
    ComplexityAnalysis,
)


class TestStreamingReadiness:
    @pytest.fixture
    def orchestrator(self):
        return StreamingOrchestrator()

    def test_buffer_token(self, orchestrator):
        token = StreamToken(text="Hello", index=0)
        orchestrator.buffer_token(token)
        assert len(orchestrator._token_buffer) == 1

    def test_buffer_critique(self, orchestrator):
        critique = PartialCritique(dimension="technical_depth", score_so_far=70.0)
        orchestrator.buffer_critique(critique)
        assert len(orchestrator._critique_buffer) == 1

    def test_flush_buffer(self, orchestrator):
        orchestrator.buffer_token(StreamToken(text="a"))
        orchestrator.buffer_token(StreamToken(text="b"))
        tokens = orchestrator.flush_buffer()
        assert len(tokens) == 2
        assert len(orchestrator._token_buffer) == 0

    def test_streaming_not_yet_capable(self, orchestrator):
        assert orchestrator.streaming_capable is False

    def test_register_listener(self, orchestrator):
        received = []
        orchestrator.register_listener(StreamEventType.TOKEN, lambda e: received.append(e))
        assert StreamEventType.TOKEN.value in orchestrator._listeners
        assert len(orchestrator._listeners[StreamEventType.TOKEN.value]) == 1

    def test_stream_event_types(self):
        types = list(StreamEventType)
        assert StreamEventType.TOKEN in types
        assert StreamEventType.PARTIAL_CRITIQUE in types
        assert StreamEventType.EVALUATION_PROGRESS in types
        assert StreamEventType.DIFFICULTY_UPDATE in types
        assert StreamEventType.INTERRUPTION in types
        assert StreamEventType.COMPLETE in types
        assert StreamEventType.ERROR in types

    def test_evaluation_progress_defaults(self):
        progress = EvaluationProgress()
        assert progress.dimensions_evaluated == 0
        assert progress.total_dimensions == 0
        assert progress.current_dimension == ""


class TestCodingGovernance:
    @pytest.fixture
    def gov(self):
        return CodingGovernance()

    def test_sandbox_disabled_by_default(self, gov):
        assert gov.sandbox_enabled is False

    def test_validate_submission_returns_not_implemented(self, gov):
        result = gov.validate_submission("print('hello')", "python")
        assert result["valid"] is False
        assert result["reason"] == "sandbox_not_implemented"

    def test_analyze_complexity_returns_unknown(self, gov):
        analysis = gov.analyze_complexity("def f(): pass")
        assert analysis.time_complexity == "unknown"
        assert analysis.space_complexity == "unknown"

    def test_detect_malicious_patterns_returns_empty(self, gov):
        patterns = gov.detect_malicious_patterns("import os; os.system('rm -rf /')")
        assert patterns == []

    def test_simulate_execution_returns_error(self, gov):
        trace = gov.simulate_execution("code", [1, 2])
        assert trace.result == ExecutionResult.RUNTIME_ERROR
        assert "sandbox not available" in trace.stderr

    def test_sandbox_config_defaults(self):
        config = SandboxConfig()
        assert config.language == "python"
        assert config.timeout_seconds == 5.0
        assert config.max_memory_mb == 256
        assert SandboxPolicy.STRICT in config.policies
        assert config.enabled is False

    def test_execution_result_values(self):
        results = list(ExecutionResult)
        assert ExecutionResult.SUCCESS in results
        assert ExecutionResult.TIMEOUT in results
        assert ExecutionResult.SECURITY_VIOLATION in results
