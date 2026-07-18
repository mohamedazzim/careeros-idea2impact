"""
Technical interview pipeline — LangGraph-compatible technical interview node.

Generates technical question and evaluates answer using Claude's
retrieval-grounded reasoning pipeline.

Phase 4D: Technical interview pipeline.
"""
import logging
from typing import Dict, Any

from src.services.interview.technical_interview_service import get_technical_interview_service

logger = logging.getLogger(__name__)


class TechnicalInterviewPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume = state.get("resume_text", "")
        if not resume:
            return {"technical_interview_error": "No resume", "technical_interview_status": "error"}

        try:
            svc = get_technical_interview_service()
            question = await svc.generate_question(
                resume_text=resume,
                difficulty=state.get("difficulty", "intermediate"),
                domain=state.get("technical_domain", "backend_engineering"),
                question_history=state.get("question_history", []),
                context=state.get("retrieval_context", ""),
            )
            return {"technical_question": question.model_dump(), "technical_interview_status": "success"}
        except Exception as e:
            return {"technical_interview_error": str(e), "technical_interview_status": "error"}

    async def evaluate(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            svc = get_technical_interview_service()
            result = await svc.evaluate_answer(
                question=state.get("question", ""),
                answer=state.get("answer", ""),
                difficulty=state.get("difficulty", "intermediate"),
                domain=state.get("technical_domain", "backend_engineering"),
                candidate_context=state.get("resume_text", ""),
            )
            return {"technical_evaluation": result.model_dump(), "technical_interview_status": "success"}
        except Exception as e:
            return {"technical_interview_error": str(e), "technical_interview_status": "error"}


_p = None
def get_technical_interview_pipeline():
    global _p
    if _p is None: _p = TechnicalInterviewPipeline()
    return _p
def __getattr__(n):
    if n == "technical_interview_pipeline": return get_technical_interview_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
