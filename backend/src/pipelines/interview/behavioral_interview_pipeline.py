"""
Behavioral interview pipeline — LangGraph-compatible behavioral interview node.

Phase 4D: Behavioral interview pipeline.
"""
import logging
from typing import Dict, Any
from src.services.interview.behavioral_interview_service import get_behavioral_interview_service
logger = logging.getLogger(__name__)

class BehavioralInterviewPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume = state.get("resume_text", "")
        if not resume:
            return {"behavioral_interview_error": "No resume", "behavioral_interview_status": "error"}
        try:
            svc = get_behavioral_interview_service()
            question = await svc.generate_question(
                resume_text=resume,
                difficulty=state.get("difficulty", "intermediate"),
                category=state.get("behavioral_category", "leadership"),
                recruiter_signals=state.get("recruiter_signals", ""),
                context=state.get("retrieval_context", ""),
            )
            return {"behavioral_question": question.model_dump(), "behavioral_interview_status": "success"}
        except Exception as e:
            return {"behavioral_interview_error": str(e), "behavioral_interview_status": "error"}

_p = None
def get_behavioral_interview_pipeline():
    global _p
    if _p is None: _p = BehavioralInterviewPipeline()
    return _p
def __getattr__(n):
    if n == "behavioral_interview_pipeline": return get_behavioral_interview_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
