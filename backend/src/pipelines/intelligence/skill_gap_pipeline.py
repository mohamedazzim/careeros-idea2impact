"""
Skill gap pipeline — LangGraph node for skill gap analysis.
"""
import logging
from typing import Dict, Any
from src.services.intelligence.skill_gap_service import get_skill_gap_service

logger = logging.getLogger(__name__)


class SkillGapPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume = state.get("resume_text") or state.get("resume_data", {}).get("text", "")
        job = state.get("job_text") or state.get("job_data", {}).get("description", "")
        if not resume:
            return {"skill_gap_error": "No resume text", "skill_gap_status": "error"}
        try:
            svc = get_skill_gap_service()
            result = await svc.analyze(resume, job)
            return {"skill_gap_result": result.model_dump(), "skill_gap_status": "success"}
        except Exception as e:
            return {"skill_gap_error": str(e), "skill_gap_status": "error"}


_p = None
def get_skill_gap_pipeline():
    global _p
    if _p is None: _p = SkillGapPipeline()
    return _p
def __getattr__(n: str):
    if n == "skill_gap_pipeline": return get_skill_gap_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
