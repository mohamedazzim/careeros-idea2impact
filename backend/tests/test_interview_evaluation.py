"""
Tests for interview evaluation service — multi-rubric scoring engine.

Phase 4D: Evaluation scoring validation.
"""
import pytest
from unittest.mock import AsyncMock, patch
from src.services.interview.interview_evaluation_service import InterviewEvaluationService


@pytest.fixture
def svc():
    return InterviewEvaluationService()


class TestInterviewEvaluation:
    @pytest.mark.asyncio
    async def test_evaluate_technical(self, svc):
        claude_eval = {
            "technical_depth": 75,
            "problem_solving": 70,
            "architecture_reasoning": 65,
            "tradeoff_awareness": 60,
            "production_realism": 55,
            "communication_clarity": 80,
            "citations": [{"dimension": "technical_depth", "passage": "evidence"}],
            "claims": [{"evidence_citations": ["cite1"]}],
            "strengths": ["Strong fundamentals"],
            "weaknesses": ["Needs production experience"],
            "improvements": ["Study deployment patterns"],
        }
        result = await svc.evaluate(
            "technical", "Q?", "Answer text", "intermediate", claude_eval
        )
        assert "overall_score" in result
        assert "dimension_scores" in result
        assert "confidence" in result
        assert "strengths" in result
        assert "weaknesses" in result
        assert result["interview_type"] == "technical"
        assert result["difficulty"] == "intermediate"

    @pytest.mark.asyncio
    async def test_evaluate_coding(self, svc):
        claude_eval = {
            "algorithmic_thinking": 85,
            "code_quality": 80,
            "edge_case_handling": 70,
            "testing_approach": 65,
            "optimization_reasoning": 60,
            "language_proficiency": 90,
            "citations": [],
            "claims": [],
        }
        result = await svc.evaluate(
            "coding", "reverse linked list?", "def reverse...", "intermediate", claude_eval
        )
        assert result["interview_type"] == "coding"

    @pytest.mark.asyncio
    async def test_evaluate_system_design(self, svc):
        claude_eval = {
            "scalability_reasoning": 75,
            "architecture_decomposition": 70,
            "fault_tolerance": 65,
            "observability_reasoning": 60,
            "async_orchestration": 55,
            "governance_reasoning": 50,
            "deployment_reasoning": 65,
            "tradeoff_reasoning": 70,
            "citations": [],
            "claims": [],
        }
        result = await svc.evaluate(
            "system_design", "Design Twitter?", "My design...", "senior", claude_eval
        )
        assert result["interview_type"] == "system_design"

    @pytest.mark.asyncio
    async def test_evaluate_ai_engineering(self, svc):
        claude_eval = {
            "rag_understanding": 80,
            "vector_db_reasoning": 75,
            "orchestration_reasoning": 70,
            "governance_understanding": 65,
            "mcp_understanding": 60,
            "langgraph_understanding": 55,
            "inference_optimization": 50,
            "production_ai": 45,
            "citations": [],
            "claims": [],
        }
        result = await svc.evaluate(
            "ai_engineering", "Explain RAG?", "RAG is...", "advanced", claude_eval
        )
        assert result["interview_type"] == "ai_engineering"

    @pytest.mark.asyncio
    async def test_evaluate_behavioral(self, svc):
        claude_eval = {
            "leadership_signals": 70,
            "conflict_resolution": 65,
            "collaboration_patterns": 75,
            "growth_mindset": 80,
            "impact_communication": 60,
            "stakeholder_management": 55,
            "failure_response": 70,
            "citations": [],
            "claims": [],
        }
        result = await svc.evaluate(
            "behavioral", "Tell me about a conflict?", "I handled...", "intermediate", claude_eval
        )
        assert result["interview_type"] == "behavioral"

    @pytest.mark.asyncio
    async def test_evaluate_unknown_type_falls_back(self, svc):
        claude_eval = {"technical_depth": 50, "citations": [], "claims": []}
        result = await svc.evaluate(
            "unknown_type", "Q", "A", "beginner", claude_eval
        )
        assert "overall_score" in result

    @pytest.mark.asyncio
    async def test_evaluate_with_contradictions(self, svc):
        claude_eval = {"technical_depth": 60, "citations": [], "claims": []}
        contradictions = {"contradictions_detected": True, "severity": "medium"}
        result = await svc.evaluate(
            "technical", "Q", "A", "intermediate", claude_eval,
            contradictions=contradictions,
        )
        assert "confidence" in result
        assert result["confidence"]["contradiction_penalty"] > 0

    @pytest.mark.asyncio
    async def test_evaluate_with_answer_history(self, svc):
        claude_eval = {"technical_depth": 75, "citations": [], "claims": []}
        history = [{"confidence": 0.8}, {"confidence": 0.75}]
        result = await svc.evaluate(
            "technical", "Q", "A", "intermediate", claude_eval,
            answer_history=history,
        )
        assert "confidence" in result
        assert result["confidence"]["consistency_score"] > 0.7

    @pytest.mark.asyncio
    async def test_evaluation_contains_question_and_answer(self, svc):
        claude_eval = {"technical_depth": 70, "citations": [], "claims": []}
        result = await svc.evaluate(
            "technical", "What is CAP?", "CAP means...", "intermediate", claude_eval
        )
        assert result["question"] == "What is CAP?"
        assert result["answer_summary"] == "CAP means..."

    @pytest.mark.asyncio
    async def test_evaluation_evidence_sufficient_flag(self, svc):
        claude_eval = {
            "technical_depth": 70, "problem_solving": 65,
            "architecture_reasoning": 60, "tradeoff_awareness": 55,
            "production_realism": 50, "communication_clarity": 75,
            "citations": [
                {"dimension": "technical_depth", "passage": "ev"},
                {"dimension": "technical_depth", "passage": "ev2"},
                {"dimension": "problem_solving", "passage": "ev3"},
            ],
            "claims": [],
        }
        result = await svc.evaluate(
            "technical", "Q", "A", "intermediate", claude_eval
        )
        assert "evidence_sufficient" in result
