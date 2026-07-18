"""
Production reasoning pipeline: the complete Claude intelligence flow.

Deterministic pipeline flow:
Query → Retrieval → Context Compression → Grounding Validation
→ Prompt Assembly → Claude Reasoning → Output Validation
→ Hallucination Detection → Confidence Scoring → Citation Alignment
→ Final Structured Output

LangGraph-compatible, stateless, async-safe, retry-safe, observable.
"""
import logging
import time
from typing import Dict, Any, Optional

from src.schemas.intelligence import StructuredResponse
from src.services.intelligence.claude_service import get_claude_service, enforce_post_hoc_caps
from src.services.intelligence.prompt_builder import get_prompt_builder
from src.services.intelligence.grounding_guard import get_grounding_guard
from src.services.intelligence.hallucination_guard import get_hallucination_guard
from src.services.intelligence.confidence_engine import get_confidence_engine
from src.services.intelligence.output_validator import get_output_validator
from src.services.intelligence.citation_alignment import get_citation_alignment
from src.services.intelligence.structured_response_builder import get_structured_response_builder
from src.services.intelligence.intelligence_observability import get_intelligence_observability
from src.services.intelligence.response_schema_registry import get_schema
from src.services.context.context_compression_service import get_context_compression_service
from src.services.context.context_assembly_service import get_context_assembly_service
from src.services.retrieval.hybrid_retrieval_service import get_hybrid_retrieval_service
from src.services.retrieval.retrieval_drift_monitor import get_drift_monitor
from src.core.config import settings

logger = logging.getLogger(__name__)


