"""Tests for Urgency Engine, Prioritization Engine, and Market Signal Engine."""

import pytest
import time
from datetime import datetime, timedelta
from src.services.opportunity.urgency_engine import UrgencyEngine, get_urgency_engine
from src.services.opportunity.prioritization_engine import PrioritizationEngine, get_prioritization_engine
from src.services.opportunity.market_signal_engine import MarketSignalEngine, get_market_signal_engine


class TestUrgencyEngine:
    @pytest.fixture
    def engine(self):
        return UrgencyEngine()

    def test_no_deadline_low_urgency(self, engine):
        opp = {"id": "o1", "title": "Job"}
        result = engine.evaluate(opp)
        assert result["urgency_score"] < 0.3

    def test_imminent_deadline_high_urgency(self, engine):
        tomorrow = (datetime.utcnow() + timedelta(days=1)).isoformat()
        opp = {"id": "o1", "title": "Job", "deadline": tomorrow}
        result = engine.evaluate(opp)
        assert result["urgency_score"] > 0.5

    def test_near_deadline_medium_urgency(self, engine):
        in_10_days = (datetime.utcnow() + timedelta(days=10)).isoformat()
        opp = {"id": "o1", "title": "Job", "deadline": in_10_days}
        result = engine.evaluate(opp)
        assert 0.3 < result["urgency_score"] < 0.8

    def test_far_deadline_low_urgency(self, engine):
        in_60_days = (datetime.utcnow() + timedelta(days=60)).isoformat()
        opp = {"id": "o1", "title": "Job", "deadline": in_60_days}
        result = engine.evaluate(opp)
        assert result["urgency_score"] < 0.3

    def test_past_deadline_max_urgency(self, engine):
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        opp = {"id": "o1", "title": "Job", "deadline": yesterday}
        result = engine.evaluate(opp)
        assert result["urgency_score"] > 0.6

    def test_urgent_keywords_increase_score(self, engine):
        opp = {"id": "o1", "title": "Urgent Hiring", "description": "ASAP immediate hire needed"}
        result = engine.evaluate(opp)
        assert result["urgency_score"] > 0.3

    def test_urgency_returns_components(self, engine):
        opp = {"id": "o1", "title": "Job"}
        result = engine.evaluate(opp)
        assert "component_scores" in result
        assert "deadline_pressure" in result["component_scores"]
        assert "application_urgency" in result["component_scores"]
        assert "market_demand_signal" in result["component_scores"]

    def test_urgency_score_range(self, engine):
        for n in range(5):
            opp = {"id": f"o{n}", "title": "Test"}
            result = engine.evaluate(opp)
            assert 0.0 <= result["urgency_score"] <= 1.0


class TestPrioritizationEngine:
    @pytest.fixture
    def engine(self):
        return PrioritizationEngine()

    @pytest.fixture
    def scored_opps(self):
        return [
            {"opportunity_id": "a", "title": "High", "overall_score": 90, "urgency_score": 0.9, "confidence": 0.85},
            {"opportunity_id": "b", "title": "Medium", "overall_score": 70, "urgency_score": 0.6, "confidence": 0.7},
            {"opportunity_id": "c", "title": "Low", "overall_score": 40, "urgency_score": 0.2, "confidence": 0.5},
        ]

    def test_rank_assigns_priority(self, engine, scored_opps):
        ranked = engine.rank(scored_opps)
        for opp in ranked:
            assert "priority_score" in opp
            assert opp["priority_score"] > 0

    def test_rank_sorts_by_score(self, engine, scored_opps):
        ranked = engine.rank(scored_opps)
        scores = [o["priority_score"] for o in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_top_opportunity_first(self, engine, scored_opps):
        ranked = engine.rank(scored_opps)
        assert ranked[0]["opportunity_id"] == "a"

    def test_top_n(self, engine, scored_opps):
        top = engine.top_n(scored_opps, n=2)
        assert len(top) == 2
        assert top[0]["opportunity_id"] == "a"
        assert top[1]["opportunity_id"] == "b"

    def test_above_threshold(self, engine, scored_opps):
        filtered = engine.above_threshold(scored_opps, threshold=70)
        assert len(filtered) == 1
        assert filtered[0]["opportunity_id"] == "a"

    def test_empty_list(self, engine):
        assert engine.rank([]) == []
        assert engine.top_n([], n=5) == []
        assert engine.above_threshold([], threshold=50) == []

    def test_priority_rank_sequential(self, engine, scored_opps):
        ranked = engine.rank(scored_opps)
        for idx, opp in enumerate(ranked, 1):
            assert opp["priority_rank"] == idx

    def test_singleton(self):
        a = get_prioritization_engine()
        b = get_prioritization_engine()
        assert a is b


class TestMarketSignalEngine:
    @pytest.fixture
    def engine(self):
        return MarketSignalEngine()

    def test_get_signals_returns_structure(self, engine):
        signals = engine.get_signals("Senior AI Engineer", "ai")
        assert "signals" in signals
        assert "hiring_velocity" in signals["signals"]
        assert "competition_level" in signals["signals"]

    def test_market_demand_score_range(self, engine):
        score = engine.market_demand_score({"id": "o1"})
        assert 0.0 <= score <= 1.0

    def test_singleton(self):
        a = get_market_signal_engine()
        b = get_market_signal_engine()
        assert a is b
