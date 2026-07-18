"""Tests for Opportunity Match Engine — 10 scoring dimensions."""

import pytest
from src.services.opportunity.opportunity_match_engine import (
    OpportunityMatchEngine,
    get_opportunity_match_engine,
)


class TestOpportunityMatchEngine:
    @pytest.fixture
    def engine(self):
        return OpportunityMatchEngine()

    @pytest.fixture
    def sample_opp(self):
        return {
            "id": "opp_1",
            "title": "Senior AI Engineer",
            "company": "Anthropic",
            "skills": ["python", "pytorch", "transformers", "langchain"],
            "domain": "artificial intelligence",
            "deadline": "2026-06-05T00:00:00Z",
            "description": "Urgent immediate hire for AI team. ASAP.",
        }

    @pytest.fixture
    def sample_candidate(self):
        return {
            "skills": ["python", "pytorch", "docker", "fastapi"],
            "target_role": "senior ai engineer",
            "domains": ["artificial intelligence", "machine learning"],
        }

    def test_score_returns_all_dimensions(self, engine, sample_opp, sample_candidate):
        result = engine.score(sample_opp, sample_candidate)
        for dim in engine.DIMENSIONS:
            assert dim in result["dimension_scores"], f"Missing: {dim}"

    def test_score_in_range(self, engine, sample_opp, sample_candidate):
        result = engine.score(sample_opp, sample_candidate)
        assert 0 <= result["overall_score"] <= 100

    def test_skill_overlap(self, engine, sample_opp, sample_candidate):
        result = engine.score(sample_opp, sample_candidate)
        dim = result["dimension_scores"]["skill_overlap"]
        assert dim["score"] > 30  # python + pyTorch match

    def test_missing_skills_penalty(self, engine, sample_opp, sample_candidate):
        result = engine.score(sample_opp, sample_candidate)
        dim = result["dimension_scores"]["missing_skills"]
        assert dim["score"] < 100  # transformers + langchain missing

    def test_role_alignment_match(self, engine, sample_opp, sample_candidate):
        result = engine.score(sample_opp, sample_candidate)
        dim = result["dimension_scores"]["role_alignment"]
        assert dim["score"] >= 85  # exact match

    def test_role_alignment_no_match(self, engine, sample_opp, sample_candidate):
        c = dict(sample_candidate, target_role="data analyst", domains=["data analytics"])
        result = engine.score(sample_opp, c)
        if "role_alignment" in result["dimension_scores"]:
            dim = result["dimension_scores"]["role_alignment"]
            assert dim["score"] < 60
        else:
            assert result.get("domain_filtered") is True or result["overall_score"] < 50

    def test_domain_alignment_match(self, engine, sample_opp, sample_candidate):
        result = engine.score(sample_opp, sample_candidate)
        dim = result["dimension_scores"]["domain_alignment"]
        assert dim["score"] >= 80

    def test_application_urgency_detected(self, engine, sample_opp, sample_candidate):
        result = engine.score(sample_opp, sample_candidate)
        dim = result["dimension_scores"]["application_urgency"]
        assert dim["score"] > 20

    def test_confidence_per_dimension(self, engine, sample_opp, sample_candidate):
        result = engine.score(sample_opp, sample_candidate)
        for dim in engine.DIMENSIONS:
            info = result["dimension_scores"][dim]
            assert 0.0 <= info["confidence"] <= 1.0
            assert "score" in info
            assert "weight" in info

    def test_empty_skills(self, engine):
        opp = {"id": "o", "title": "Engineer", "skills": []}
        cand = {"skills": ["python"]}
        result = engine.score(opp, cand)
        assert result["overall_score"] >= 0

    def test_seniority_fit_staff(self, engine):
        opp = {"id": "o", "title": "Staff ML Engineer", "skills": []}
        cand = {"skills": []}
        result = engine.score(opp, cand)
        dim = result["dimension_scores"]["seniority_fit"]
        assert dim["score"] >= 80

    def test_seniority_fit_junior(self, engine):
        opp = {"id": "o", "title": "Junior Developer", "skills": []}
        cand = {"skills": []}
        result = engine.score(opp, cand)
        dim = result["dimension_scores"]["seniority_fit"]
        assert dim["score"] <= 30

    def test_overall_confidence_returned(self, engine, sample_opp, sample_candidate):
        result = engine.score(sample_opp, sample_candidate)
        assert 0 <= result["confidence"] <= 1.0

    def test_weights_sum_to_one(self, engine):
        total = sum(engine.WEIGHTS.values())
        assert 0.99 <= total <= 1.01, f"Weights sum to {total}"

    def test_evidence_citations(self, engine, sample_opp, sample_candidate):
        result = engine.score(sample_opp, sample_candidate)
        assert isinstance(result["evidence_citations"], list)

    def test_singleton(self):
        a = get_opportunity_match_engine()
        b = get_opportunity_match_engine()
        assert a is b
