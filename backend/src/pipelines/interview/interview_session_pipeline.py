"""
Interview session pipeline — LangGraph-compatible interview session node.

Orchestrates full interview lifecycle: init → questions → evaluate → close.
Passes all upstream evaluation intelligence (ATS, strategy, AI readiness).

Phase 4D: Interview session pipeline.
"""
import logging
from typing import Dict, Any

from src.services.interview.interview_orchestrator import get_interview_orchestrator

logger = logging.getLogger(__name__)


class InterviewSessionPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume = state.get("resume_text") or state.get("resume_data", {}).get("text", "")
        interview_type = state.get("interview_type", "technical")
        eval_results = state.get("evaluation_results", {})
        strategy_result = state.get("strategy_result", {})
        ats_result = state.get("ats_result", {})

        if not resume:
            return {"interview_status": "error", "interview_error": "No resume text"}

        try:
            orch = get_interview_orchestrator()
            init = await orch.initialize_session(
                interview_type=interview_type,
                resume_text=resume,
                ats_data=ats_result.get("data", {}) if hasattr(ats_result, "get") else {},
                ai_readiness=strategy_result.get("ai_readiness", {}),
                architecture_maturity=strategy_result.get("trajectory", {}),
                strategy_data=strategy_result,
            )

            q_result = await orch.generate_next_question(
                session_id=init["session_id"],
                resume_text=resume,
                ats_data=ats_result.get("data", {}) if hasattr(ats_result, "get") else {},
                ai_readiness=strategy_result.get("ai_readiness", {}),
            )

            return {
                "interview_session": init,
                "interview_current_question": q_result,
                "interview_status": "initialized",
            }

        except Exception as e:
            logger.error(f"Interview session pipeline failed: {e}")
            return {"interview_status": "error", "interview_error": str(e)}


_p = None
def get_interview_session_pipeline():
    global _p
    if _p is None: _p = InterviewSessionPipeline()
    return _p
def __getattr__(n):
    if n == "interview_session_pipeline": return get_interview_session_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
