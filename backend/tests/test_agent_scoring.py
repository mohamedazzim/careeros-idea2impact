"""Tests for Scoring, Prioritization, and Urgency agents."""

import pytest
import asyncio
from src.agents.opportunity_scoring_agent import OpportunityScoringAgent, get_opportunity_scoring_agent, ScoringState
from src.agents.opportunity_prioritization_agent import OpportunityPrioritizationAgent, get_opportunity_prioritization_agent
from src.agents.deadline_urgency_agent import DeadlineUrgencyAgent, get_deadline_urgency_agent
from src.agents.notification_decision_agent import NotificationDecisionAgent, get_notification_decision_agent


class TestOpportunityScoringAgent:
    @pytest.fixture
    def mock_claude_service(self, monkeypatch):
        import json
        class MockClaudeService:
            async def reason_text(self, *args, **kwargs):
                return {
                    "result": json.dumps({
                        dim: {"score": 85, "confidence": 0.95, "citations": ["mocked evidence"]}
                        for dim in [
                            "seniority_fit", "compensation_relevance", "role_alignment",
                            "domain_alignment", "application_urgency", "market_demand"
                        ]
                    })
                }
        from src.services.intelligence import claude_service
        monkeypatch.setattr(claude_service, "get_claude_service", lambda: MockClaudeService())

    @pytest.fixture
    def agent(self):
        return OpportunityScoringAgent()

    def test_score_basic(self, agent, mock_claude_service):
        opp = {"id": "o1", "title": "Senior AI Engineer", "company": "Anthropic",
               "skills": ["python", "pytorch", "langchain"]}
        cand = {"skills": ["python", "pytorch", "docker"]}
        state = asyncio.run(agent.score("u1", opp, cand))
        assert state.status == "completed"
        assert state.overall_score > 0

    def test_score_all_dimensions(self, agent, mock_claude_service):
        opp = {"id": "o1", "title": "Junior Dev", "company": "Acme", "skills": ["javascript"]}
        cand = {"skills": ["javascript", "react"]}
        state = asyncio.run(agent.score("u1", opp, cand))
        for dim in agent.ALL_DIMENSIONS:
            assert dim in state.dimension_scores, f"Missing dimension: {dim}"

    def test_score_returns_confidence(self, agent, mock_claude_service):
        opp = {"id": "o1", "title": "Engineer"}
        cand = {"skills": ["python"]}
        state = asyncio.run(agent.score("u1", opp, cand))
        assert 0.0 <= state.confidence <= 1.0

    def test_score_empty_opportunity(self, agent, mock_claude_service):
        opp = {"id": "o1", "title": "Role"}
        cand = {}
        state = asyncio.run(agent.score("u1", opp, cand))
        assert state.overall_score >= 0

    def test_scoring_state_dataclass(self):
        state = ScoringState(scoring_run_id="r1", user_id="u1", opportunity_id="o1")
        assert state.status == "active"
        assert state.confidence == 0.5
        assert state.overall_score == 0.0

    def test_singleton(self):
        a = get_opportunity_scoring_agent()
        b = get_opportunity_scoring_agent()
        assert a is b


class TestPrioritizationAgent:
    @pytest.fixture
    def agent(self):
        return OpportunityPrioritizationAgent()

    def test_prioritize_ranks(self, agent):
        opps = [
            {"opportunity_id": "a", "overall_score": 90, "urgency_score": 0.9, "confidence": 0.9},
            {"opportunity_id": "b", "overall_score": 50, "urgency_score": 0.3, "confidence": 0.5},
        ]
        state = asyncio.run(agent.prioritize("u1", opps))
        assert state.status == "completed"
        assert state.ranked_opportunities[0]["opportunity_id"] == "a"
        assert state.ranked_opportunities[0]["priority_rank"] == 1

    def test_prioritize_empty(self, agent):
        state = asyncio.run(agent.prioritize("u1", []))
        assert state.status == "completed"
        assert state.ranked_opportunities == []

    def test_singleton(self):
        a = get_opportunity_prioritization_agent()
        b = get_opportunity_prioritization_agent()
        assert a is b


class TestDeadlineUrgencyAgent:
    @pytest.fixture
    def agent(self):
        return DeadlineUrgencyAgent()

    def test_evaluate_no_deadline(self, agent):
        opps = [{"id": "o1", "title": "Job"}]
        state = asyncio.run(agent.evaluate("u1", opps))
        assert state.status == "completed"
        assert state.urgency_scores.get("o1", 1.0) < 0.3

    def test_evaluate_with_deadlines(self, agent):
        from datetime import datetime, timedelta
        tomorrow = (datetime.utcnow() + timedelta(days=1)).isoformat()
        opps = [{"id": "o1", "title": "Urgent Job", "deadline": tomorrow, "application_urgency": 50}]
        state = asyncio.run(agent.evaluate("u1", opps))
        assert state.urgency_scores["o1"] > 0.4

    def test_compute_urgency_past_deadline(self, agent):
        from datetime import datetime, timedelta
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        opp = {"deadline": yesterday, "title": "Late"}
        urgency = agent._compute_urgency(opp)
        assert urgency > 0.5

    def test_singleton(self):
        a = get_deadline_urgency_agent()
        b = get_deadline_urgency_agent()
        assert a is b


class TestNotificationDecisionAgent:
    @pytest.fixture
    def agent(self):
        return NotificationDecisionAgent()

    def test_decide_not_notify_low_fit(self, agent):
        opp = {"id": "o1", "title": "Role"}
        score = {"overall_score": 30, "confidence": 0.5}
        decision = asyncio.run(agent.decide("u1", opp, score, urgency=0.3, governance_passed=True))
        assert decision.should_notify is False
        assert decision.suppression_reason is not None

    def test_decide_not_notify_low_confidence(self, agent):
        opp = {"id": "o1", "title": "Role"}
        score = {"overall_score": 90, "confidence": 0.4}
        decision = asyncio.run(agent.decide("u1", opp, score, urgency=0.9, governance_passed=True))
        assert decision.should_notify is False

    def test_decide_not_notify_governance_blocked(self, agent):
        opp = {"id": "o1", "title": "Role"}
        score = {"overall_score": 90, "confidence": 0.9}
        decision = asyncio.run(agent.decide("u1", opp, score, urgency=0.9, governance_passed=False))
        assert decision.should_notify is False
        assert "governance_blocked" in (decision.suppression_reason or "")

    def test_decide_should_notify(self, agent):
        opp = {"id": "o1", "title": "Senior Engineer", "company": "Acme"}
        score = {"overall_score": 85, "confidence": 0.85}
        decision = asyncio.run(agent.decide("u1", opp, score, urgency=0.8, governance_passed=True))
        assert decision.should_notify is True
        assert len(decision.notification_message) > 10

    def test_singleton(self):
        a = get_notification_decision_agent()
        b = get_notification_decision_agent()
        assert a is b
