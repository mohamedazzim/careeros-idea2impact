"""
Reasoning trace builder — explainability engine for intelligence outputs.

Builds deterministic reasoning chains showing how each score was derived
from retrieval evidence, through Claude reasoning, to final output.

Stateless, async-safe, observable.
"""
import logging
from typing import Dict, Any, List, Optional

from src.schemas.retrieval import Citation, FusedResult

logger = logging.getLogger(__name__)


class ReasoningTraceBuilder:
    """Builds explainable reasoning traces for ATS and intelligence outputs."""

    def build_trace(
        self,
        query: str,
        context: str,
        citations: List[Citation],
        fused: List[FusedResult],
        claude_output: Dict[str, Any],
        confidence: float = 0.0,
        grounding_score: float = 0.0,
        hallucination_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Construct a full reasoning trace showing the path from evidence to output.

        Returns:
            Dict with query, evidence_chain, reasoning_path, confidence_chain, output.
        """
        evidence_chain = []
        for f in fused[:10]:
            evidence_chain.append({
                "chunk_id": f.chunk_id,
                "text_snippet": f.text[:150],
                "rrf_score": f.rrf_score,
                "dense_score": f.dense_score,
                "sparse_score": f.sparse_score,
                "source": f.source,
            })

        reasoning_path = {
            "pipeline_steps": [
                "query_understanding",
                "hybrid_retrieval",
                "reciprocal_rank_fusion",
                "context_compression",
                "grounding_validation",
                "claude_reasoning",
                "output_validation",
                "hallucination_detection",
                "citation_alignment",
                "confidence_scoring",
            ],
            "retrieval_quality": {
                "dense_results": len([f for f in fused if f.dense_score]),
                "sparse_results": len([f for f in fused if f.sparse_score]),
                "fused_results": len(fused),
                "citations": len(citations),
            },
        }

        confidence_chain = {
            "overall": round(confidence, 4),
            "grounding": round(grounding_score, 4),
            "hallucination": round(hallucination_score, 4),
        }

        return {
            "query": query,
            "evidence_chain": evidence_chain,
            "reasoning_path": reasoning_path,
            "confidence_chain": confidence_chain,
            "output": claude_output,
        }


_trace_builder: Optional[ReasoningTraceBuilder] = None
def get_reasoning_trace_builder() -> ReasoningTraceBuilder:
    global _trace_builder
    if _trace_builder is None: _trace_builder = ReasoningTraceBuilder()
    return _trace_builder
def __getattr__(name: str):
    if name == "reasoning_trace_builder": return get_reasoning_trace_builder()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
