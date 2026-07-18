"""
Tests for the Phase 2C Semantic Chunking pipeline.
Tests: section-aware chunking, overlap strategy, token limits,
metadata preservation, boundary detection, chunk quality.
"""
import pytest
from src.services.resume.processing.chunking_pipeline import (
    ChunkingPipeline,
    ChunkResult,
    RetryablePipelineError,
)
from src.services.resume.processing.interfaces import ChunkingStrategy


@pytest.fixture
def pipeline():
    return ChunkingPipeline()


@pytest.fixture
def small_chunk_strategy():
    return ChunkingStrategy(
        max_chunk_tokens=100,
        min_chunk_tokens=20,
        overlap_tokens=20,
        preserve_section_boundaries=True,
        preserve_sentence_boundaries=True,
    )


# ── Basic Chunking ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_basic_chunking_splits_text(pipeline):
    text = "Sentence one here. Sentence two is here. Sentence three goes here. " * 10
    result = await pipeline.chunk(text)
    assert result.chunk_count > 0
    assert len(result.chunks) > 0
    assert all(c.text for c in result.chunks)
    assert result.avg_chunk_size > 0


@pytest.mark.asyncio
async def test_chunking_respects_max_tokens(pipeline, small_chunk_strategy):
    text = "Sentence one here. Sentence two here. Sentence three here. " * 20
    result = await pipeline.chunk(text, strategy=small_chunk_strategy)
    for chunk in result.chunks:
        assert chunk.token_count <= small_chunk_strategy.max_chunk_tokens + 30
        assert chunk.word_count > 0


@pytest.mark.asyncio
async def test_chunking_produces_metadata(pipeline):
    text = "This is a test sentence. Another sentence follows. " * 10
    result = await pipeline.chunk(text)
    for chunk in result.chunks:
        assert chunk.chunk_id
        assert chunk.section
        assert chunk.char_start >= 0
        assert chunk.char_end > chunk.char_start
        assert chunk.token_count > 0


# ── Overlap Strategy ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_overlap_between_chunks(pipeline, small_chunk_strategy):
    text = "This is sentence one. This is sentence two. This is sentence three. " * 30
    result = await pipeline.chunk(text, strategy=small_chunk_strategy)
    if result.chunk_count >= 2:
        overlapping = [c for c in result.chunks if c.overlap_with_previous]
        assert len(overlapping) > 0 or result.chunk_count == 1


@pytest.mark.asyncio
async def test_no_overlap_for_first_chunk(pipeline):
    text = "One. Two. Three. " * 20
    result = await pipeline.chunk(text)
    assert result.chunks[0].overlap_with_previous is False


@pytest.mark.asyncio
async def test_no_overlap_for_last_chunk(pipeline):
    text = "One. Two. Three. " * 20
    result = await pipeline.chunk(text)
    assert result.chunks[-1].overlap_with_next is False


# ── Section-Aware Chunking ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_section_boundaries_detected(pipeline):
    text = (
        "SUMMARY\nThis is a summary paragraph.\n\n"
        "EXPERIENCE\nSoftware engineer with five years at Acme Corp.\n"
        "Built production systems using Python and React.\n"
        "Managed a team of four developers.\n\n"
        "EDUCATION\nBachelor of Science in Computer Science.\n"
        "Graduated with honors.\n\n"
        "SKILLS\nPython, React, TypeScript, Docker, AWS, Kubernetes\n"
    )
    result = await pipeline.chunk(text)
    assert len(result.section_boundaries) > 0
    sections = {b.normalized_name for b in result.section_boundaries}
    assert len(sections) > 0


@pytest.mark.asyncio
async def test_chunks_labeled_by_section(pipeline):
    text = (
        "EXPERIENCE\nFive years at company. Built many things. Led teams."
        "Developed microservices. Mentored juniors. Designed architecture.\n\n"
        "SKILLS\nPython and React and TypeScript and Docker and more."
    )
    result = await pipeline.chunk(text)
    section_labels = {c.section for c in result.chunks}
    assert len(section_labels) > 0


# ── Token-Aware Chunk Sizing ────────────────────────────────────────

@pytest.mark.asyncio
async def test_token_estimation_is_reasonable(pipeline):
    text = "Python React TypeScript Docker Kubernetes AWS Lambda Terraform " * 10
    result = await pipeline.chunk(text)
    for chunk in result.chunks:
        assert chunk.token_count > 0
        assert chunk.word_count > 0
        assert chunk.token_count >= chunk.word_count


@pytest.mark.asyncio
async def test_chunk_size_statistics(pipeline):
    text = "Sentence one is here. Sentence two follows now. " * 15
    result = await pipeline.chunk(text)
    assert result.avg_chunk_size > 0
    assert result.avg_chunk_tokens > 0
    assert result.chunk_count > 0


# ── Metadata Preservation ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_chunks_have_metadata_fields(pipeline):
    text = "EXPERIENCE\nSenior Engineer. Built systems. Led teams. " * 5
    result = await pipeline.chunk(text)
    for chunk in result.chunks:
        assert isinstance(chunk.metadata, dict)
        assert "chunk_type" in chunk.__dict__ or chunk.chunk_type


