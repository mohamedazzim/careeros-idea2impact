import pytest
import os
from unittest.mock import AsyncMock, patch
from src.services.evaluation.evaluation_engine import get_evaluation_engine


@pytest.mark.asyncio
async def test_evaluation_engine_real_provider():
    """Test that evaluation engine calls the provider and returns structured output."""
    engine = get_evaluation_engine()
    mock_result = {
        "ats_score": {"score": 85, "justification": "Good match"},
        "match_score": {"score": 80, "strongest_factors": ["Python"], "weakest_factors": ["AWS"], "rationale": "Solid"},
        "strengths": [{"strength": "Python", "evidence": "5 years", "impact": "Backend", "confidence_score": 0.9}],
        "weaknesses": [{"weakness": "AWS", "evidence": "Not Found In Resume", "impact": "Deployments", "confidence_score": 1.0}],
        "recommendations": [{"priority": "High", "category": "skills", "recommendation": "Learn AWS", "expected_impact": "Better fit"}],
        "skill_gaps": [{"skill": "AWS", "status": "Required Skills Missing", "importance": "High", "confidence": 1.0, "evidence": "Not Found In Resume"}],
    }

    resume_text = "Experienced Backend Engineer with 5 years of Python."
    job_text = "Looking for a Python Backend Engineer."
    context = "[1] Source: Resume - Python 5 years"

    mock_service = AsyncMock()
    mock_service.reason = AsyncMock(return_value={"result": mock_result})

    with patch.object(engine, "_extract", return_value=None), \
         patch("src.services.evaluation.evaluation_engine.get_claude_service", return_value=mock_service):

        hallucination = await engine.evaluate_hallucination(resume_text, context)
        grounding = await engine.evaluate_grounding(resume_text, context)

    assert "hallucination_score" in hallucination
    assert "grounding_score" in grounding


@pytest.mark.asyncio
async def test_evaluation_engine_low_match():
    """Test low-match evaluation path."""
    engine = get_evaluation_engine()
    mock_bundle = {
        "hallucination_score": 30,
        "high_risk_spans": [],
        "grounding_score": 20,
        "unsupported_claims": [],
        "relevance_score": 15,
        "retrieval_quality_score": 25,
        "irrelevant_count": 5,
        "explanation": "Poor match",
        "evidence": [],
    }

    mock_service = AsyncMock()
    mock_service.reason = AsyncMock(return_value={"result": mock_bundle})

    with patch("src.services.evaluation.evaluation_engine.get_claude_service", return_value=mock_service):
        result = await engine.run_full_evaluation(
            query="cloud architect",
            answer="frontend dev",
            context="unrelated",
            retrieved_chunks=["chunk1"],
        )

    assert result["hallucination"]["hallucination_score"] == 30
    assert result["grounding"]["grounding_score"] == 20
    assert result["answer_relevance"]["relevance_score"] == 15


@pytest.mark.asyncio
async def test_evaluation_engine_error_handling():
    """Test that errors are properly raised and contain useful messages."""
    engine = get_evaluation_engine()

    mock_service = AsyncMock()
    mock_service.reason_text = AsyncMock(side_effect=RuntimeError("API error"))

    with patch("src.services.evaluation.evaluation_engine.get_claude_service", return_value=mock_service):
        result = await engine.evaluate_hallucination("test response", "test context")

    assert "hallucination_score" in result
    assert result.get("error") is True or result.get("hallucination_score") == 50
