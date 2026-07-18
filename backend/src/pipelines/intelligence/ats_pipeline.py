"""
ATS scoring pipeline — LangGraph-compatible ATS evaluation node.

Evaluates resume against job using 14 category ATS scoring,
all grounded in retrieval evidence.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import logging
from typing import Dict, Any

from src.services.intelligence.ats_scoring_service import get_ats_scoring_service
from src.services.intelligence.score_calibration import get_score_calibration
from src.services.intelligence.evidence_scorer import get_evidence_scorer
from src.services.intelligence.intelligence_metrics import get_intelligence_metrics

logger = logging.getLogger(__name__)


class ATSPipeline:
    """LangGraph-compatible ATS evaluation pipeline node."""

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        resume_text = state.get("resume_text") or state.get("resume_data", {}).get("text", "")
        job_text = state.get("job_text") or state.get("job_data", {}).get("description", "")

        if not resume_text or not job_text:
            return {"ats_error": "Missing resume_text or job_text", "ats_status": "error"}

        try:
            service = get_ats_scoring_service()
            result = await service.evaluate(
                resume_text=resume_text,
                job_text=job_text,
                resume_id=state.get("resume_id"),
                user_id=state.get("user_id"),
            )

            calibration = get_score_calibration()
            cat_scores = result.data.get("category_scores", {})
            calibrated = calibration.calibrate(cat_scores)
            overall = calibration.compute_overall(calibrated)

            evidence = get_evidence_scorer()
            enriched = evidence.annotate_scores(
                calibrated,
                result.metadata.num_evidence_chunks,
                [],
            )

            metrics = get_intelligence_metrics()
            metrics.record_evaluation(
                category="ats",
                duration_ms=result.metadata.total_latency_ms,
                tokens_in=result.metadata.prompt_tokens,
                tokens_out=result.metadata.completion_tokens,
                confidence=result.metadata.confidence_overall,
                grounding=result.metadata.grounding_score,
                hallucination=result.metadata.hallucination_score,
                validation_ok=result.metadata.validation_passed,
            )

            return {
                "ats_result": result.model_dump(),
                "ats_overall_score": overall,
                "ats_category_scores": calibrated,
                "ats_enriched": enriched,
                "ats_confidence": result.metadata.confidence_overall,
                "ats_status": "success",
                "ats_error": None,
            }

        except Exception as e:
            logger.error(f"ATS pipeline failed: {e}")
            return {"ats_error": str(e), "ats_status": "error"}


_pipeline: ATSPipeline | None = None


def get_ats_pipeline() -> ATSPipeline:
    global _pipeline
    if _pipeline is None: _pipeline = ATSPipeline()
    return _pipeline


def __getattr__(name: str):
    if name == "ats_pipeline": return get_ats_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
