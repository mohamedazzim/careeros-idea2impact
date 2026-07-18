"""
Recruiter review pipeline — LangGraph node for enterprise recruiter evaluation.
"""
import logging
from typing import Dict, Any
from src.services.intelligence.recruiter_evaluation_service import get_recruiter_evaluation_service

logger = logging.getLogger(__name__)


class RecruiterReviewPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume = state.get("resume_text") or state.get("resume_data", {}).get("text", "")
        job = state.get("job_text") or state.get("job_data", {}).get("description", "")
        ats = state.get("ats_result", {})
        if not resume:
            return {"recruiter_error": "No resume text", "recruiter_status": "error"}
        try:
            svc = get_recruiter_evaluation_service()
            result = await svc.evaluate(resume, job, ats)
            return {"recruiter_result": result.model_dump(), "recruiter_status": "success"}
        except Exception as e:
            return {"recruiter_error": str(e), "recruiter_status": "error"}


_p = None
def get_recruiter_review_pipeline():
    global _p
    if _p is None: _p = RecruiterReviewPipeline()
    return _p
def __getattr__(n: str):
    if n == "recruiter_review_pipeline": return get_recruiter_review_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
