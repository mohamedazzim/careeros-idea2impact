"""
Tests for the Phase 2C Normalization pipeline.
Tests: whitespace normalization, Unicode normalization, OCR cleanup,
section reconstruction, heading preservation, bullet normalization.
"""
import pytest
from src.services.resume.processing.normalization_pipeline import (
    NormalizationPipeline,
    NormalizationResult,
    RetryablePipelineError,
)


@pytest.fixture
def pipeline():
    return NormalizationPipeline()


# ── Whitespace Normalization ────────────────────────────────────────

@pytest.mark.asyncio
async def test_whitespace_collapse_multiple_spaces(pipeline):
    text = "John    Doe\n\n\nSoftware    Engineer\n  Python  "
    result = await pipeline.normalize(text, enable_section_reconstruction=False)
    assert "John Doe" in result.normalized_text
    assert "    " not in result.normalized_text
    assert result.metrics.whitespace_fixes > 0


@pytest.mark.asyncio
async def test_whitespace_normalize_line_endings(pipeline):
    text = "Line 1\r\nLine 2\r\nLine 3\r\n"
    result = await pipeline.normalize(text, enable_section_reconstruction=False)
    assert "\r\n" not in result.normalized_text
    assert "\r" not in result.normalized_text


@pytest.mark.asyncio
async def test_whitespace_collapse_blank_lines(pipeline):
    text = "Header\n\n\n\n\n\nContent"
    result = await pipeline.normalize(text, enable_section_reconstruction=False)
    assert "\n\n\n\n" not in result.normalized_text


# ── Unicode Normalization ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_unicode_nfkc_normalization(pipeline):
    text = "Caf\u00e9 r\u00e9sum\u00e9 \u2013 \u201cquoted\u201d"
    result = await pipeline.normalize(text, enable_section_reconstruction=False)
    # NFKC should decompose composed chars, smart quotes should be replaced
    assert result.metrics.unicode_fixes > 0


@pytest.mark.asyncio
async def test_unicode_smart_quotes_replaced(pipeline):
    text = "\u201cthis is a quote\u201d and \u2018single\u2019"
    result = await pipeline.normalize(text, enable_section_reconstruction=False)
    assert '\u201c' not in result.normalized_text
    assert '\u201d' not in result.normalized_text
    assert '"' in result.normalized_text or "'" in result.normalized_text


@pytest.mark.asyncio
async def test_unicode_non_breaking_space(pipeline):
    text = "Hello\u00a0World\u00a0!"
    result = await pipeline.normalize(text, enable_section_reconstruction=False)
    assert '\u00a0' not in result.normalized_text


# ── OCR Cleanup ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ocr_control_character_removal(pipeline):
    text = "Name:\x00John Doe\x08\nSkills:\x0bPython\x0cReact"
    result = await pipeline.normalize(text, ocr_mode=True, enable_section_reconstruction=False)
    assert '\x00' not in result.normalized_text
    assert '\x08' not in result.normalized_text
    assert "John Doe" in result.normalized_text


@pytest.mark.asyncio
async def test_ocr_garbage_lines_removed(pipeline):
    text = "John Doe\n---\n||||||||||||\nSoftware Engineer\n======\nPython"
    result = await pipeline.normalize(text, ocr_mode=True, enable_section_reconstruction=False)
    assert "||||||||||||" not in result.normalized_text
    assert "Software Engineer" in result.normalized_text


@pytest.mark.asyncio
async def test_ocr_page_numbers_removed(pipeline):
    text = "Header\nContent line here.\n42\nMore content\n17\nMore content"
    result = await pipeline.normalize(text, ocr_mode=True, enable_section_reconstruction=False)
    assert "Software" not in result.normalized_text  # Already clean


# ── Section Detection ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_section_detection_experience(pipeline):
    text = "CONTACT\nJohn Doe\n\nEXPERIENCE\nSoftware Engineer at Acme\n\nEDUCATION\nBS Computer Science"
    result = await pipeline.normalize(text)
    assert result.section_count >= 2
    section_types = [s.section_type for s in result.sections]
    assert "experience" in section_types
    assert "education" in section_types


@pytest.mark.asyncio
async def test_section_detection_skills(pipeline):
    text = "EXPERIENCE\n5 years at Corp\n\nSKILLS\nPython, React, TypeScript"
    result = await pipeline.normalize(text)
    section_types = [s.section_type for s in result.sections]
    assert "skills" in section_types