class ReasoningPipeline:
    """Full Claude reasoning pipeline: retrieval → grounding → reasoning → validation.

    LangGraph-compatible: call run(state) to execute as a graph node.
    """

    async def reason(
        self,
        query: str,
        category: str = "ats",
        prompt_id: str = "ats_evaluation",
        output_schema_name: Optional[str] = None,
        template_vars: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
        top_n: int = 10,
    ) -> StructuredResponse:
        """Execute the complete grounded reasoning pipeline.

        Args:
            query: User query or intent
            category: Prompt category
            prompt_id: Specific prompt identifier
            output_schema_name: Pydantic schema name for structured output
            template_vars: Variables for prompt template
            top_k: Retrieval candidate pool size
            top_n: Final result count

        Returns:
            StructuredResponse with data, claims, metadata, and evidence
        """
        overall_start = time.monotonic()
        obs = get_intelligence_observability()

        # ── Step 1: Retrieval ───────────────────────────────────────
        hybrid = get_hybrid_retrieval_service()
        retrieval_result = await hybrid.retrieve(
            query=query,
            top_k=top_k,
            top_n=top_n,
            use_hybrid=True,
        )

        # ── Step 2: Context Compression ─────────────────────────────
        compression = get_context_compression_service()
        compressed = await compression.compress(
            chunks=retrieval_result.fused_results,
            max_tokens=settings.CONTEXT_MAX_TOKENS,
        )
        fused_chunks = compressed.chunks

        # ── Step 3: Assembly ────────────────────────────────────────
        assembly = get_context_assembly_service()
        assembled = await assembly.assemble(
            chunks=fused_chunks,
            query=query,
        )
        context = assembled.context
        citations = assembled.citations

        # ── Step 4: Grounding Validation ────────────────────────────
        grounding = get_grounding_guard()
        grounding_report = grounding.verify(
            context=context,
            citations=citations,
        )

        if grounding_report.rejected:
            logger.warning(
                f"Reasoning rejected by grounding guard: {grounding_report.rejection_reason}"
            )
            builder = get_structured_response_builder()
            return await builder.build_rejected(
                response_type=category,
                reason=grounding_report.rejection_reason,
                metadata={
                    "grounding_score": grounding_report.grounding_score,
                    "num_evidence_chunks": len(fused_chunks),
                    "num_citations_used": len(citations),
                    "total_latency_ms": round((time.monotonic() - overall_start) * 1000, 2),
                },
            )

        # ── Step 5: Prompt Assembly ─────────────────────────────────
        prompt_builder = get_prompt_builder()
        prompt = await prompt_builder.build(
            category=category,
            prompt_id=prompt_id,
            template_vars=template_vars or {},
            retrieval_context=context,
            citations=citations,
        )

        # ── Step 6: Claude Reasoning ────────────────────────────────
        claude = get_claude_service()
        output_schema = None
        if output_schema_name:
            output_schema = get_schema(output_schema_name)

        claude_result = await claude.reason(
            system_prompt=prompt["system_prompt"],
            human_message=prompt["human_message"],
            output_schema=output_schema,
            category=category,
        )

        claude_data = claude_result["result"]

        # Post-hoc structural enforcement: truncate outputs to hard caps
        if prompt_id in ("roadmap_generation", "recommendation_advanced",
                         "opportunity_prioritization", "interview_simulation"):
            claude_data = enforce_post_hoc_caps(prompt_id, claude_data)

        # ── Step 7: Output Validation ───────────────────────────────
        validator = get_output_validator()
        validation_report = validator.validate(
            response=claude_data if isinstance(claude_data, dict) else {},
            citations=citations,
        )

        # Repair if needed
        if not validation_report.valid and isinstance(claude_data, str):
            repaired = validator.repair_json(claude_data)
            if repaired:
                claude_data = repaired
                validation_report = validator.validate(
                    response=claude_data,
                    citations=citations,
                )

        # ── Step 8: Hallucination Detection ─────────────────────────
        hg = get_hallucination_guard()
        hall_report = hg.detect(
            response=claude_data if isinstance(claude_data, dict) else {},
            context=context,
        )
        claude_data = hg.mitigate(claude_data, hall_report)

        # ── Step 9: Citation Alignment ──────────────────────────────
        alignment = get_citation_alignment()
        raw_claims = alignment.extract_claims(
            claude_data if isinstance(claude_data, dict) else {}
        )
        grounded_claims = alignment.align(raw_claims, context, citations)
        unsupported = alignment.detect_unsupported(
            claude_data if isinstance(claude_data, dict) else {},
            context,
        )

        # ── Step 10: Confidence Scoring ─────────────────────────────
        drift_monitor = get_drift_monitor()
        drift_state = drift_monitor.get_drift_state()
        confidence = get_confidence_engine()
        confidence_breakdown = confidence.score(
            retrieval_metrics=retrieval_result.metrics,
            fused_results=retrieval_result.fused_results,
            citations=citations,
            context=context,
            hallucination_score=hall_report.hallucination_score,
            validation_score=validation_report.validation_score,
            drift_status=drift_state,
        )

        # ── Step 11: Build Structured Response ──────────────────────
        elapsed = round((time.monotonic() - overall_start) * 1000, 2)
        metadata = obs.build_response_metadata(
            claude_result=claude_result,
            grounding_score=grounding_report.grounding_score,
            hallucination_score=hall_report.hallucination_score,
            confidence=confidence_breakdown.overall,
            validation_passed=validation_report.valid,
        )
        metadata["num_evidence_chunks"] = len(fused_chunks)
        metadata["num_citations_used"] = len(citations)
        metadata["retrieval_collection"] = retrieval_result.metrics.get("collection", "")
        metadata["total_latency_ms"] = elapsed

        obs.record_claude_call(
            model=settings.CLAUDE_MODEL,
            status="success",
            latency_ms=claude_result.get("latency_ms", 0),
            tokens_in=claude_result.get("tokens", {}).get("input", 0),
            tokens_out=claude_result.get("tokens", {}).get("output", 0),
            cost_usd=claude_result.get("cost", 0),
        )
        obs.record_grounding(grounding_report.grounding_score)
        obs.record_hallucination(hall_report.hallucination_score)
        obs.record_confidence(
            confidence_breakdown.overall,
            {
                "retrieval_quality": confidence_breakdown.retrieval_quality,
                "rerank_quality": confidence_breakdown.rerank_quality,
                "citation_coverage": confidence_breakdown.citation_coverage,
                "evidence_density": confidence_breakdown.evidence_density,
                "hallucination_inverted": confidence_breakdown.hallucination_risk_inverted,
                "validation": confidence_breakdown.output_validation_score,
            },
        )

        builder = get_structured_response_builder()
        response = await builder.build(
            response_type=category,
            claude_data=claude_data if isinstance(claude_data, dict) else {"raw": claude_data},
            metadata=metadata,
            claims=grounded_claims,
            unsupported=unsupported,
        )

        logger.info(
            f"Reasoning completed: {category}/{prompt_id} "
            f"({elapsed}ms, confidence={confidence_breakdown.overall:.2%}, "
            f"grounding={grounding_report.grounding_score:.2%})"
        )

        return response

    # ── LangGraph Node Interface ─────────────────────────────────────

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph node entry point for reasoning pipeline.

        Expects: query, category, prompt_id, template_vars in state.
        Returns: intelligence_result, structured_response in state.
        """
        query = state.get("query") or state.get("job_data", {}).get("description", "")
        category = state.get("intelligence_category", "ats")
        prompt_id = state.get("intelligence_prompt_id", "ats_evaluation")
        template_vars = state.get("intelligence_template_vars", {})

        if not query:
            return {
                "intelligence_error": "No query provided",
                "intelligence_status": "error",
            }

        try:
            response = await self.reason(
                query=query,
                category=category,
                prompt_id=prompt_id,
                output_schema_name=state.get("output_schema_name"),
                template_vars=template_vars,
                top_k=state.get("retrieval_top_k", 20),
                top_n=state.get("retrieval_top_n", 10),
            )

            return {
                "intelligence_result": response.data,
                "structured_response": response.model_dump(),
                "intelligence_claims": [c.model_dump() for c in response.claims],
                "intelligence_confidence": response.metadata.confidence_overall,
                "intelligence_status": "success",
                "intelligence_error": None,
            }

        except Exception as e:
            logger.error(f"Reasoning pipeline failed: {e}")
            return {
                "intelligence_result": None,
                "intelligence_error": str(e),
                "intelligence_status": "error",
            }


_pipeline: Optional[ReasoningPipeline] = None


def get_reasoning_pipeline() -> ReasoningPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ReasoningPipeline()
    return _pipeline


def reset_reasoning_pipeline() -> None:
    global _pipeline
    _pipeline = None


def __getattr__(name: str):
    if name == "reasoning_pipeline":
        return get_reasoning_pipeline()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
