"""
Phase 3A core tests — services and pipelines with proper mocking.
"""
import json
import time
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.embedding.embedding_service import EmbeddingService
from src.schemas.retrieval import RetrievedChunk, RerankedChunk, RetrievalResult
from src.services.resume.processing.interfaces import EmbeddingPayload, EmbeddingBatch, EmbeddingResult

DIMS = 4096


# ══════════════════════ EMBEDDING PAYLOAD & PROPS ═══════════════════════

def test_embed_payload_generation():
    svc = EmbeddingService()
    p = svc.generate_payload("raw", "Work experience: raw", 0, 42, "user_1", 1,
                             metadata={"section": "experience"},
                             retrieval_metadata={"retrieval_score": 0.95})
    assert p["user_id"] == "user_1"
    assert p["resume_id"] == 42
    assert p["version_num"] == 1
    assert p["chunk_index"] == 0
    assert p["text"] == "raw"
    assert p["embedding_text"] == "Work experience: raw"
    assert p["model"] == "nvidia/nv-embed-v1"
    assert p["dimensions"] == 4096
    assert p["metadata"]["section"] == "experience"
    assert p["retrieval_metadata"]["retrieval_score"] == 0.95


def test_embed_properties():
    svc = EmbeddingService()
    assert svc.dimensions == 4096
    assert "nv-embed" in svc.model_name.lower()


def test_embed_cache_key():
    svc = EmbeddingService()
    key = svc._cache_key("hello world")
    assert key.startswith("embed:")
    assert "nvidia" in key
    assert len(key) > 50


# ══════════════════════ QDRANT SERVICE FILTERS ═════════════════════════

def test_build_filter_exact_match():
    from src.services.vector_store.qdrant_service import QdrantService
    svc = QdrantService()
    f = svc._build_filter({"user_id": "test123"})
    assert f is not None


def test_build_filter_multi_value():
    from src.services.vector_store.qdrant_service import QdrantService
    svc = QdrantService()
    f = svc._build_filter({"section": ["experience", "skills"]})
    assert f is not None


def test_build_filter_range():
    from src.services.vector_store.qdrant_service import QdrantService
    svc = QdrantService()
    f = svc._build_filter({"chunk_index": {"gte": 0, "lte": 10}})
    assert f is not None


def test_build_filter_none_skipped():
    from src.services.vector_store.qdrant_service import QdrantService
    svc = QdrantService()
    f = svc._build_filter({"user_id": None, "resume_id": 1})
    assert f is not None


def test_build_filter_empty():
    from src.services.vector_store.qdrant_service import QdrantService
    svc = QdrantService()
    assert QdrantService()._build_filter({}) is None


def test_qdrant_validate_required_fields():
    from src.services.vector_store.qdrant_service import QdrantService, RESUME_REQUIRED_FIELDS
    assert "text" in RESUME_REQUIRED_FIELDS
    assert "chunk_index" in RESUME_REQUIRED_FIELDS
    assert "version_num" in RESUME_REQUIRED_FIELDS


# ══════════════════════ MASKING PIPELINE AUDIT ═════════════════════════

def test_masking_policy():
    from src.services.resume.processing.interfaces import MaskingPolicy, MaskingStrategy
    policy = MaskingPolicy(
        entity_types=["EMAIL", "PHONE"],
        strategy=MaskingStrategy.TOKEN,
        min_confidence=0.5,
    )
    assert policy.strategy == MaskingStrategy.TOKEN
    assert "EMAIL" in policy.entity_types
    assert policy.min_confidence == 0.5


def test_masking_audit_report():
    from src.services.resume.processing.interfaces import MaskingAuditReport, MaskedEntity
    entities = [
        MaskedEntity(
            entity_type="EMAIL",
            original_text="test@example.com",
            masked_text="[MASKED_EMAIL]",
            start_char=10, end_char=27,
            confidence=0.95, source="regex",
            replacement_method="token",
        )
    ]
    report = MaskingAuditReport(
        total_entities=1,
        entities_by_type={"EMAIL": 1},
        entities_by_source={"regex": 1},
        avg_confidence=0.95,
        min_confidence=0.95,
        max_confidence=0.95,
        masked_entities=entities,
        unmasked_low_confidence=[],
    )
    d = report.to_dict()
    assert d["total_entities"] == 1
    assert d["entities_by_type"]["EMAIL"] == 1
    assert abs(d["avg_confidence"] - 0.95) < 0.01


# ══════════════════════ CHUNKING STRATEGY ═══════════════════════════

def test_chunking_strategy_defaults():
    from src.services.resume.processing.interfaces import ChunkingStrategy
    cfg = ChunkingStrategy()
    assert cfg.max_chunk_tokens == 512
    assert cfg.min_chunk_tokens == 100
    assert cfg.overlap_tokens == 50
    assert cfg.preserve_section_boundaries is True
    assert cfg.preserve_sentence_boundaries is True


