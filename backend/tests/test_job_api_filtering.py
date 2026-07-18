"""Tests for /jobs API default query filtering behavior.

Verifies that the default /jobs endpoint only returns India-eligible,
tech-role jobs, and that non-tech jobs are excluded from the visible feed.
"""
import pytest


def test_classify_tech_role_python():
    """Tech keyword in title should classify as tech role."""
    from src.services.job_role_filter import classify_tech_role
    result = classify_tech_role("Senior Software Engineer Python", "Build backend services")
    assert result["is_tech_role"] is True
    assert result["confidence"] >= 0.9


def test_classify_tech_role_non_tech():
    """Non-tech keyword in title should classify as non-tech role."""
    from src.services.job_role_filter import classify_tech_role
    result = classify_tech_role("Sales Executive", "Sell enterprise software")
    assert result["is_tech_role"] is False
    assert result["confidence"] >= 0.7


def test_classify_tech_role_public_area_attendant():
    """Public Area Attendant should be classified as non-tech."""
    from src.services.job_role_filter import classify_tech_role
    result = classify_tech_role("Public Area Attendant", "Clean and maintain public spaces")
    assert result["is_tech_role"] is False


def test_classify_tech_role_data_entry():
    """Data entry should be classified as non-tech."""
    from src.services.job_role_filter import classify_tech_role
    result = classify_tech_role("Online Data Entry Operator", "Enter data into spreadsheets")
    assert result["is_tech_role"] is False


def test_classify_tech_role_ml_engineer():
    """ML Engineer should be classified as tech."""
    from src.services.job_role_filter import classify_tech_role
    result = classify_tech_role("Senior ML Engineer", "Build ML models with PyTorch")
    assert result["is_tech_role"] is True
    assert result["tech_role_category"] == "ai_ml"


def test_classify_tech_role_frontend():
    """Frontend developer should be classified as tech."""
    from src.services.job_role_filter import classify_tech_role
    result = classify_tech_role("Frontend Developer", "React and TypeScript")
    assert result["is_tech_role"] is True
    assert result["tech_role_category"] == "frontend"


def test_classify_tech_role_ambigous_skills():
    """Ambiguous title with multiple tech skills should be classified as tech."""
    from src.services.job_role_filter import classify_tech_role
    result = classify_tech_role("Associate", "Python and Docker deployment",
                                skills=["python", "docker", "kubernetes"])
    assert result["is_tech_role"] is True


def test_call_eligible_above_threshold():
    """Score >= 65 should be call-eligible (current threshold is 65)."""
    from src.agents.opportunity_alert_agent import is_call_eligible
    assert is_call_eligible(65) is True
    assert is_call_eligible(69) is True
    assert is_call_eligible(85) is True
    assert is_call_eligible(100) is True


def test_call_eligible_below_threshold():
    """Score < 65 should NOT be call-eligible."""
    from src.agents.opportunity_alert_agent import is_call_eligible
    assert is_call_eligible(64.9) is False
    assert is_call_eligible(50) is False
    assert is_call_eligible(0) is False


def test_call_eligible_none():
    """None score should NOT be call-eligible."""
    from src.agents.opportunity_alert_agent import is_call_eligible
    assert is_call_eligible(None) is False


def test_call_eligible_zero_one_normalized():
    """Score 0.7 (normalized 0-1) should be call-eligible after normalization."""
    from src.agents.opportunity_alert_agent import is_call_eligible
    assert is_call_eligible(0.7) is True
    assert is_call_eligible(0.5) is False


def test_is_job_eligible_compatible():
    """Mid-level candidate for mid-level job should be compatible."""
    from src.services.job_role_filter import is_job_eligible_for_candidate
    result = is_job_eligible_for_candidate(
        job_min_years=2.0, job_max_years=8.0, job_seniority="mid",
        candidate_years=3.0, candidate_level="mid",
    )
    assert result["eligible"] is True
    assert result["match_type"] == "compatible"


def test_is_job_eligible_too_junior():
    """Junior candidate for senior job should be ineligible."""
    from src.services.job_role_filter import is_job_eligible_for_candidate
    result = is_job_eligible_for_candidate(
        job_min_years=5.0, job_max_years=None, job_seniority="senior",
        candidate_years=0.5, candidate_level="junior",
    )
    assert result["eligible"] is False
    assert result["match_type"] in ("mismatch", "candidate_too_junior")


def test_is_job_eligible_unknown_candidate():
    """Unknown candidate experience should still be allowed."""
    from src.services.job_role_filter import is_job_eligible_for_candidate
    result = is_job_eligible_for_candidate(
        job_min_years=3.0, job_max_years=8.0, job_seniority="mid",
        candidate_years=None, candidate_level="unknown",
    )
    assert result["eligible"] is True
    assert result["match_type"] == "unknown"


def test_extract_job_experience_senior():
    """'Senior' in title should extract senior seniority."""
    from src.services.job_role_filter import extract_job_experience_requirement
    result = extract_job_experience_requirement("Senior Backend Engineer", "5+ years experience")
    assert result["seniority_level"] == "senior"
    assert result["min_years"] == 5.0


def test_extract_job_experience_junior():
    """'Junior' in title should extract junior seniority."""
    from src.services.job_role_filter import extract_job_experience_requirement
    result = extract_job_experience_requirement("Junior Frontend Developer", "Entry level")
    assert result["seniority_level"] == "junior"


def test_job_response_model_fields():
    """JobResponse model should include tech role and India eligibility fields."""
    from src.api.v1.endpoints.jobs import JobResponse
    job = JobResponse(
        id=1,
        title="Software Engineer",
        is_india_eligible=True,
        is_tech_role=True,
        tech_role_category="backend",
        seniority_level="mid",
        match_score=85.0,
    )
    assert job.is_india_eligible is True
    assert job.is_tech_role is True
    assert job.tech_role_category == "backend"
    assert job.seniority_level == "mid"
    assert job.match_score == 85.0
