"""
Resume evaluation pipeline — LangGraph-compatible full resume evaluation node.

Runs resume analysis, achievement analysis, skill gap analysis,
and recruiter review in a coordinated pipeline.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import logging
from typing import Dict, Any

from src.services.intelligence.skill_gap_service import get_skill_gap_service
from src.services.intelligence.semantic_fit_service import get_semantic_fit_service
from src.services.intelligence.achievement_analysis_service import get_achievement_analysis_service
from src.services.intelligence.recruiter_evaluation_service import get_recruiter_evaluation_service
from src.services.intelligence.recommendation_engine import get_recommendation_engine

logger = logging.getLogger(__name__)


class ResumeEvaluationPipeline:
    """Full resume evaluation: analysis + gaps + fit + recruiter + recommendations."""

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume_text = state.get("resume_text") or state.get("resume_data", {}).get("text", "")
        job_text = state.get("job_text") or state.get("job_data", {}).get("description", "")
        ats_result = state.get("ats_result", {})

        if not resume_text:
            return {"evaluation_error": "No resume text", "evaluation_status": "error"}

        try:
            results = {}

            # Skill gap analysis
            gaps = get_skill_gap_service()
            results["skill_gaps"] = await gaps.analyze(resume_text, job_text)

            # Semantic fit
            fit = get_semantic_fit_service()
            results["semantic_fit"] = await fit.analyze(resume_text, job_text)

            # Achievement analysis
            achievements = get_achievement_analysis_service()
            results["achievements"] = await achievements.analyze(resume_text)

            # Recruiter review
            recruiter = get_recruiter_evaluation_service()
            ats_summary = ats_result.get("data", ats_result)
            results["recruiter"] = await recruiter.evaluate(
                resume_text, job_text, ats_summary
            )

            # Recommendations (best-effort — runs even if some upstream fails)
            try:
                rec = get_recommendation_engine()
                results["recommendations"] = await rec.generate(
                    ats_score=ats_summary.get("overall_score", 0),
                    strengths=ats_summary.get("strengths", []),
                    weaknesses=ats_summary.get("weaknesses", []),
                    skill_gaps=results["skill_gaps"].data,
                    achievement_analysis=results["achievements"].data,
                )
            except Exception as e:
                logger.warning(f"Recommendation generation failed: {e}")
                results["recommendations"] = {"error": str(e)}

            return {
                "evaluation_results": results,
                "evaluation_status": "success",
                "evaluation_error": None,
            }

        except Exception as e:
            logger.error(f"Resume evaluation pipeline failed: {e}")
            return {"evaluation_error": str(e), "evaluation_status": "error"}


_pipeline: ResumeEvaluationPipeline | None = None


def get_resume_evaluation_pipeline() -> ResumeEvaluationPipeline:
    global _pipeline
    if _pipeline is None: _pipeline = ResumeEvaluationPipeline()
    return _pipeline


def __getattr__(name: str):
    if name == "resume_evaluation_pipeline": return get_resume_evaluation_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
