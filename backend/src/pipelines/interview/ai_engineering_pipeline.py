"""
AI engineering interview pipeline — LangGraph-compatible AI engineering node.

Phase 4D: AI engineering interview pipeline.
"""
import logging
from typing import Dict, Any
from src.services.interview.ai_engineering_interview_service import get_ai_engineering_interview_service
logger = logging.getLogger(__name__)

class AIEngineeringPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume = state.get("resume_text", "")
        if not resume:
            return {"ai_engineering_error": "No resume", "ai_engineering_status": "error"}
        try:
            svc = get_ai_engineering_interview_service()
            question = await svc.generate_question(
                resume_text=resume,
                difficulty=state.get("difficulty", "intermediate"),
                domain=state.get("ai_engineering_domain", "rag_systems"),
                ai_readiness_signals=state.get("ai_readiness_signals", ""),
                context=state.get("retrieval_context", ""),
            )
            return {"ai_engineering_question": question.model_dump(), "ai_engineering_status": "success"}
        except Exception as e:
            return {"ai_engineering_error": str(e), "ai_engineering_status": "error"}

_p = None
def get_ai_engineering_pipeline():
    global _p
    if _p is None: _p = AIEngineeringPipeline()
    return _p
def __getattr__(n):
    if n == "ai_engineering_pipeline": return get_ai_engineering_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