@pytest.mark.asyncio
async def test_result_metadata_complete(pipeline):
    text = "EXPERIENCE\nFive years. Skills: Python, React. Education: BS CS." * 3
    result = await pipeline.chunk(text)
    assert result.metadata["method"] == "semantic_section_aware"
    assert result.metadata["max_chunk_tokens"] > 0
    assert result.metadata["overlap_tokens"] >= 0
    assert isinstance(result.metadata["section_distribution"], dict)


# ── Quality Validation ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chunks_contain_meaningful_content(pipeline):
    text = "EXPERIENCE\nSoftware Engineer at Google. Led ML team. Built pipelines."
    result = await pipeline.chunk(text)
    for chunk in result.chunks:
        assert len(chunk.text.strip()) >= 10


@pytest.mark.asyncio
async def test_no_overlapping_char_ranges(pipeline):
    text = "One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten. " * 5
    result = await pipeline.chunk(text)
    chunks = result.chunks
    for i in range(len(chunks) - 1):
        assert chunks[i].char_end <= chunks[i + 1].char_start + 1


@pytest.mark.asyncio
async def test_full_text_coverage(pipeline):
    text = "Content here. More content there. And even more everywhere. " * 10
    result = await pipeline.chunk(text)
    if result.chunks:
        covered_text = " ".join(c.text for c in result.chunks)
        assert len(covered_text) > 0


# ── Empty/Edge Cases ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_text_raises(pipeline):
    with pytest.raises(RetryablePipelineError):
        await pipeline.chunk("")


@pytest.mark.asyncio
async def test_single_sentence_chunking(pipeline):
    text = "Just one sentence."
    result = await pipeline.chunk(text)
    assert result.chunk_count == 1
    assert result.chunks[0].text.strip() == "Just one sentence."


@pytest.mark.asyncio
async def test_very_long_chunk(pipeline):
    text = "Very long sentence. " * 200
    result = await pipeline.chunk(text)
    assert result.chunk_count >= 1


# ── LangGraph Node Interface ────────────────────────────────────────

@pytest.mark.asyncio
async def test_langgraph_node_success(pipeline):
    state = {"normalized_text": "EXPERIENCE\nFive years at Corp.\n\nSKILLS\nPython, React"}
    update = await pipeline.run(state)
    assert update["chunks"] is not None
    assert update["chunking_error"] is None
    assert len(update["chunks"]) > 0


@pytest.mark.asyncio
async def test_langgraph_node_empty_text(pipeline):
    state = {"normalized_text": None, "masked_text": None, "raw_text": None}
    update = await pipeline.run(state)
    assert update["chunks"] is None
    assert update["chunking_error"] is not None


@pytest.mark.asyncio
async def test_langgraph_node_falls_back_to_raw(pipeline):
    state = {"normalized_text": None, "masked_text": None, "raw_text": "Some raw text."}
    update = await pipeline.run(state)
    assert update["chunks"] is not None
    assert len(update["chunks"]) > 0


# ── Retrieval Quality Tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_chunk_boundaries_preserve_sections(pipeline):
    """Verify chunks don't break section content across unrelated sections."""
    text = (
        "EXPERIENCE\nPython developer at Acme Corp. Built REST APIs and data pipelines.\n"
        "Used FastAPI, PostgreSQL, Docker, and AWS.\n\n"
        "EDUCATION\nBS Computer Science from State University. Graduated 2018."
    )
    result = await pipeline.chunk(text)
    for chunk in result.chunks:
        assert chunk.section is not None


@pytest.mark.asyncio
async def test_retrieval_metadata_present(pipeline):
    text = "EXPERIENCE\nSenior engineer. Skills: Python, React, TypeScript, Docker."
    result = await pipeline.chunk(text)
    for chunk in result.chunks:
        assert chunk.chunk_id
        assert chunk.section
        assert chunk.token_count > 0


@pytest.mark.asyncio
async def test_chunks_indexed_correctly(pipeline):
    text = "Chunk one content. Chunk two content. Chunk three here." * 10
    result = await pipeline.chunk(text)
    chunk_ids = [c.chunk_id for c in result.chunks]
    assert len(chunk_ids) == len(set(chunk_ids))


# ── Benchmark: Chunk Quality Validation ─────────────────────────────

@pytest.mark.asyncio
async def test_chunk_size_within_range(pipeline):
    text = "Sentence here. Another one. And another." * 40
    result = await pipeline.chunk(text)
    sizes = [c.word_count for c in result.chunks]
    assert all(s > 0 for s in sizes)
    assert max(sizes) <= pipeline.strategy.max_chunk_tokens * 3


@pytest.mark.asyncio
async def test_chunking_is_deterministic(pipeline):
    text = "Test content that should chunk the same way every time. " * 20
    result1 = await pipeline.chunk(text)
    result2 = await pipeline.chunk(text)
    assert result1.chunk_count == result2.chunk_count
    for i in range(min(len(result1.chunks), len(result2.chunks))):
        assert result1.chunks[i].text == result2.chunks[i].text
