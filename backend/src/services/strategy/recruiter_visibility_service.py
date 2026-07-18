"""Recruiter visibility service — recruiter attractiveness and discoverability intelligence."""
import logging
from typing import Any, Optional
from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.schemas.intelligence import StructuredResponse
logger = logging.getLogger(__name__)

class RecruiterVisibilityService:
    async def analyze(self, resume_text: str="", recruiter_review: Any="", ats_score: Any="", context: str="") -> StructuredResponse:
        return await get_reasoning_pipeline().reason(query="recruiter visibility", category="strategy", prompt_id="hiring_probability",
            template_vars={"ats_score": str(ats_score), "recruiter_review": str(recruiter_review), "skill_gaps": "", "portfolio_strength": "", "context": context})

_svc: Optional[RecruiterVisibilityService] = None
def get_recruiter_visibility_service(): global _svc; _svc = _svc or RecruiterVisibilityService(); return _svc
def __getattr__(n):
    if n == "recruiter_visibility_service": return get_recruiter_visibility_service()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