@pytest.mark.asyncio
async def test_section_detection_summary(pipeline):
    text = "SUMMARY\nSenior engineer with 10 years experience\n\nEXPERIENCE\n..."
    result = await pipeline.normalize(text)
    section_types = [s.section_type for s in result.sections]
    assert "summary" in section_types


@pytest.mark.asyncio
async def test_section_no_sections_found(pipeline):
    text = "Just a plain paragraph with no resume headers at all."
    result = await pipeline.normalize(text)
    assert result.section_count == 1
    assert result.sections[0].section_type == "general"


@pytest.mark.asyncio
async def test_section_preserves_content(pipeline):
    text = "EXPERIENCE\nSenior Engineer at Google, 2015-2022\nLed ML team of 12 engineers"
    result = await pipeline.normalize(text)
    exp_section = next(s for s in result.sections if s.section_type == "experience")
    assert "Google" in exp_section.content
    assert "2015" in exp_section.content


# ── Bullet Normalization ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bullet_normalization_dash(pipeline):
    text = "SKILLS\n- Python\n- React\n- TypeScript"
    result = await pipeline.normalize(text, enable_section_reconstruction=False)
    assert result.metrics.bullets_normalized >= 2
    assert "• Python" in result.normalized_text


@pytest.mark.asyncio
async def test_bullet_normalization_asterisk(pipeline):
    text = "SKILLS\n* Python\n* React"
    result = await pipeline.normalize(text, enable_section_reconstruction=False)
    assert result.metrics.bullets_normalized >= 2
    assert "• Python" in result.normalized_text


@pytest.mark.asyncio
async def test_bullet_normalization_unicode_bullet(pipeline):
    text = "SKILLS\n• Python\n• React"
    result = await pipeline.normalize(text, enable_section_reconstruction=False)
    assert "• Python" in result.normalized_text
    assert "• React" in result.normalized_text


# ── Duplicate Line Removal ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_line_removal(pipeline):
    text = "Python\nPython\nPython\nReact\nReact\nTypeScript"
    result = await pipeline.normalize(text, enable_section_reconstruction=False)
    assert result.metrics.duplicate_lines_removed > 0


# ── Full Pipeline Integration ───────────────────────────────────────

@pytest.mark.asyncio
async def test_full_normalization_preserves_content(pipeline):
    text = (
        "SUMMARY\n"
        "Experienced software engineer with 10+ years in ML and cloud.\n\n"
        "EXPERIENCE\n"
        "Senior Engineer at Google, 2015-2022\n"
        "- Led ML team\n"
        "- Built scalable pipelines\n\n"
        "EDUCATION\n"
        "MS Computer Science, Stanford University\n\n"
        "SKILLS\n"
        "- Python\n- TensorFlow\n- AWS"
    )
    result = await pipeline.normalize(text)
    assert result.normalized_text
    assert result.section_count >= 4
    assert result.metrics.whitespace_fixes >= 0
    assert len(result.normalized_text) > 100


@pytest.mark.asyncio
async def test_empty_text_raises(pipeline):
    with pytest.raises(RetryablePipelineError):
        await pipeline.normalize("")


@pytest.mark.asyncio
async def test_langgraph_node_success(pipeline):
    state = {"raw_text": "SUMMARY\nEngineer\n\nEXPERIENCE\n5 years at Corp"}
    update = await pipeline.run(state)
    assert update["normalized_text"] is not None
    assert update["normalization_error"] is None
    assert update["normalized_sections"] is not None


@pytest.mark.asyncio
async def test_langgraph_node_empty_text(pipeline):
    state = {"raw_text": None, "masked_text": None}
    update = await pipeline.run(state)
    assert update["normalized_text"] is None
    assert update["normalization_error"] is not None


# ── Metrics Recording ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_are_recorded(pipeline):
    text = "John    Doe\n\nSKILLS\n- Python\n- React\n\x00badchar"
    result = await pipeline.normalize(text, ocr_mode=True)
    assert result.metrics.preprocessing_duration_ms >= 0
    assert isinstance(result.metrics.whitespace_fixes, int)
    assert isinstance(result.metrics.unicode_fixes, int)
    assert isinstance(result.metrics.ocr_fixes, int)
    assert isinstance(result.metrics.bullets_normalized, int)


@pytest.mark.asyncio
async def test_metadata_includes_length_changes(pipeline):
    text = "Original    text   with   spaces"
    result = await pipeline.normalize(text, enable_section_reconstruction=False)
    assert "original_length" in result.metadata
    assert "normalized_length" in result.metadata
    assert result.metadata["original_length"] >= result.metadata["normalized_length"]
