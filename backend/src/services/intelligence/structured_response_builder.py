"""
Structured response builder for Claude intelligence outputs.

Transforms raw Claude results into governance-ready structured responses
with metadata, citations, and evidence references.

Stateless, async-safe, observable. Worker-safe.
"""
import logging
from typing import Dict, Any, List, Optional

from src.schemas.intelligence import (
    StructuredResponse,
    IntelligenceMetadata,
    GroundedClaim,
)

logger = logging.getLogger(__name__)


class StructuredResponseBuilder:
    """Builds governance-ready structured responses from Claude outputs."""

    async def build(
        self,
        response_type: str,
        claude_data: Dict[str, Any],
        metadata: Dict[str, Any],
        claims: Optional[List[GroundedClaim]] = None,
        unsupported: Optional[List[str]] = None,
    ) -> StructuredResponse:
        """Construct a structured response with all metadata and evidence references."""
        meta = IntelligenceMetadata(
            prompt_version=metadata.get("prompt_version", "v1"),
            model=metadata.get("model", "claude-sonnet-4-20250514"),
            retrieval_collection=metadata.get("retrieval_collection", ""),
            grounding_score=metadata.get("grounding_score", 0.0),
            hallucination_score=metadata.get("hallucination_score", 0.0),
            confidence_overall=metadata.get("confidence_overall", 0.0),
            num_evidence_chunks=metadata.get("num_evidence_chunks", 0),
            num_citations_used=metadata.get("num_citations_used", 0),
            prompt_tokens=metadata.get("prompt_tokens", 0),
            completion_tokens=metadata.get("completion_tokens", 0),
            estimated_cost_usd=metadata.get("estimated_cost_usd", 0.0),
            total_latency_ms=metadata.get("total_latency_ms", 0.0),
            validation_passed=metadata.get("validation_passed", True),
        )

        return StructuredResponse(
            response_type=response_type,
            data=claude_data,
            claims=claims or [],
            unsupported_statements=unsupported or [],
            metadata=meta,
        )

    async def build_error(
        self,
        response_type: str,
        error: str,
    ) -> StructuredResponse:
        """Build an error response with zero confidence."""
        return StructuredResponse(
            response_type=response_type,
            data={"error": error},
            claims=[],
            unsupported_statements=[],
            metadata=IntelligenceMetadata(
                prompt_version="error",
                grounding_score=0.0,
                hallucination_score=1.0,
                confidence_overall=0.0,
                validation_passed=False,
            ),
        )

    async def build_rejected(
        self,
        response_type: str,
        reason: str,
        metadata: Dict[str, Any],
    ) -> StructuredResponse:
        """Build a response rejected due to insufficient grounding."""
        return StructuredResponse(
            response_type=response_type,
            data={"rejection_reason": reason},
            claims=[],
            unsupported_statements=[],
            metadata=IntelligenceMetadata(
                prompt_version=metadata.get("prompt_version", "v1"),
                grounding_score=0.0,
                hallucination_score=0.0,
                confidence_overall=0.0,
                validation_passed=False,
                **{k: metadata.get(k, 0) for k in [
                    "num_evidence_chunks", "num_citations_used",
                    "prompt_tokens", "completion_tokens",
                    "total_latency_ms",
                ]},
            ),
        )


_builder: Optional[StructuredResponseBuilder] = None


def get_structured_response_builder() -> StructuredResponseBuilder:
    global _builder
    if _builder is None:
        _builder = StructuredResponseBuilder()
    return _builder


def reset_structured_response_builder() -> None:
    global _builder
    _builder = None


def __getattr__(name: str):
    if name == "structured_response_builder":
        return get_structured_response_builder()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
