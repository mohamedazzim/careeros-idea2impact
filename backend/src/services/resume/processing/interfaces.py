"""
Pipeline interfaces and types.
Defines contracts for all Phase 2C processing pipelines.
Designed for LangGraph node compatibility.
Stateless, async-safe, retry-safe, observable.
"""
from typing import Protocol, Dict, Any, Optional, TypedDict, runtime_checkable, List
from dataclasses import dataclass, field
from enum import Enum


class ProcessingStatus(str, Enum):
    """Processing pipeline statuses."""
    PENDING = "pending"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    OCR = "ocr"
    MASKING = "masking"
    CHUNKING = "chunking"
    NORMALIZING = "normalizing"
    EMBEDDING = "embedding"
    PREPARING = "preparing"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineError(Exception):
    """Base error for pipeline failures."""
    pass


class RetryablePipelineError(PipelineError):
    """Error that can be retried."""
    pass


class PermanentPipelineError(PipelineError):
    """Error that cannot be retried."""
    pass


# ── Masking Policy ──────────────────────────────────────────────────

class MaskingStrategy(str, Enum):
    """Strategies for PII replacement."""
    TOKEN = "token"
    SYNTHETIC = "synthetic"
    REDACT = "redact"
    HASH = "hash"


@dataclass
class MaskingPolicy:
    """Configurable masking rules per entity type."""
    entity_types: List[str] = field(default_factory=lambda: [
        "PERSON", "EMAIL", "PHONE", "ADDRESS", "ORGANIZATION", "URL"
    ])
    strategy: MaskingStrategy = MaskingStrategy.TOKEN
    preserve_format: bool = True
    min_confidence: float = 0.5
    audit_trail: bool = True


@dataclass
class MaskedEntity:
    """Single masked entity record for audit trail."""
    entity_type: str
    original_text: str
    masked_text: str
    start_char: int
    end_char: int
    confidence: float
    source: str
    replacement_method: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "original_text": self.original_text,
            "masked_text": self.masked_text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "confidence": self.confidence,
            "source": self.source,
            "replacement_method": self.replacement_method,
        }


@dataclass
class MaskingAuditReport:
    """Full audit trail for masking operations."""
    total_entities: int
    entities_by_type: Dict[str, int]
    entities_by_source: Dict[str, int]
    avg_confidence: float
    min_confidence: float
    max_confidence: float
    masked_entities: List[MaskedEntity] = field(default_factory=list)
    unmasked_low_confidence: List[MaskedEntity] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_entities": self.total_entities,
            "entities_by_type": self.entities_by_type,
            "entities_by_source": self.entities_by_source,
            "avg_confidence": self.avg_confidence,
            "min_confidence": self.min_confidence,
            "max_confidence": self.max_confidence,
            "masked_entities": [e.to_dict() for e in self.masked_entities],
            "unmasked_low_confidence": [e.to_dict() for e in self.unmasked_low_confidence],
        }


# ── Chunking Types ──────────────────────────────────────────────────

@dataclass
class SectionBoundary:
    """Detected section boundary in resume."""
    name: str
    normalized_name: str
    start_line: int
    end_line: Optional[int] = None
    heading_level: int = 1
    char_start: int = 0
    char_end: int = 0
    confidence: float = 0.9

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "normalized_name": self.normalized_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "heading_level": self.heading_level,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "confidence": self.confidence,
        }


@dataclass
class SemanticChunk:
    """Semantically-aware text chunk."""
    chunk_id: str
    text: str
    char_start: int
    char_end: int
    section: str
    chunk_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    word_count: int = 0
    sentence_count: int = 0
    overlap_with_previous: bool = False
    overlap_with_next: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "section": self.section,
            "chunk_type": self.chunk_type,
            "metadata": self.metadata,
            "token_count": self.token_count,
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "overlap_with_previous": self.overlap_with_previous,
            "overlap_with_next": self.overlap_with_next,
        }


