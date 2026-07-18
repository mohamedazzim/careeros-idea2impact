"""
Interview feedback pipeline — LangGraph-compatible interview feedback node.

Orchestrates end-of-session feedback: weakness pattern detection, growth plan
generation, session trace building, and full interview close summary.

Phase 4D: Interview feedback pipeline.
"""
import logging
from typing import Dict, Any

from src.services.interview.interview_orchestrator import get_interview_orchestrator

logger = logging.getLogger(__name__)


class InterviewFeedbackPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        session = state.get("interview_session", {})
        session_id = session.get("session_id")

        if not session_id:
            return {"feedback_error": "No session_id in state", "feedback_status": "error"}

        resume = state.get("resume_text", "")
        strategy_result = state.get("strategy_result", {})
        learning_path = state.get("learning_path", "")

        try:
            orch = get_interview_orchestrator()
            close_result = await orch.close_session(
                session_id=session_id,
                resume_text=resume,
                strategy_data=str(strategy_result) if strategy_result else "",
                learning_path=str(learning_path) if learning_path else "",
                context=state.get("retrieval_context", ""),
            )

            return {
                "feedback_status": "success",
                "session_summary": close_result.get("session_summary", {}),
                "weakness_patterns": close_result.get("weakness_patterns", {}),
                "growth_plan": close_result.get("growth_plan"),
                "feedback_summary": close_result.get("feedback_summary"),
                "session_trace": close_result.get("session_trace"),
            }

        except Exception as e:
            logger.error(f"Feedback pipeline failed: {e}")
            return {"feedback_error": str(e), "feedback_status": "error"}


_p: InterviewFeedbackPipeline | None = None


def get_interview_feedback_pipeline() -> InterviewFeedbackPipeline:
    global _p
    if _p is None:
        _p = InterviewFeedbackPipeline()
    return _p


def __getattr__(name: str):
    if name == "interview_feedback_pipeline":
        return get_interview_feedback_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
