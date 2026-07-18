"""
ATS scoring service — enterprise multi-category ATS evaluation.

Evaluates resumes against job descriptions using 14 scoring categories,
each grounded in retrieval evidence with citations.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import logging
import time
from typing import Optional

from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.services.intelligence.output_validator import get_output_validator
from src.services.retrieval.hybrid_retrieval_service import get_hybrid_retrieval_service
from src.schemas.intelligence import StructuredResponse

logger = logging.getLogger(__name__)

ATS_EXPECTED_KEYS = [
    "overall_score", "category_scores", "strengths", "weaknesses",
    "missing_skills", "ats_risks", "evidence", "citations", "confidence",
]


class ATSScoringService:
    """Enterprise ATS scoring with retrieval-grounded multi-category evaluation."""

    async def evaluate(
        self,
        resume_text: str,
        job_text: str,
        resume_id: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> StructuredResponse:
        """Execute full ATS evaluation.

        Pipeline: retrieve resume context → retrieve job requirements
        → build template vars → reasoning pipeline → validate → return.
        """
        overall_start = time.monotonic()

        # Retrieve context for resume and job
        hybrid = get_hybrid_retrieval_service()
        resume_ctx = await hybrid.retrieve(
            query=resume_text[:500],
            collection="careeros_resumes",
            filter_kwargs={"user_id": user_id} if user_id else None,
            top_k=10,
            top_n=5,
            use_hybrid=True,
        )
        job_ctx = await hybrid.retrieve(
            query=job_text[:500],
            collection="careeros_jobs",
            top_k=10,
            top_n=5,
            use_hybrid=True,
        )

        combined_context = (
            f"RESUME CONTEXT:\n{resume_ctx.context}\n\n"
            f"JOB CONTEXT:\n{job_ctx.context}"
        )

        template_vars = {
            "resume_text": resume_text,
            "job_text": job_text,
            "context": combined_context,
            "tech_stack": self._extract_tech(resume_text, job_text),
        }

        pipeline = get_reasoning_pipeline()
        response = await pipeline.reason(
            query=f"ATS score for {resume_text[:100]}",
            category="ats",
            prompt_id="ats_score",
            template_vars=template_vars,
            top_k=20,
            top_n=10,
        )

        # Validate ATS-specific output — pass actual citations
        validator = get_output_validator()
        report = validator.validate(
            response=response.data,
            expected_keys=ATS_EXPECTED_KEYS,
            citations=list(response.citations) if response.citations else [],
        )
        if not report.valid:
            logger.warning(
                f"ATS output validation failed: {report.malformed_sections}"
            )

        return response

    def _extract_tech(self, resume: str, job: str) -> str:
        import re
        combined = (resume + " " + job).lower()
        tech = set(re.findall(
            r"\b(?:react|angular|vue|typescript|javascript|python|java|golang|rust|"
            r"aws|azure|gcp|kubernetes|docker|terraform|postgresql|mysql|mongo|redis|"
            r"graphql|rest|grpc|kafka|langgraph|langchain|mcp|llm|pytorch|tensorflow|"
            r"fastapi|django|spring|node\.?js|\.net|c#|scikit-learn|pandas|numpy|"
            r"ci/cd|jenkins|github actions|argocd|prometheus|grafana|elasticsearch|"
            r"spark|hadoop|airflow|databricks|snowflake|k8s|next\.js|nuxt)\b",
            combined
        ))
        return ", ".join(sorted(tech))


_atssvc: Optional[ATSScoringService] = None


def get_ats_scoring_service() -> ATSScoringService:
    global _atssvc
    if _atssvc is None:
        _atssvc = ATSScoringService()
    return _atssvc


def reset_ats_scoring_service() -> None:
    global _atssvc
    _atssvc = None


def __getattr__(name: str):
    if name == "ats_scoring_service":
        return get_ats_scoring_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
