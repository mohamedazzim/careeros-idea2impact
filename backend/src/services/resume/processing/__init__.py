"""
Resume processing pipelines module.
Modular pipeline architecture for resume processing.
Designed for LangGraph node extraction.
"""
from .interfaces import (
    ProcessingStatus,
    ProcessingState,
    PipelineConfig,
    ParseResult,
    ExtractionResult,
    MaskingResult,
    ChunkResult,
    NormalizationResult,
    EmbeddingResult,
    PipelineError,
    RetryablePipelineError,
    PermanentPipelineError,
    DocumentParser,
    EntityExtractor,
    PIIMasker,
    SemanticChunker,
    ContentNormalizer,
    EmbeddingGenerator,
    MaskingPolicy,
    MaskingStrategy,
    MaskedEntity,
    MaskingAuditReport,
    SemanticChunk,
    SectionBoundary,
    ChunkingStrategy,
    ResumeSection,
    NormalizationMetrics,
    EmbeddingPayload,
    EmbeddingBatch,
)
from .parser import parser_pipeline, ParserPipeline
from .mime_detector import mime_detector, MimeDetectorPipeline
from .ocr_pipeline import ocr_pipeline, OcrPipeline
from .extraction_pipeline import extraction_pipeline, ExtractionPipeline
from .masking_pipeline import masking_pipeline, MaskingPipeline
from .normalization_pipeline import normalization_pipeline, NormalizationPipeline
from .chunking_pipeline import chunking_pipeline, ChunkingPipeline
from .embedding_preparation import embedding_preparation_pipeline, EmbeddingPreparationPipeline
from .indexing_pipeline import indexing_pipeline, IndexingPipeline
from .embedding_pipeline import embedding_pipeline, EmbeddingPipeline
from .status_pipeline import status_pipeline, StatusPipeline
from .orchestration import (
    processing_orchestrator,
    ProcessingOrchestrator,
    create_orchestrator,
)

__all__ = [
    # Interfaces
    "ProcessingStatus",
    "ProcessingState",
    "PipelineConfig",
    "ParseResult",
    "ExtractionResult",
    "MaskingResult",
    "ChunkResult",
    "NormalizationResult",
    "EmbeddingResult",
    "PipelineError",
    "RetryablePipelineError",
    "PermanentPipelineError",
    # Protocols
    "DocumentParser",
    "EntityExtractor",
    "PIIMasker",
    "SemanticChunker",
    "ContentNormalizer",
    "EmbeddingGenerator",
    # Phase 2C Types
    "MaskingPolicy",
    "MaskingStrategy",
    "MaskedEntity",
    "MaskingAuditReport",
    "SemanticChunk",
    "SectionBoundary",
    "ChunkingStrategy",
    "ResumeSection",
    "NormalizationMetrics",
    "EmbeddingPayload",
    "EmbeddingBatch",
    # Pipelines
    "parser_pipeline",
    "ParserPipeline",
    "mime_detector",
    "MimeDetectorPipeline",
    "ocr_pipeline",
    "OcrPipeline",
    "extraction_pipeline",
    "ExtractionPipeline",
    "masking_pipeline",
    "MaskingPipeline",
    "normalization_pipeline",
    "NormalizationPipeline",
    "chunking_pipeline",
    "ChunkingPipeline",
    "embedding_preparation_pipeline",
    "EmbeddingPreparationPipeline",
    "indexing_pipeline",
    "IndexingPipeline",
    "embedding_pipeline",
    "EmbeddingPipeline",
    "status_pipeline",
    "StatusPipeline",
    # Orchestration
    "processing_orchestrator",
    "ProcessingOrchestrator",
    "create_orchestrator",
]
