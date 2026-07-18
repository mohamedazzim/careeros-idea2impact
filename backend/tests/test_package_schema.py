"""Tests for package schema parsing, JSON repair, and deterministic fallback."""
import json
import pytest
from src.schemas.package import (
    parse_package_json,
    build_deterministic_package,
    _strip_code_fences,
    _attempt_json_repair,
    PackageContent,
    ResumeContent,
    ResumeHeader,
)


class TestStripCodeFences:
    def test_plain_json(self):
        assert _strip_code_fences('{"key": "value"}') == '{"key": "value"}'

    def test_json_with_fence(self):
        result = _strip_code_fences('```json\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

    def test_json_with_plain_fence(self):
        result = _strip_code_fences('```\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'


class TestJsonRepair:
    def test_returns_valid_json_as_is(self):
        text = '{"a": 1}'
        repaired = _attempt_json_repair(text)
        assert json.loads(repaired) == {"a": 1}

    def test_closes_truncated_object(self):
        text = '{"a": 1, "b": [1, 2, 3'
        repaired = _attempt_json_repair(text)
        assert json.loads(repaired) == {"a": 1, "b": [1, 2, 3]}

    def test_extracts_from_prose(self):
        text = 'Some intro text {"result": "ok"} and trailing text'
        repaired = _attempt_json_repair(text)
        assert json.loads(repaired) == {"result": "ok"}


class TestParsePackageJson:
    def test_parses_valid_full_package(self):
        data = {
            "resume": {
                "header": {"name": "Jane Doe", "role_target": "Python Developer"},
                "summary": ["Experienced developer with 5 years in Python."],
                "skills": {"Languages": ["Python", "TypeScript"]},
                "experience": [{"title": "Senior Dev", "company": "Acme Corp", "dates": "2020-2023", "bullets": ["Built APIs"]}],
                "projects": [],
                "education": [],
                "certifications": [],
                "achievements": [],
                "ats_keywords": ["Python", "API"],
                "quality_notes": [],
            },
            "cover_letter": {"subject": "Application", "body": "Dear Hiring Manager..."},
            "outreach": {"linkedin_message": "Hi, interested...", "email_message": "Subject: Application..."},
            "interview_guide": {
                "likely_questions": ["Tell me about yourself"],
                "talking_points": ["Highlight achievements"],
                "weaknesses_to_prepare": ["Prepare for gap questions"],
                "questions_to_ask": ["What is the team size?"],
            },
            "metadata": {"warnings": []},
        }
        parsed = parse_package_json(json.dumps(data))
        assert isinstance(parsed, PackageContent)
        assert parsed.resume.header.name == "Jane Doe"
        assert parsed.resume.summary[0].startswith("Experienced")
        assert parsed.resume.skills["Languages"] == ["Python", "TypeScript"]
        assert parsed.cover_letter.subject == "Application"
        assert parsed.outreach.linkedin_message.startswith("Hi")
        assert len(parsed.interview_guide.likely_questions) == 1

    def test_parses_fenced_json(self):
        data = {"resume": {"header": {}, "summary": ["Test"], "skills": {}, "experience": [], "projects": [], "education": [], "certifications": [], "achievements": [], "ats_keywords": [], "quality_notes": []}, "cover_letter": {"subject": "", "body": ""}, "outreach": {"linkedin_message": "", "email_message": ""}, "interview_guide": {"likely_questions": [], "talking_points": [], "weaknesses_to_prepare": [], "questions_to_ask": []}, "metadata": {"warnings": []}}
        text = '```json\n' + json.dumps(data) + '\n```'
        parsed = parse_package_json(text)
        assert isinstance(parsed, PackageContent)

    def test_fails_on_gibberish(self):
        with pytest.raises(RuntimeError, match="non-JSON"):
            parse_package_json("This is not JSON at all, just random text from an LLM.")

    def test_repairs_truncated_json(self):
        valid = {
            "resume": {"header": {}, "summary": ["Test"], "skills": {}, "experience": [], "projects": [], "education": [], "certifications": [], "achievements": [], "ats_keywords": [], "quality_notes": []},
            "cover_letter": {"subject": "App", "body": "Content"},
            "outreach": {"linkedin_message": "Hi", "email_message": "Email"},
            "interview_guide": {"likely_questions": [], "talking_points": [], "weaknesses_to_prepare": [], "questions_to_ask": []},
            "metadata": {"warnings": []},
        }
        full = json.dumps(valid)
        truncated = full[:len(full) - 5]
        parsed = parse_package_json(truncated)
        assert isinstance(parsed, PackageContent)


class TestDeterministicFallback:
    def test_builds_valid_package_with_minimal_data(self):
        pkg = build_deterministic_package(
            job_title="Python Developer",
            company="Acme Corp",
            skills=["Python", "FastAPI"],
            missing_skills=["Docker"],
            experience_summary="Built APIs at previous company.",
            match_score=68.0,
        )
        assert isinstance(pkg, PackageContent)
        assert pkg.resume.header.role_target == "Python Developer"
        assert pkg.resume.summary[0].startswith("Experienced")
        assert "Python" in pkg.resume.skills.get("Skills from Profile", [])
        assert "Docker" in pkg.resume.skills.get("Skills to Develop", [])
        assert pkg.cover_letter.subject.startswith("Application")
        assert pkg.cover_letter.body.startswith("Dear")
        assert pkg.outreach.linkedin_message.startswith("Hi")
        assert len(pkg.interview_guide.likely_questions) == 3
        assert pkg.metadata.generation_mode == "deterministic_fallback"

    def test_builds_package_with_no_skills(self):
        pkg = build_deterministic_package(
            job_title="Engineer",
            company="Co",
            skills=[],
            missing_skills=[],
            experience_summary="",
            match_score=0.0,
        )
        assert isinstance(pkg, PackageContent)
        assert "Add your experience" in str(pkg.resume.experience[0].company)
