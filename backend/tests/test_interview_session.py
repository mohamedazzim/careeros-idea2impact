"""
Tests for interview session orchestration — full interview lifecycle.
Phase 4D: Session state and progression tests.
"""
import pytest
from unittest.mock import AsyncMock, patch

from src.services.interview.interview_orchestrator import InterviewOrchestrator
from src.services.interview.interview_memory_service import reset_interview_memory_service


@pytest.fixture(autouse=True)
def reset_memory():
    reset_interview_memory_service()
    yield
    reset_interview_memory_service()


@pytest.fixture
def orch():
    return InterviewOrchestrator()


class TestSessionOrchestration:
    @pytest.mark.asyncio
    async def test_initialize_technical_session(self, orch):
        result = await orch.initialize_session(
            "technical",
            resume_text="Python backend engineer, 5 years",
            ats_data={"overall_score": 75},
            ai_readiness={"overall_score": 60},
        )
        assert "session_id" in result
        assert result["interview_type"] == "technical"
        assert result["question_count"] == 0
        assert result["difficulty_level"] in ["beginner", "intermediate", "advanced", "senior", "staff"]

    @pytest.mark.asyncio
    async def test_initialize_invalid_type(self, orch):
        result = await orch.initialize_session("invalid_type")
        assert "error" in result
        assert "valid_types" in result

    @pytest.mark.asyncio
    async def test_initialize_with_metadata(self, orch):
        result = await orch.initialize_session(
            "behavioral",
            metadata={"candidate_id": "c42"},
        )
        assert result["session_metadata"]["candidate_id"] == "c42"

    @pytest.mark.asyncio
    async def test_generate_question_nonexistent_session(self, orch):
        result = await orch.generate_next_question("nonexistent")
        assert "error" in result

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_generate_technical_question(self, orch):
        init = await orch.initialize_session("technical", resume_text="Python engineer")
        with patch.object(
            orch, "_extract_question",
            return_value={"question": "What is CAP theorem?", "question_id": "q1"},
        ):
            result = await orch.generate_next_question(init["session_id"])
            assert result["question"] == "What is CAP theorem?"
            assert result["difficulty"] in ["beginner", "intermediate", "advanced", "senior", "staff"]

    @pytest.mark.asyncio
    async def test_generate_question_tracks_index(self, orch):
        init = await orch.initialize_session("technical", resume_text="Engineer")
        with patch.object(orch, "_extract_question", return_value={"question": "Q1", "question_id": "q1"}):
            r1 = await orch.generate_next_question(init["session_id"])
            assert r1["question_index"] == 1
        with patch.object(orch, "_extract_question", return_value={"question": "Q2", "question_id": "q2"}):
            r2 = await orch.generate_next_question(init["session_id"])
            assert r2["question_index"] == 2

    @pytest.mark.asyncio
    async def test_evaluate_answer_nonexistent_session(self, orch):
        result = await orch.evaluate_answer("nonexistent", "Q", "A")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_evaluate_answer_flow(self, orch):
        init = await orch.initialize_session("technical", resume_text="Engineer")
        with patch.object(orch, "_extract_question", return_value={"question": "Q1", "question_id": "q1"}):
            await orch.generate_next_question(init["session_id"])

        with patch.object(
            orch, "_run_claude_evaluation",
            return_value={"technical_depth": 70, "citations": []},
        ):
            result = await orch.evaluate_answer(init["session_id"], "Q1", "My answer")
            assert "evaluation" in result
            assert "governance" in result
            assert "feedback" in result
            assert "difficulty_decision" in result
            assert "trace" in result

    @pytest.mark.asyncio
    async def test_close_session(self, orch):
        init = await orch.initialize_session("technical", resume_text="Engineer")
        with patch.object(orch, "_extract_question", return_value={"question": "Q1", "question_id": "q1"}):
            await orch.generate_next_question(init["session_id"])

        result = await orch.close_session(init["session_id"])
        assert "session_summary" in result
        assert "weakness_patterns" in result
        assert "session_trace" in result

    @pytest.mark.asyncio
    async def test_close_nonexistent_session(self, orch):
        result = await orch.close_session("nonexistent")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_full_interview_lifecycle(self, orch):
        init = await orch.initialize_session("technical", resume_text="SWE with 5 years Python")

        with patch.object(orch, "_extract_question", return_value={"question": "Q1", "question_id": "q1"}):
            q1 = await orch.generate_next_question(init["session_id"])

        with patch.object(orch, "_run_claude_evaluation", return_value={"technical_depth": 75}):
            eval1 = await orch.evaluate_answer(init["session_id"], "Q1", "Good answer")

        close = await orch.close_session(init["session_id"])
        assert "session_summary" in close
        assert close["session_summary"]["questions_asked"] > 0
