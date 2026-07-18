from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum


class RetrievedChunk(BaseModel):
    id: str
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    text: str
    score: float
    source: Optional[str] = None
    metadata: Dict[str, Any] = {}


class RerankedChunk(RetrievedChunk):
    rerank_score: float


class Citation(BaseModel):
    citation_id: int
    source: Optional[str] = None
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None


class RetrievalResult(BaseModel):
    query: str
    retrieved_chunks: List[RetrievedChunk]
    reranked_chunks: List[RerankedChunk]
    context: str
    citations: List[Citation]
    metrics: Dict[str, Any] = {}


# ── Phase 3B: Hybrid Retrieval Schemas ──────────────────────────────

class FusionMethod(str, Enum):
    RRF = "rrf"
    WEIGHTED_SUM = "weighted_sum"
    RANK_COMBINATION = "rank_combination"


class SparseRetrievalResult(BaseModel):
    """Single result from BM25 / sparse retrieval."""
    chunk_id: str
    text: str
    score: float
    rank: int
    token_matches: int = 0
    matched_tokens: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SparseRetrievalResponse(BaseModel):
    query: str
    results: List[SparseRetrievalResult]
    total_indexed: int
    query_tokens: List[str]
    latency_ms: float


class FusedResult(BaseModel):
    """Result from reciprocal rank fusion."""
    chunk_id: str
    text: str
    rrf_score: float
    dense_rank: Optional[int] = None
    dense_score: Optional[float] = None
    sparse_rank: Optional[int] = None
    sparse_score: Optional[float] = None
    metadata_rank: Optional[int] = None
    metadata_score: Optional[float] = None
    fusion_method: str = "rrf"
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HybridRetrievalResult(BaseModel):
    query: str
    dense_results: List[RetrievedChunk]
    sparse_results: List[SparseRetrievalResult]
    fused_results: List[FusedResult]
    reranked_chunks: List[RerankedChunk] = Field(default_factory=list)
    context: str = ""
    citations: List[Citation] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)


# ── Phase 3B: Query Understanding Schemas ───────────────────────────

class QueryIntent(str, Enum):
    ATS_SCORING = "ats_scoring"
    RESUME_ANALYSIS = "resume_analysis"
    JOB_MATCHING = "job_matching"
    INTERVIEW_PREP = "interview_prep"
    RECOMMENDATION = "recommendation"
    RECRUITER_SEARCH = "recruiter_search"
    GENERAL = "general"


class QueryUnderstandingResult(BaseModel):
    original_query: str
    intent: QueryIntent = QueryIntent.GENERAL
    intent_confidence: float = 0.0
    extracted_skills: List[str] = Field(default_factory=list)
    expanded_skills: Dict[str, List[str]] = Field(default_factory=dict)
    tech_stack: List[str] = Field(default_factory=list)
    synonyms: Dict[str, str] = Field(default_factory=dict)
    acronyms_expanded: Dict[str, str] = Field(default_factory=dict)
    expanded_queries: List[str] = Field(default_factory=list)
    spatial_hints: Dict[str, Any] = Field(default_factory=dict)
    retrieval_strategy: str = "semantic"


class RoutingDecision(BaseModel):
    query: str
    target_collections: List[str]
    collection_weights: Dict[str, float]
    routing_confidence: float
    routing_reason: str
    is_federated: bool = False


# ── Phase 3B: Context Compression Schemas ───────────────────────────

class CompressionResult(BaseModel):
    original_chunks: int
    compressed_chunks: int
    original_tokens: int
    compressed_tokens: int
    token_reduction_pct: float
    removed_duplicates: int
    removed_overlaps: int
    compression_ratio: float
    chunks: List[FusedResult]


class AssemblyBlock(BaseModel):
    block_id: int
    text: str
    source: str
    section: str
    relevance_score: float
    rerank_score: Optional[float] = None
    retrieval_reason: str
    chunks: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)


class ContextAssemblyResult(BaseModel):
    context: str
    blocks: List[AssemblyBlock]
    citations: List[Citation]
    total_tokens: int
    token_budget_used_pct: float
    source_count: int
    section_count: int


# ── Phase 3B: Evaluation Schemas ────────────────────────────────────

class RetrievalMetrics(BaseModel):
    recall_at_k: Dict[int, float] = Field(default_factory=dict)
    hit_at_k: Dict[int, float] = Field(default_factory=dict)
    precision_at_k: Dict[int, float] = Field(default_factory=dict)
    mrr: float = 0.0
    ndcg_at_k: Dict[int, float] = Field(default_factory=dict)
    retrieval_consistency: float = 0.0
    hallucination_risk: float = 0.0
    retrieval_drift: float = 0.0


class EvaluationResult(BaseModel):
    query: str
    metrics: RetrievalMetrics
    dense_only_metrics: Dict[str, Any] = Field(default_factory=dict)
    hybrid_metrics: Dict[str, Any] = Field(default_factory=dict)
    hybrid_recall_gain: float = 0.0
    latency_breakdown: Dict[str, float] = Field(default_factory=dict)


class RerankingObservation(BaseModel):
    rerank_latency_ms: float
    rerank_confidence_avg: float
    score_distribution: Dict[str, float] = Field(default_factory=dict)
    rank_correlation: float = 0.0
    rank_inversion_rate: float = 0.0