@dataclass
class ChunkingStrategy:
    """Configuration for semantic chunking."""
    max_chunk_tokens: int = 512
    min_chunk_tokens: int = 100
    overlap_tokens: int = 50
    preserve_section_boundaries: bool = True
    preserve_sentence_boundaries: bool = True
    enable_token_counting: bool = True
    section_merge_threshold: int = 256


# ── Normalization Types ─────────────────────────────────────────────

@dataclass
class NormalizationMetrics:
    """Metrics recorded during normalization."""
    whitespace_fixes: int = 0
    unicode_fixes: int = 0
    ocr_fixes: int = 0
    section_headers_detected: int = 0
    bullets_normalized: int = 0
    duplicate_lines_removed: int = 0
    preprocessing_duration_ms: float = 0.0


@dataclass
class ResumeSection:
    """Structured resume section after normalization."""
    section_type: str
    heading: str
    content: str
    normalized_content: str
    char_start: int
    char_end: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    subsections: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_type": self.section_type,
            "heading": self.heading,
            "content": self.content,
            "normalized_content": self.normalized_content,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "metadata": self.metadata,
            "subsections": self.subsections,
        }


# ── Embedding Preparation Types ─────────────────────────────────────

@dataclass
class EmbeddingPayload:
    """Chunk prepared for NV-Embed-v1 ingestion."""
    chunk_id: str
    text: str
    embedding_text: str
    input_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    retrieval_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "embedding_text": self.embedding_text,
            "input_type": self.input_type,
            "metadata": self.metadata,
            "retrieval_metadata": self.retrieval_metadata,
        }


@dataclass
class EmbeddingBatch:
    """Batch of chunks ready for embedding generation."""
    payloads: List[EmbeddingPayload] = field(default_factory=list)
    batch_id: str = ""
    total_chunks: int = 0
    total_tokens: int = 0
    avg_chunk_tokens: float = 0.0
    section_distribution: Dict[str, int] = field(default_factory=dict)
    retrieval_strategy: str = "semantic"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_chunks": self.total_chunks,
            "total_tokens": self.total_tokens,
            "avg_chunk_tokens": self.avg_chunk_tokens,
            "section_distribution": self.section_distribution,
            "retrieval_strategy": self.retrieval_strategy,
            "payloads": [p.to_dict() for p in self.payloads],
        }


# ── Enhanced Result Types ───────────────────────────────────────────

class ProcessingState(TypedDict, total=False):
    """State for LangGraph processing graph.

    Each field represents a checkpoint in the pipeline.
    Phase 2C: Enhanced with all new pipeline outputs.
    """
    resume_id: int
    user_id: str
    filename: str
    storage_path: str
    content_type: Optional[str]

    # Document parsing results
    raw_text: Optional[str]
    parse_error: Optional[str]

    # OCR results
    ocr_text: Optional[str]
    ocr_confidence: Optional[float]
    ocr_error: Optional[str]

    # GLiNER extraction results
    entities: Optional[Dict[str, Any]]
    extraction_error: Optional[str]

    # Masking results (Phase 2C: enhanced with audit trail)
    masked_text: Optional[str]
    masked_entities: Optional[List[Dict[str, Any]]]
    masking_metadata: Optional[Dict[str, Any]]
    masking_error: Optional[str]
    masking_audit: Optional[Dict[str, Any]]

    # Normalization results (Phase 2C: full normalization)
    normalized_text: Optional[str]
    normalized_sections: Optional[List[Dict[str, Any]]]
    normalization_metrics: Optional[Dict[str, Any]]
    normalization_error: Optional[str]

    # Chunking results (Phase 2C: semantic chunking)
    chunks: Optional[List[Dict[str, Any]]]
    semantic_chunks: Optional[List[Dict[str, Any]]]
    section_boundaries: Optional[List[Dict[str, Any]]]
    chunking_error: Optional[str]

    # Embedding preparation results
    embedding_payloads: Optional[List[Dict[str, Any]]]
    embedding_batch: Optional[Dict[str, Any]]
    embedding_error: Optional[str]

    # Pipeline metadata
    version_id: Optional[int]
    status: ProcessingStatus
    error_message: Optional[str]


