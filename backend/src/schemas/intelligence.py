"""
Phase 4A: Intelligence response schemas for Claude orchestration.

Defines the structured output contracts for grounded reasoning,
confidence scoring, hallucination detection, and response validation.

Stateless, pydantic-validated, JSON-safe.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


# ── Core Intelligence Response ──────────────────────────────────────

class EvidenceReference(BaseModel):
    """A single piece of retrieved evidence supporting a claim."""
    citation_id: int
    source: str = ""
    chunk_id: Optional[str] = None
    snippet: str = ""


class GroundedClaim(BaseModel):
    """A claim grounded in retrieved evidence."""
    claim: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: List[EvidenceReference] = Field(default_factory=list)
    unsupported: bool = False


class IntelligenceMetadata(BaseModel):
    """Per-response metadata for traceability and governance."""
    prompt_version: str = "v1"
    model: str = "claude-sonnet-4-20250514"
    retrieval_collection: str = ""
    grounding_score: float = Field(default=0.0, ge=0.0, le=1.0)
    hallucination_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_overall: float = Field(default=0.0, ge=0.0, le=1.0)
    num_evidence_chunks: int = 0
    num_citations_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    validation_passed: bool = True


class StructuredResponse(BaseModel):
    """Top-level container for all Claude-generated structured outputs."""
    response_type: str = ""  # "ats_evaluation", "recommendation", "interview_analysis", etc.
    data: Dict[str, Any] = Field(default_factory=dict)
    claims: List[GroundedClaim] = Field(default_factory=list)
    unsupported_statements: List[str] = Field(default_factory=list)
    metadata: IntelligenceMetadata = Field(default_factory=IntelligenceMetadata)


# ── Grounding Report ────────────────────────────────────────────────

class GroundingReport(BaseModel):
    """Report from the grounding guard validation pass."""
    passed: bool = False
    evidence_present: bool = False
    total_claims: int = 0
    supported_claims: int = 0
    unsupported_claims: int = 0
    grounding_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rejected: bool = False
    rejection_reason: str = ""
    weak_claims: List[Dict[str, Any]] = Field(default_factory=list)


# ── Hallucination Report ────────────────────────────────────────────

class HallucinationReport(BaseModel):
    """Report from the hallucination guard."""
    hallucination_detected: bool = False
    risk_level: str = "none"  # "none", "low", "medium", "high", "critical"
    unsupported_technologies: List[str] = Field(default_factory=list)
    fabricated_metrics: List[str] = Field(default_factory=list)
    invented_chronology: List[str] = Field(default_factory=list)
    unsupported_recommendations: List[str] = Field(default_factory=list)
    evidence_gaps: List[str] = Field(default_factory=list)
    hallucination_score: float = Field(default=0.0, ge=0.0, le=1.0)


# ── Confidence Breakdown ────────────────────────────────────────────

class ConfidenceBreakdown(BaseModel):
    """Multi-factor confidence decomposition."""
    retrieval_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    rerank_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_density: float = Field(default=0.0, ge=0.0, le=1.0)
    context_overlap_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    hallucination_risk_inverted: float = Field(default=0.0, ge=0.0, le=1.0)
    output_validation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    retrieval_drift_inverted: float = Field(default=0.0, ge=0.0, le=1.0)
    overall: float = Field(default=0.0, ge=0.0, le=1.0)


# ── Output Validation Report ────────────────────────────────────────

class ValidationReport(BaseModel):
    """Report from the output validator."""
    valid: bool = False
    schema_compliant: bool = False
    json_parsed: bool = False
    json_repaired: bool = False
    citations_valid: bool = False
    confidence_in_range: bool = False
    missing_evidence_refs: int = 0
    malformed_sections: List[str] = Field(default_factory=list)
    repair_attempts: int = 0
    validation_score: float = Field(default=0.0, ge=0.0, le=1.0)


# ── Prompt Version Record ───────────────────────────────────────────

class PromptVersion(BaseModel):
    """Versioned prompt record for governance."""
    prompt_id: str
    category: str  # "ats", "scoring", "recommendation", "interview", "reasoning", "governance"
    version: str  # Semver-like: "1.0.0"
    system_prompt: str
    human_template: str
    output_schema: str  # Reference to schema type
    parent_version: Optional[str] = None
    created_at: str = ""
    change_description: str = ""
    active: bool = True
    metrics: Dict[str, Any] = Field(default_factory=dict)
