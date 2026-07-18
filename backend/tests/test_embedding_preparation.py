"""
Tests for the Phase 2C Embedding Preparation pipeline.
Tests: payload generation, metadata enrichment, retrieval optimization,
section weights, NV-Embed-v1 payload format.
"""
import pytest
from src.services.resume.processing.embedding_preparation import (
    EmbeddingPreparationPipeline,
    EmbeddingResult,
    RetryablePipelineError,
)


@pytest.fixture
def pipeline():
    return EmbeddingPreparationPipeline()


@pytest.fixture
def sample_chunks():
    return [
        {
            "text": "Senior Software Engineer at Google from 2015 to 2022.",
            "section": "experience",
            "chunk_type": "section_content",
            "char_start": 0,
            "char_end": 56,
            "word_count": 10,
            "sentence_count": 1,
            "token_count": 15,
            "overlap_with_previous": False,
            "overlap_with_next": True,
            "metadata": {},
        },
        {
            "text": "Python, React, TypeScript, Docker, AWS, Kubernetes",
            "section": "skills",
            "chunk_type": "section_content",
            "char_start": 57,
            "char_end": 109,
            "word_count": 7,
            "sentence_count": 1,
            "token_count": 12,
            "overlap_with_previous": True,
            "overlap_with_next": False,
            "metadata": {},
        },
        {
            "text": "Experienced engineer with 10+ years in ML and cloud infrastructure.",
            "section": "summary",
            "chunk_type": "section_content",
            "char_start": 110,
            "char_end": 185,
            "word_count": 12,
            "sentence_count": 1,
            "token_count": 18,
            "overlap_with_previous": False,
            "overlap_with_next": False,
            "metadata": {"confidence": 0.95},
        },
    ]


# ── Payload Generation ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_payloads_generated(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    assert result.batch.total_chunks == len(sample_chunks)
    assert len(result.batch.payloads) == len(sample_chunks)


