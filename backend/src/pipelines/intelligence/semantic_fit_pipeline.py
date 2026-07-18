"""
Semantic fit pipeline — LangGraph node for job-fit analysis.
"""
import logging
from typing import Dict, Any
from src.services.intelligence.semantic_fit_service import get_semantic_fit_service

logger = logging.getLogger(__name__)


class SemanticFitPipeline:
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume = state.get("resume_text") or state.get("resume_data", {}).get("text", "")
        job = state.get("job_text") or state.get("job_data", {}).get("description", "")
        if not resume:
            return {"semantic_fit_error": "No resume text", "semantic_fit_status": "error"}
        try:
            svc = get_semantic_fit_service()
            result = await svc.analyze(resume, job)
            return {"semantic_fit_result": result.model_dump(), "semantic_fit_status": "success"}
        except Exception as e:
            return {"semantic_fit_error": str(e), "semantic_fit_status": "error"}


_p = None
def get_semantic_fit_pipeline():
    global _p
    if _p is None: _p = SemanticFitPipeline()
    return _p
def __getattr__(n: str):
    if n == "semantic_fit_pipeline": return get_semantic_fit_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")
