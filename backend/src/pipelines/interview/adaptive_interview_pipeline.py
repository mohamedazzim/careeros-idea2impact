"""
Adaptive interview pipeline — LangGraph-compatible adaptive interview node.

Handles question generation, answer evaluation, difficulty adaptation,
and feedback in a single LangGraph node.

Phase 4D: Adaptive interview pipeline.
"""
import logging
from typing import Dict, Any

from src.services.interview.interview_orchestrator import get_interview_orchestrator

logger = logging.getLogger(__name__)


class AdaptiveInterviewPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        session = state.get("interview_session", {})
        question_state = state.get("interview_current_question", {})
        resume = state.get("resume_text", "")
        answer = state.get("interview_answer", "")

        session_id = session.get("session_id")
        if not session_id or not answer:
            return {"interview_error": "Missing session_id or answer", "interview_status": "error"}

        try:
            orch = get_interview_orchestrator()
            eval_result = await orch.evaluate_answer(
                session_id=session_id,
                question=question_state.get("question", ""),
                answer=answer,
                resume_text=resume,
            )

            next_q = await orch.generate_next_question(
                session_id=session_id,
                resume_text=resume,
            )

            return {
                "interview_last_evaluation": eval_result,
                "interview_current_question": next_q,
                "interview_status": "in_progress",
                "interview_scoring": eval_result.get("evaluation", {}),
                "interview_governance_result": eval_result.get("governance", {}),
                "interview_feedback": eval_result.get("feedback", {}),
            }

        except Exception as e:
            logger.error(f"Adaptive interview pipeline failed: {e}")
            return {"interview_error": str(e), "interview_status": "error"}


_p = None
def get_adaptive_interview_pipeline():
    global _p
    if _p is None: _p = AdaptiveInterviewPipeline()
    return _p
def __getattr__(n):
    if n == "adaptive_interview_pipeline": return get_adaptive_interview_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
