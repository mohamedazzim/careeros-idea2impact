"""Tests for resume experience extraction."""
from src.services.resume_experience_extractor import extract_resume_experience


def test_unknown_when_no_years():
    result = extract_resume_experience(resume_text="Looking for my first software role")
    assert result["experience_level"] == "unknown"
    assert result["years_of_experience"] is None


def test_intern_is_entry():
    result = extract_resume_experience(resume_text="Software engineering intern at Google")
    assert result["is_intern"] is True
    assert result["experience_level"] == "entry"


def test_one_year():
    result = extract_resume_experience(resume_text="1 year experience in Python")
    assert result["years_of_experience"] == 1.0
    assert result["experience_level"] == "junior"


def test_two_years():
    result = extract_resume_experience(resume_text="2 years of experience in full stack")
    assert result["years_of_experience"] == 2.0
    assert result["experience_level"] == "mid"


def test_two_point_five_years():
    result = extract_resume_experience(resume_text="2.5 years of experience")
    assert result["years_of_experience"] == 2.5
    assert result["experience_level"] == "mid"


def test_three_plus_years():
    result = extract_resume_experience(resume_text="3+ years experience in backend")
    assert result["years_of_experience"] == 3.0
    assert result["experience_level"] == "mid"


def test_five_years():
    result = extract_resume_experience(resume_text="5 years of experience in software")
    assert result["years_of_experience"] == 5.0
    assert result["experience_level"] == "senior"


def test_six_years():
    result = extract_resume_experience(resume_text="6 years of experience in software")
    assert result["years_of_experience"] == 6.0
    assert result["experience_level"] == "senior"


def test_eight_years():
    result = extract_resume_experience(resume_text="8 years of experience in architecture")
    assert result["years_of_experience"] == 8.0
    assert result["experience_level"] == "lead"


def test_ten_years():
    result = extract_resume_experience(resume_text="Over 10 years of experience leading teams")
    assert result["years_of_experience"] == 10.0
    assert result["experience_level"] == "lead"


def test_date_range():
    result = extract_resume_experience(resume_text="Worked at Google from 2019 to 2024")
    assert result["years_of_experience"] >= 4.0


def test_unknown_no_signal():
    result = extract_resume_experience(resume_text="Passionate about technology")
    assert result["experience_level"] == "unknown"


def test_analysis_results():
    result = extract_resume_experience(analysis_results={"years_of_experience": 4})
    assert result["years_of_experience"] == 4.0
    assert result["experience_level"] == "mid"


def test_empty():
    result = extract_resume_experience()
    assert result["experience_level"] == "unknown"


def test_multiple_signals_use_max():
    result = extract_resume_experience(resume_text="2 years at Company A, worked from 2020 to 2025")
    assert result["years_of_experience"] >= 2.0
