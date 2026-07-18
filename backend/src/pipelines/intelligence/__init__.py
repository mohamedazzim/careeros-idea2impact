"""
Intelligence pipelines — LangGraph-compatible evaluation nodes.

Phase 4B: ATS, resume evaluation, skill gap, semantic fit,
recommendation, and recruiter review pipelines.
Phase 4B Hardening: parallelized pipeline with timeout + partial recovery.
"""
from .ats_pipeline import ATSPipeline
from .resume_evaluation_pipeline import ResumeEvaluationPipeline
from .skill_gap_pipeline import SkillGapPipeline
from .semantic_fit_pipeline import SemanticFitPipeline
from .recommendation_pipeline import RecommendationPipeline
from .recruiter_review_pipeline import RecruiterReviewPipeline
from .hardened_resume_evaluation_pipeline import HardenedResumeEvaluationPipeline

__all__ = [
    "ATSPipeline",
    "ResumeEvaluationPipeline",
    "SkillGapPipeline",
    "SemanticFitPipeline",
    "RecommendationPipeline",
    "RecruiterReviewPipeline",
    "HardenedResumeEvaluationPipeline",
    "ats_pipeline", "resume_evaluation_pipeline",
    "skill_gap_pipeline", "semantic_fit_pipeline",
    "recommendation_pipeline", "recruiter_review_pipeline",
    "hardened_resume_evaluation_pipeline",
]

def __getattr__(name: str):
    if name == "ats_pipeline":
        from .ats_pipeline import get_ats_pipeline; return get_ats_pipeline()
    if name == "resume_evaluation_pipeline":
        from .resume_evaluation_pipeline import get_resume_evaluation_pipeline; return get_resume_evaluation_pipeline()
    if name == "skill_gap_pipeline":
        from .skill_gap_pipeline import get_skill_gap_pipeline; return get_skill_gap_pipeline()
    if name == "semantic_fit_pipeline":
        from .semantic_fit_pipeline import get_semantic_fit_pipeline; return get_semantic_fit_pipeline()
    if name == "recommendation_pipeline":
        from .recommendation_pipeline import get_recommendation_pipeline; return get_recommendation_pipeline()
    if name == "recruiter_review_pipeline":
        from .recruiter_review_pipeline import get_recruiter_review_pipeline; return get_recruiter_review_pipeline()
    if name == "hardened_resume_evaluation_pipeline":
        from .hardened_resume_evaluation_pipeline import get_hardened_resume_evaluation_pipeline; return get_hardened_resume_evaluation_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
