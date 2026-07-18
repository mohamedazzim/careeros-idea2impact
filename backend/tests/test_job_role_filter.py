"""Tests for tech-role classification and experience-level filtering."""
from src.services.job_role_filter import (
    classify_tech_role,
    extract_job_experience_requirement,
    is_job_eligible_for_candidate,
)


# --- Tech-role classification ---

def test_software_engineer_is_tech():
    assert classify_tech_role("Software Engineer")["is_tech_role"] is True

def test_data_scientist_is_tech():
    assert classify_tech_role("Data Scientist")["is_tech_role"] is True

def test_frontend_dev_is_tech():
    assert classify_tech_role("Frontend Developer")["is_tech_role"] is True

def test_fullstack_is_tech():
    assert classify_tech_role("Full Stack Developer")["is_tech_role"] is True

def test_ai_engineer_is_tech():
    assert classify_tech_role("AI Engineer")["is_tech_role"] is True

def test_devops_is_tech():
    assert classify_tech_role("DevOps Engineer")["is_tech_role"] is True

def test_mobile_dev_is_tech():
    assert classify_tech_role("Mobile Developer")["is_tech_role"] is True

def test_sales_is_not_tech():
    r = classify_tech_role("Sales Executive")
    assert r["is_tech_role"] is False
    assert r["confidence"] >= 0.7

def test_hr_manager_is_not_tech():
    r = classify_tech_role("HR Manager")
    assert r["is_tech_role"] is False
    assert r["confidence"] >= 0.7

def test_marketing_is_not_tech():
    assert classify_tech_role("Marketing Associate")["is_tech_role"] is False

def test_accountant_is_not_tech():
    assert classify_tech_role("Senior Accountant")["is_tech_role"] is False

def test_customer_support_is_not_tech():
    assert classify_tech_role("Customer Support Specialist")["is_tech_role"] is False

def test_ambiguous_with_tech_skills():
    r = classify_tech_role("Analyst", skills=["Python", "SQL", "pandas"])
    assert r["is_tech_role"] is True

def test_ambiguous_with_tech_description():
    r = classify_tech_role("Engineer", description="Microservices with Python, Docker, Kubernetes, React, PostgreSQL")
    assert r["is_tech_role"] is True


# --- Experience requirement extraction ---

def test_experience_5plus_years():
    r = extract_job_experience_requirement("Senior Developer", "Requires 5+ years of experience")
    assert r["min_years"] == 5.0

def test_experience_range():
    r = extract_job_experience_requirement("Mid-level Developer", "Requires 4 to 6 years of relevant experience")
    assert r["min_years"] == 4.0
    assert r["max_years"] == 6.0

def test_seniority_from_title():
    r = extract_job_experience_requirement("Senior Software Engineer")
    assert r["seniority_level"] == "senior"
    assert r["min_years"] == 5.0

def test_junior_from_title():
    assert extract_job_experience_requirement("Junior Developer")["seniority_level"] == "junior"

def test_lead_from_title():
    r = extract_job_experience_requirement("Tech Lead")
    assert r["seniority_level"] == "lead"
    assert r["min_years"] == 8.0

def test_plain_title_infers_seniority():
    r = extract_job_experience_requirement("Software Engineer")
    assert r["seniority_level"] is not None


# --- Experience filtering ---

def test_unknown_candidate_not_blocked():
    r = is_job_eligible_for_candidate(5.0, None, "senior", None, "unknown")
    assert r["eligible"] is True
    assert r["match_type"] == "unknown"

def test_no_requirement_always_eligible():
    r = is_job_eligible_for_candidate(None, None, None, 3.0, "mid")
    assert r["eligible"] is True

def test_0_2_candidate_excludes_senior():
    r = is_job_eligible_for_candidate(5.0, None, "senior", 1.0, "junior")
    assert r["eligible"] is False
    assert "too_junior" in r["reason"]

def test_0_2_candidate_accepts_junior():
    r = is_job_eligible_for_candidate(0.0, 2.0, "junior", 1.5, "junior")
    assert r["eligible"] is True

def test_3_year_candidate_accepts_mid():
    r = is_job_eligible_for_candidate(2.0, 5.0, "mid", 3.0, "mid")
    assert r["eligible"] is True

def test_6_year_candidate_accepts_senior():
    r = is_job_eligible_for_candidate(5.0, None, "senior", 6.0, "senior")
    assert r["eligible"] is True

def test_10_year_on_junior_job():
    r = is_job_eligible_for_candidate(0.0, 2.0, "junior", 10.0, "lead")
    assert r["eligible"] is False
    assert "too_senior" in r["reason"]

def test_lead_on_senior_job():
    r = is_job_eligible_for_candidate(5.0, 8.0, "senior", 10.0, "lead")
    assert r["eligible"] is True

def test_senior_on_junior_job():
    r = is_job_eligible_for_candidate(0.0, 2.0, "junior", 7.0, "senior")
    assert r["eligible"] is True
