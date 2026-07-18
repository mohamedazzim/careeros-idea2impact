"""Structured schema for Application Package generation output.

Validates LLM output for resume, cover letter, outreach, and interview guide.
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field


class ResumeHeader(BaseModel):
    name: str = Field(default="[Candidate Name]", description="Full name of candidate")
    role_target: str = Field(default="", description="Target role title")
    location: str = Field(default="", description="City, State or Remote")
    email: str = Field(default="", description="Email if available in profile")
    phone: str = Field(default="", description="Phone if available")
    linkedin: str = Field(default="", description="LinkedIn URL if available")
    github: str = Field(default="", description="GitHub URL if available")
    portfolio: str = Field(default="", description="Portfolio URL if available")


class ExperienceEntry(BaseModel):
    title: str = ""
    company: str = ""
    dates: str = ""
    bullets: list[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    name: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    description: str = ""
    impact: str = ""


class EducationEntry(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""


class CertificationEntry(BaseModel):
    name: str = ""
    issuer: str = ""
    year: str = ""


class ResumeContent(BaseModel):
    header: ResumeHeader = Field(default_factory=ResumeHeader)
    summary: list[str] = Field(default_factory=list, description="3-4 strong targeted summary lines")
    skills: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Skills grouped by category: Languages, Backend, AI/ML, Cloud/DevOps, Databases, Tools",
    )
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    ats_keywords: list[str] = Field(default_factory=list)
    quality_notes: list[str] = Field(default_factory=list)


class CoverLetterContent(BaseModel):
    subject: str = ""
    body: str = ""


class OutreachContent(BaseModel):
    linkedin_message: str = ""
    email_message: str = ""


class InterviewGuideContent(BaseModel):
    likely_questions: list[str] = Field(default_factory=list)
    talking_points: list[str] = Field(default_factory=list)
    weaknesses_to_prepare: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)


class PackageMetadata(BaseModel):
    job_id: str = ""
    target_role: str = ""
    target_company: str = ""
    match_score: float = 0.0
    generation_mode: str = "llm"
    warnings: list[str] = Field(default_factory=list)


class PackageContent(BaseModel):
    resume: ResumeContent = Field(default_factory=ResumeContent)
    cover_letter: CoverLetterContent = Field(default_factory=CoverLetterContent)
    outreach: OutreachContent = Field(default_factory=OutreachContent)
    interview_guide: InterviewGuideContent = Field(default_factory=InterviewGuideContent)
    metadata: PackageMetadata = Field(default_factory=PackageMetadata)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|JSON)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _attempt_json_repair(text: str) -> str:
    """Try to repair truncated/partial JSON from LLM output."""
    text = _strip_code_fences(text)
    # Find the outermost JSON object
    start = text.find("{")
    if start == -1:
        return text
    # Track open structures to detect truncation
    stack = []
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ("{", "["):
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()
    # Case 1: All braces balanced — try parsing
    if not stack:
        try:
            data = json.loads(text[start:])
            return json.dumps(data, separators=(",", ":"))
        except (json.JSONDecodeError, ValueError):
            pass
        decoder = json.JSONDecoder()
        try:
            obj, end_idx = decoder.raw_decode(text, start)
            return json.dumps(obj, separators=(",", ":"))
        except (json.JSONDecodeError, ValueError):
            pass
    # Case 2: Truncated JSON — find longest valid prefix and close it
    truncated = text[start:]
    truncated = truncated.rstrip(", \t\n\r")
    if in_string or truncated.endswith(":") or truncated.endswith(","):
        last_close = max(truncated.rfind("}"), truncated.rfind("]"))
        if last_close > 0:
            truncated = truncated[:last_close + 1]
        else:
            truncated = "{" + "}"
    truncated = truncated.rstrip(", \t\n\r")
    # Re-track the stack on the truncated text to get correct open count
    final_stack = []
    in_str = False
    esc = False
    for ch in truncated:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ("{", "["):
            final_stack.append(ch)
        elif ch == "}":
            if final_stack and final_stack[-1] == "{":
                final_stack.pop()
        elif ch == "]":
            if final_stack and final_stack[-1] == "[":
                final_stack.pop()
    closing = ""
    for opener in reversed(final_stack):
        closing += "}" if opener == "{" else "]"
    truncated += closing
    return truncated


def parse_package_json(raw_text: str) -> PackageContent:
    """Parse LLM output into PackageContent with repair attempts.

    Raises RuntimeError with clear message if all attempts fail.
    """
    text = raw_text.strip()

    # Attempt 1: direct JSON parse
    try:
        data = json.loads(text)
        return PackageContent.model_validate(data)
    except (json.JSONDecodeError, Exception):
        pass

    # Attempt 2: strip code fences
    cleaned = _strip_code_fences(text)
    try:
        data = json.loads(cleaned)
        return PackageContent.model_validate(data)
    except (json.JSONDecodeError, Exception):
        pass

    # Attempt 3: repair truncated JSON
    repaired = _attempt_json_repair(text)
    try:
        data = json.loads(repaired)
        return PackageContent.model_validate(data)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Package generation returned non-JSON content: {str(e)[:200]}. "
            f"First 300 chars of output: {text[:300]}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Package schema validation failed: {str(e)[:200]}. "
            f"Output may be missing required fields."
        ) from e


def build_deterministic_package(
    *,
    job_title: str,
    company: str,
    skills: list[str],
    missing_skills: list[str],
    experience_summary: str,
    match_score: float,
) -> PackageContent:
    """Build a deterministic fallback package from available data.

    Used when LLM generation fails. Honest — never fabricates data.
    """
    skill_categories: dict[str, list[str]] = {
        "Skills from Profile": list(skills[:12]) if skills else ["See Knowledge Hub for full profile"],
    }
    if missing_skills:
        skill_categories["Skills to Develop"] = list(missing_skills[:8])

    resume = ResumeContent(
        header=ResumeHeader(role_target=job_title),
        summary=[
            f"Experienced professional targeting the {job_title} role at {company}.",
            "Profile evidence sourced from your CareerOS Knowledge Hub documents.",
            "Tailor this resume further by adding quantified achievements from your experience.",
        ],
        skills=skill_categories,
        experience=(
            [ExperienceEntry(company="See Knowledge Hub", title="Your Role", bullets=[experience_summary])]
            if experience_summary
            else [ExperienceEntry(company="Add your experience", title="Your Role", bullets=["Upload your resume to Knowledge Hub for auto-extraction"])]
        ),
        projects=[ProjectEntry(name="CareerOS Profile", tech_stack=skills[:5] if skills else [], description="CareerOS-powered job matching profile")],
        quality_notes=[
            "This resume was generated in deterministic fallback mode because the AI provider was unavailable.",
            "Add your resume to the Knowledge Hub and upload job descriptions for AI-generated tailored resumes.",
        ] if missing_skills else [],
    )

    return PackageContent(
        resume=resume,
        cover_letter=CoverLetterContent(
            subject=f"Application for {job_title} at {company}",
            body=f"Dear Hiring Manager,\n\nI am writing to express my interest in the {job_title} role at {company}. "
            f"My background includes {', '.join(skills[:5]) if skills else 'relevant experience'}.\n\n"
            "I would welcome the opportunity to discuss how my experience aligns with your team's goals.\n\nBest regards,\n[Candidate Name]",
        ),
        outreach=OutreachContent(
            linkedin_message=f"Hi, I came across the {job_title} role at {company} and I'm very interested. "
            f"My background in {', '.join(skills[:3]) if skills else 'this field'} aligns well. Would you be open to a brief conversation?",
            email_message=f"Subject: Interest in {job_title} role\n\nDear Hiring Team,\n\n"
            f"I'm reaching out regarding the {job_title} position at {company}. "
            f"My experience includes {', '.join(skills[:4]) if skills else 'relevant expertise'}.\n\n"
            "I've attached my resume for your review. I look forward to hearing from you.\n\nBest regards,\n[Candidate Name]",
        ),
        interview_guide=InterviewGuideContent(
            likely_questions=[
                f"Why are you interested in the {job_title} role at {company}?",
                "Tell me about a challenging project you led.",
                f"How does your experience with {skills[0] if skills else 'your core skills'} apply to this role?",
            ],
            talking_points=[
                "Highlight specific achievements with measurable impact.",
                f"Connect your experience to {company}'s industry and challenges.",
                "Prepare examples of collaboration and leadership.",
            ],
            weaknesses_to_prepare=[
                f"Address any gaps in {', '.join(missing_skills[:3])}" if missing_skills else "Prepare for general skill gap questions",
            ],
            questions_to_ask=[
                "What does success look like in the first 90 days?",
                "How does the team handle technical challenges?",
                "What are the biggest opportunities for the team this year?",
            ],
        ),
        metadata=PackageMetadata(
            job_id="",
            target_role=job_title,
            target_company=company,
            match_score=match_score,
            generation_mode="deterministic_fallback",
            warnings=["AI provider was unavailable - this package was generated from available profile data."] if missing_skills else [],
        ),
    )
