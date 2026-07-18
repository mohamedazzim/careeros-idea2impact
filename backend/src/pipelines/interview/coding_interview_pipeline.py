"""
Coding interview pipeline — LangGraph-compatible coding interview node.

Phase 4D: Coding interview pipeline.
"""
import logging
from typing import Dict, Any
from src.services.interview.coding_interview_service import get_coding_interview_service
logger = logging.getLogger(__name__)

class CodingInterviewPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume = state.get("resume_text", "")
        if not resume:
            return {"coding_interview_error": "No resume", "coding_interview_status": "error"}
        try:
            svc = get_coding_interview_service()
            question = await svc.generate_question(
                resume_text=resume,
                difficulty=state.get("difficulty", "intermediate"),
                domain=state.get("coding_domain", "algorithms"),
                question_history=state.get("question_history", []),
                context=state.get("retrieval_context", ""),
            )
            return {"coding_question": question.model_dump(), "coding_interview_status": "success"}
        except Exception as e:
            return {"coding_interview_error": str(e), "coding_interview_status": "error"}

_p = None
def get_coding_interview_pipeline():
    global _p
    if _p is None: _p = CodingInterviewPipeline()
    return _p
def __getattr__(n):
    if n == "coding_interview_pipeline": return get_coding_interview_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