def test_chunking_strategy_custom():
    from src.services.resume.processing.interfaces import ChunkingStrategy
    cfg = ChunkingStrategy(
        max_chunk_tokens=256,
        overlap_tokens=30,
        preserve_section_boundaries=False,
    )
    assert cfg.max_chunk_tokens == 256
    assert cfg.overlap_tokens == 30
    assert cfg.preserve_section_boundaries is False


# ══════════════════════ EMBEDDING BATCH ══════════════════════════════

def test_embedding_batch():
    payload = EmbeddingPayload(
        chunk_id="abc123",
        text="Experience at Google",
        embedding_text="Work experience: Experience at Google",
        input_type="passage",
        metadata={"section": "experience"},
        retrieval_metadata={"retrieval_score": 0.9},
    )
    batch = EmbeddingBatch(
        payloads=[payload],
        batch_id="batch-1",
        total_chunks=1,
        total_tokens=15,
        avg_chunk_tokens=15.0,
        section_distribution={"experience": 1},
        retrieval_strategy="semantic",
    )
    d = batch.to_dict()
    assert d["total_chunks"] == 1
    assert d["retrieval_strategy"] == "semantic"
    assert d["section_distribution"]["experience"] == 1


# ══════════════════════ RETRIEVAL SCHEMA ═════════════════════════════

def test_retrieved_chunk():
    rc = RetrievedChunk(
        id="r1",
        document_id="resume_1",
        chunk_id="c1",
        text="Python experience at Google",
        score=0.95,
        source="resume",
        metadata={"section": "experience"},
    )
    assert rc.score == 0.95
    assert rc.text == "Python experience at Google"


def test_reranked_chunk():
    rc = RerankedChunk(
        id="r1",
        text="text",
        score=0.95,
        rerank_score=0.97,
        metadata={},
    )
    assert rc.rerank_score > rc.score


def test_retrieval_result():
    result = RetrievalResult(
        query="test",
        retrieved_chunks=[],
        reranked_chunks=[],
        context="",
        citations=[],
        metrics={"total_latency_ms": 20.0},
    )
    assert result.metrics["total_latency_ms"] == 20.0


# ══════════════════════ VECTOR PAYLOADS ══════════════════════════════

def test_resume_payload():
    from src.schemas.vector_payloads import ResumePayload
    p = ResumePayload(
        user_id="u1",
        resume_id=5,
        version_num=1,
        chunk_index=0,
        text="Resume text",
        start_char=0,
        end_char=12,
    )
    assert p.user_id == "u1"
    assert p.resume_id == 5
    assert p.version_num == 1


def test_job_payload():
    from src.schemas.vector_payloads import JobPayload
    p = JobPayload(
        job_id="job-1",
        company="Google",
        title="SWE",
        text="Job description",
    )
    assert p.job_id == "job-1"


def test_knowledge_payload():
    from src.schemas.vector_payloads import KnowledgePayload
    p = KnowledgePayload(
        document_id="doc-1",
        category="best_practices",
        text="Content",
    )
    assert p.category == "best_practices"


# ══════════════════════ PIPELINE CONFIG ══════════════════════════════

def test_pipeline_config_defaults():
    from src.services.resume.processing.interfaces import PipelineConfig
    cfg = PipelineConfig()
    assert cfg.enable_normalization is True
    assert cfg.enable_chunking is True
    assert cfg.enable_masking is True
    assert cfg.enable_gliner is True
    assert cfg.enable_embedding_prep is True


def test_processing_status():
    from src.services.resume.processing.interfaces import ProcessingStatus
    assert ProcessingStatus.PENDING.value == "pending"
    assert ProcessingStatus.COMPLETED.value == "completed"
    assert ProcessingStatus.PREPARING.value == "preparing"


# ══════════════════════ SECTION BOUNDARY ═════════════════════════════

def test_section_boundary():
    from src.services.resume.processing.interfaces import SectionBoundary
    sb = SectionBoundary(
        name="EXPERIENCE",
        normalized_name="experience",
        start_line=5,
        end_line=20,
        heading_level=1,
        char_start=100,
        char_end=500,
        confidence=0.95,
    )
    d = sb.to_dict()
    assert d["normalized_name"] == "experience"
    assert d["confidence"] == 0.95
    assert d["char_start"] == 100


# ══════════════════════ SEMANTIC CHUNK ═══════════════════════════════

def test_semantic_chunk():
    from src.services.resume.processing.interfaces import SemanticChunk
    sc = SemanticChunk(
        chunk_id="abc",
        text="Work text",
        char_start=0,
        char_end=9,
        section="experience",
        chunk_type="section_content",
        token_count=12,
        word_count=8,
        sentence_count=1,
        overlap_with_previous=False,
        overlap_with_next=True,
        metadata={"section_confidence": 0.9},
    )
    d = sc.to_dict()
    assert d["section"] == "experience"
    assert d["token_count"] == 12
    assert d["overlap_with_next"] is True
