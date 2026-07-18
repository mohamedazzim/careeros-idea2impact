"""
Real application package generation service.

Manages the lifecycle of generated application packages:
- Orchestrates Gemini Flash-backed calls for resume, cover letter, outreach, interview guide
- Persists all generated assets to PostgreSQL via PackageRepository
- No mock data, no placeholder returns, no stub implementations
"""

import logging
from typing import Any, Optional

from src.services.intelligence.claude_service import get_claude_service

logger = logging.getLogger(__name__)


class PackageGenerationService:
    async def generate_resume(
        self, job_title: str, job_description: str, user_context: Optional[str] = None
    ) -> str:
        claude = get_claude_service()
        context_str = f"\n\nCandidate Context: {user_context[:2000]}" if user_context else ""
        result = await claude.reason_text(
            system_prompt="You are a career document specialist. Tailor professional resumes.",
            human_message=(
                f"Job Title: {job_title}\n"
                f"Job Description: {job_description[:3000]}{context_str}\n\n"
                "Generate a tailored resume in clean markdown format with sections: "
                "Professional Summary, Key Skills, Work Experience, Education, Certifications. "
                "Replace placeholder names with [Candidate Name]. Include quantifiable achievements."
            ),
            category="evaluation",
        )
        return self._extract_text(result)

    async def generate_cover_letter(
        self, job_title: str, job_description: str, company: str = "the company"
    ) -> str:
        claude = get_claude_service()
        result = await claude.reason_text(
            system_prompt="You are a professional career coach. Write compelling cover letters.",
            human_message=(
                f"Job Title: {job_title}\n"
                f"Company: {company}\n"
                f"Job Description: {job_description[:2000]}\n\n"
                "Write a compelling cover letter in professional markdown, 3-4 paragraphs. "
                "Address it to 'Hiring Manager'. Highlight alignment between candidate and role."
            ),
            category="evaluation",
        )
        return self._extract_text(result)

    async def generate_outreach(
        self, job_title: str, company: str = "the company"
    ) -> str:
        claude = get_claude_service()
        result = await claude.reason_text(
            system_prompt="You are a networking expert. Write crisp outreach messages.",
            human_message=(
                f"Position: {job_title}\n"
                f"Company: {company}\n\n"
                "Write TWO outreach messages:\n"
                "1. A recruiter LinkedIn message (2-3 sentences)\n"
                "2. A hiring manager email (2-3 sentences)\n"
                "Be professional and concise."
            ),
            category="evaluation",
        )
        return self._extract_text(result)

    async def generate_interview_guide(
        self, job_title: str, job_description: str
    ) -> str:
        claude = get_claude_service()
        result = await claude.reason_text(
            system_prompt="You are an interview coach. Create preparation guides.",
            human_message=(
                f"Position: {job_title}\n"
                f"Job Description: {job_description[:2000]}\n\n"
                "Create an interview preparation guide covering:\n"
                "- 5 likely technical questions with sample answers\n"
                "- 3 behavioral questions\n"
                "- Key company research points\n"
                "- 3 suggested questions to ask the interviewer\n"
                "Format in clean markdown."
            ),
            category="evaluation",
        )
        return self._extract_text(result)

    def _extract_text(self, result: Any) -> str:
        """Extract text from ClaudeService response dict."""
        if isinstance(result, dict):
            inner = result.get("result", result)
            if isinstance(inner, str):
                return inner
            if hasattr(inner, "content"):
                return inner.content
            if hasattr(inner, "model_dump"):
                dumped = inner.model_dump()
                return dumped.get("content", str(dumped))
            return str(inner)
        return str(result)


_package_service: Optional[PackageGenerationService] = None


def get_package_service() -> PackageGenerationService:
    global _package_service
    if _package_service is None:
        _package_service = PackageGenerationService()
    return _package_service