@pytest.mark.asyncio
async def test_payloads_have_chunk_id(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    for payload in result.batch.payloads:
        assert payload.chunk_id
        assert len(payload.chunk_id) > 0


@pytest.mark.asyncio
async def test_payloads_have_embedding_text(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    for payload in result.batch.payloads:
        assert payload.embedding_text
        assert len(payload.embedding_text) > 0


@pytest.mark.asyncio
async def test_payloads_input_type_passage(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    for payload in result.batch.payloads:
        assert payload.input_type == "passage"


# ── Metadata Enrichment ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_payloads_have_metadata(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    for payload in result.batch.payloads:
        assert payload.metadata
        assert payload.metadata["resume_id"] == 1
        assert "section" in payload.metadata
        assert "chunk_index" in payload.metadata


@pytest.mark.asyncio
async def test_metadata_includes_char_boundaries(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    for payload in result.batch.payloads:
        assert payload.metadata["char_start"] >= 0
        assert payload.metadata["char_end"] > payload.metadata["char_start"]


# ── Retrieval Optimization Metadata ─────────────────────────────────

@pytest.mark.asyncio
async def test_retrieval_metadata_generated(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    for payload in result.batch.payloads:
        assert payload.retrieval_metadata
        assert "retrieval_score" in payload.retrieval_metadata
        assert "section_weight" in payload.retrieval_metadata
        assert "position_score" in payload.retrieval_metadata


@pytest.mark.asyncio
async def test_retrieval_score_in_range(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    for payload in result.batch.payloads:
        score = payload.retrieval_metadata["retrieval_score"]
        assert 0 <= score <= 1.5


@pytest.mark.asyncio
async def test_skills_higher_weight_than_general(pipeline):
    skills_chunk = [{"text": "Skill text", "section": "skills", "token_count": 5}]
    general_chunk = [{"text": "General text", "section": "general", "token_count": 5}]
    result_skills = await pipeline.prepare(skills_chunk, resume_id=1, user_id="u")
    result_general = await pipeline.prepare(general_chunk, resume_id=2, user_id="u")
    assert (
        result_skills.batch.payloads[0].retrieval_metadata["section_weight"]
        > result_general.batch.payloads[0].retrieval_metadata["section_weight"]
    )


# ── Section Prefix Embedding Enhancement ────────────────────────────

@pytest.mark.asyncio
async def test_embedding_text_has_section_prefix(pipeline):
    chunks = [{"text": "Some text here", "section": "experience", "token_count": 5}]
    result = await pipeline.prepare(chunks, resume_id=1, user_id="u")
    assert result.batch.payloads[0].embedding_text.startswith("Work experience: ")


@pytest.mark.asyncio
async def test_general_section_no_prefix(pipeline):
    chunks = [{"text": "Some text", "section": "general", "token_count": 3}]
    result = await pipeline.prepare(chunks, resume_id=1, user_id="u")
    assert result.batch.payloads[0].embedding_text == "Some text"


# ── Batch Statistics ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_has_statistics(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    assert result.batch.total_chunks > 0
    assert result.batch.total_tokens > 0
    assert result.batch.avg_chunk_tokens > 0
    assert isinstance(result.batch.section_distribution, dict)


@pytest.mark.asyncio
async def test_section_distribution_correct(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    dist = result.batch.section_distribution
    assert dist.get("experience", 0) == 1
    assert dist.get("skills", 0) == 1
    assert dist.get("summary", 0) == 1


@pytest.mark.asyncio
async def test_batch_has_batch_id(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    assert result.batch.batch_id
    assert len(result.batch.batch_id) > 0


# ── Result Structure ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_has_model_info(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    assert result.model == "nvidia/nv-embed-v1"
    assert result.dimensions == 4096


@pytest.mark.asyncio
async def test_result_has_metadata(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="test_user")
    assert result.metadata["resume_id"] == 1
    assert result.metadata["user_id"] == "test_user"
    assert result.metadata["retrieval_strategy"] == "semantic"


@pytest.mark.asyncio
async def test_version_num_passed_through(pipeline, sample_chunks):
    result = await pipeline.prepare(sample_chunks, resume_id=1, user_id="u", version_num=5)
    assert result.metadata["version_num"] == 5
    for payload in result.batch.payloads:
        assert payload.metadata["version_num"] == 5


# ── Edge Cases ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_chunks_raises(pipeline):
    with pytest.raises(RetryablePipelineError):
        await pipeline.prepare([], resume_id=1, user_id="u")


@pytest.mark.asyncio
async def test_single_chunk_works(pipeline):
    chunks = [{"text": "Only chunk.", "section": "general", "token_count": 3}]
    result = await pipeline.prepare(chunks, resume_id=1, user_id="u")
    assert result.batch.total_chunks == 1


@pytest.mark.asyncio
async def test_chunk_ids_are_unique(pipeline):
    chunks = [{"text": "Same text", "section": "general", "token_count": 3} for _ in range(5)]
    for i, c in enumerate(chunks):
        c["text"] = f"Text for chunk {i}"
    result = await pipeline.prepare(chunks, resume_id=1, user_id="u")
    chunk_ids = [p.chunk_id for p in result.batch.payloads]
    assert len(chunk_ids) == len(set(chunk_ids))


@pytest.mark.asyncio
async def test_large_batch_performance(pipeline):
    chunks = [{"text": f"Chunk number {i} with some content.", "section": "experience", "token_count": 6} for i in range(100)]
    result = await pipeline.prepare(chunks, resume_id=1, user_id="u")
    assert result.batch.total_chunks == 100


# ── LangGraph Node Interface ────────────────────────────────────────

@pytest.mark.asyncio
async def test_langgraph_node_success(pipeline, sample_chunks):
    state = {"semantic_chunks": sample_chunks, "resume_id": 1, "user_id": "test_user"}
    update = await pipeline.run(state)
    assert update["embedding_payloads"] is not None
    assert update["embedding_error"] is None
    assert update["embedding_batch"] is not None


@pytest.mark.asyncio
async def test_langgraph_node_falls_back_to_chunks(pipeline):
    chunks = [{"text": "Fallback chunk", "section": "general", "token_count": 3}]
    state = {"semantic_chunks": None, "chunks": chunks, "resume_id": 1, "user_id": "u"}
    update = await pipeline.run(state)
    assert update["embedding_payloads"] is not None


@pytest.mark.asyncio
async def test_langgraph_node_no_chunks(pipeline):
    state = {"semantic_chunks": None, "chunks": None, "resume_id": 1, "user_id": "u"}
    update = await pipeline.run(state)
    assert update["embedding_payloads"] is None
    assert update["embedding_error"] is not None