@dataclass
class ParseResult:
    """Result from document parsing stage."""
    text: str
    content_type: str
    metadata: Dict[str, Any]
    confidence: float = 1.0


@dataclass
class ExtractionResult:
    """Result from entity extraction stage (GLiNER)."""
    entities: Dict[str, List[Dict[str, Any]]]
    entity_count: int
    metadata: Dict[str, Any]


@dataclass
class MaskingResult:
    """Result from PII masking stage - Phase 2C enhanced."""
    masked_text: str
    masked_entities: List[MaskedEntity]
    audit_report: MaskingAuditReport
    original_length: int
    masked_length: int
    strategy: MaskingStrategy = MaskingStrategy.TOKEN


@dataclass
class NormalizationResult:
    """Result from normalization stage - Phase 2C enhanced."""
    normalized_text: str
    sections: List[ResumeSection]
    section_count: int
    metrics: NormalizationMetrics
    metadata: Dict[str, Any]


@dataclass
class ChunkResult:
    """Result from semantic chunking stage - Phase 2C enhanced."""
    chunks: List[SemanticChunk]
    section_boundaries: List[SectionBoundary]
    chunk_count: int
    avg_chunk_size: int
    avg_chunk_tokens: int
    metadata: Dict[str, Any]


@dataclass
class EmbeddingResult:
    """Result from embedding preparation stage."""
    batch: EmbeddingBatch
    vectors: Optional[List[List[float]]] = None
    model: str = "nvidia/nv-embed-v1"
    dimensions: int = 4096
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Protocol Interfaces ─────────────────────────────────────────────

@runtime_checkable
class DocumentParser(Protocol):
    """Protocol for document parsing pipelines."""

    async def parse(self, filename: str, storage_path: str) -> ParseResult:
        """Parse document to extract text."""
        ...


@runtime_checkable
class EntityExtractor(Protocol):
    """Protocol for entity extraction pipelines (GLiNER)."""

    async def extract(self, text: str) -> ExtractionResult:
        """Extract entities from text."""
        ...


@runtime_checkable
class PIIMasker(Protocol):
    """Protocol for PII masking pipelines."""

    async def mask(
        self, text: str, entities: Optional[Dict] = None, policy: Optional[MaskingPolicy] = None
    ) -> MaskingResult:
        """Mask PII in text."""
        ...


@runtime_checkable
class SemanticChunker(Protocol):
    """Protocol for semantic chunking pipelines."""

    async def chunk(
        self, text: str, strategy: Optional[ChunkingStrategy] = None
    ) -> ChunkResult:
        """Chunk text semantically."""
        ...


@runtime_checkable
class ContentNormalizer(Protocol):
    """Protocol for content normalization pipelines."""

    async def normalize(
        self, text: str, entities: Optional[Dict] = None
    ) -> NormalizationResult:
        """Normalize content into structured format."""
        ...


@runtime_checkable
class EmbeddingGenerator(Protocol):
    """Protocol for embedding generation pipelines."""

    async def embed(self, chunks: List[str]) -> EmbeddingResult:
        """Generate embeddings for chunks."""
        ...


# ── Pipeline Configuration ──────────────────────────────────────────

@dataclass
class PipelineConfig:
    """Configuration for processing pipeline execution."""
    enable_ocr: bool = False
    enable_gliner: bool = True
    enable_masking: bool = True
    enable_chunking: bool = True
    enable_normalization: bool = True
    enable_embedding_prep: bool = True
    enable_embedding: bool = False

    # Stage-specific configs
    ocr_confidence_threshold: float = 0.8
    chunk_max_tokens: int = 512
    chunk_overlap_tokens: int = 50
    embedding_model: str = "nvidia/nv-embed-v1"

    # Phase 2C: masking
    masking_strategy: MaskingStrategy = MaskingStrategy.TOKEN
    masking_min_confidence: float = 0.5
    masking_audit_enabled: bool = True

    # Phase 2C: normalization
    normalization_enable_ocr_cleanup: bool = True
    normalization_enable_unicode_cleanup: bool = True
    normalization_section_reconstruction: bool = True
