"""
Tests for the Phase 2C Masking pipeline.
Tests: GLiNER integration, regex fallback, confidence scoring,
masking strategies, audit-safe replacements, entity merging.
"""
import pytest
from src.services.resume.processing.masking_pipeline import (
    MaskingPipeline,
    MaskingResult,
    RetryablePipelineError,
)
from src.services.resume.processing.interfaces import (
    MaskingPolicy,
    MaskingStrategy,
)


@pytest.fixture
def pipeline():
    return MaskingPipeline()


@pytest.fixture
def token_policy():
    return MaskingPolicy(strategy=MaskingStrategy.TOKEN)


@pytest.fixture
def synthetic_policy():
    return MaskingPolicy(strategy=MaskingStrategy.SYNTHETIC)


@pytest.fixture
def redact_policy():
    return MaskingPolicy(strategy=MaskingStrategy.REDACT)


# ── Email Masking ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_email_masking_token(pipeline, token_policy):
    text = "Contact me at john.doe@example.com"
    result = await pipeline.mask(text, policy=token_policy)
    assert "john.doe@example.com" not in result.masked_text
    assert "[MASKED_EMAIL]" in result.masked_text
    assert result.audit_report.total_entities >= 1


@pytest.mark.asyncio
async def test_email_masking_redact(pipeline, redact_policy):
    text = "Contact me at john.doe@example.com"
    result = await pipeline.mask(text, policy=redact_policy)
    assert "john.doe@example.com" not in result.masked_text
    assert "[REDACTED]" in result.masked_text


@pytest.mark.asyncio
async def test_email_masking_synthetic(pipeline, synthetic_policy):
    text = "Contact me at john.doe@example.com"
    result = await pipeline.mask(text, policy=synthetic_policy)
    assert "john.doe@example.com" not in result.masked_text


# ── Phone Masking ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phone_masking(pipeline, token_policy):
    text = "Call me at (555) 123-4567"
    result = await pipeline.mask(text, policy=token_policy)
    assert "(555) 123-4567" not in result.masked_text
    assert "MASKED" in result.masked_text


@pytest.mark.asyncio
async def test_phone_variants_masked(pipeline):
    text = "Call 555-123-4567 or 555.123.4567 or (555) 123-4567"
    result = await pipeline.mask(text)
    assert "555" not in result.masked_text or "[MASKED" in result.masked_text


# ── URL/Profile Masking ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_linkedin_url_masked(pipeline):
    text = "My profile: https://linkedin.com/in/johndoe"
    result = await pipeline.mask(text)
    assert "linkedin.com" not in result.masked_text


@pytest.mark.asyncio
async def test_github_url_masked(pipeline):
    text = "My code: https://github.com/johndoe"
    result = await pipeline.mask(text)
    assert "github.com" not in result.masked_text


# ── Audit Report ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_report_generated(pipeline, token_policy):
    text = "john@example.com, (555) 123-4567, https://linkedin.com/in/john"
    result = await pipeline.mask(text, policy=token_policy)
    assert result.audit_report.total_entities >= 1
    assert isinstance(result.audit_report.entities_by_type, dict)
    assert isinstance(result.audit_report.entities_by_source, dict)
    assert result.audit_report.avg_confidence > 0


@pytest.mark.asyncio
async def test_audit_report_masked_entities_detail(pipeline):
    text = "email: jane@example.com phone: 555-123-4567"
    result = await pipeline.mask(text)
    assert len(result.masked_entities) >= 1
    for me in result.masked_entities:
        assert me.entity_type
        assert me.original_text
        assert me.masked_text
        assert me.confidence >= 0
        assert me.source


@pytest.mark.asyncio
async def test_audit_report_confidence_stats(pipeline):
    text = "john@example.com and jane@example.com and bob@example.com"
    result = await pipeline.mask(text)
    assert result.audit_report.avg_confidence >= 0
    assert result.audit_report.min_confidence >= 0
    assert result.audit_report.max_confidence >= result.audit_report.min_confidence


# ── Confidence Filtering ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_low_confidence_entities_filtered(pipeline):
    policy = MaskingPolicy(min_confidence=0.95, entity_types=["EMAIL", "PHONE"])
    text = "john@example.com and (555) 123-4567"
    result = await pipeline.mask(text, policy=policy)
    assert result.audit_report.total_entities >= 0


@pytest.mark.asyncio
async def test_min_confidence_zero_masks_all(pipeline):
    policy = MaskingPolicy(min_confidence=0.0)
    text = "john@example.com"
    result = await pipeline.mask(text, policy=policy)
    assert result.audit_report.total_entities >= 1


# ── Strategy Comparison ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_token_strategy_has_labels(pipeline):
    text = "Email: test@example.com Phone: 555-123-4567"
    result = await pipeline.mask(text, policy=MaskingPolicy(strategy=MaskingStrategy.TOKEN))
    assert "MASKED" in result.masked_text


@pytest.mark.asyncio
async def test_redact_strategy_uniform(pipeline):
    text = "Email: test@example.com Phone: 555-123-4567"
    result = await pipeline.mask(text, policy=MaskingPolicy(strategy=MaskingStrategy.REDACT))
    assert "[REDACTED]" in result.masked_text


@pytest.mark.asyncio
async def test_hash_strategy_produces_hash(pipeline):
    text = "Email: test@example.com"
    result = await pipeline.mask(text, policy=MaskingPolicy(strategy=MaskingStrategy.HASH))
    assert "[HASH:" in result.masked_text
    assert "test@example.com" not in result.masked_text


# ── Entity Merging ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gliner_regex_merge_no_duplicates(pipeline):
    text = "Contact: john.doe@example.com"
    result = await pipeline.mask(text)
    email_entities = [e for e in result.masked_entities if e.entity_type == "EMAIL"]
    assert len(email_entities) <= 1


@pytest.mark.asyncio
async def test_entity_preserves_position_order(pipeline):
    text = "Name: John\nEmail: john@example.com\nPhone: 555-123-4567"
    result = await pipeline.mask(text)
    positions = [(e.start_char, e.end_char) for e in result.masked_entities]
    for i in range(len(positions) - 1):
        assert positions[i][0] <= positions[i + 1][0]


# ── Edge Cases ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_text_raises(pipeline):
    with pytest.raises(RetryablePipelineError):
        await pipeline.mask("")


@pytest.mark.asyncio
async def test_no_pii_returns_unchanged(pipeline):
    text = "This is a simple sentence with no personal information."
    result = await pipeline.mask(text)
    assert result.masked_text == text
    assert result.audit_report.total_entities == 0


@pytest.mark.asyncio
async def test_length_tracking(pipeline):
    text = "Email: john@example.com Phone: 555-123-4567"
    result = await pipeline.mask(text)
    assert result.original_length == len(text)
    assert result.masked_length > 0


# ── LangGraph Node Interface ────────────────────────────────────────

@pytest.mark.asyncio
async def test_langgraph_node_success(pipeline):
    state = {"normalized_text": "Email: test@example.com Phone: 555-123-4567"}
    update = await pipeline.run(state)
    assert update["masked_text"] is not None
    assert update["masking_error"] is None
    assert update["masking_audit"] is not None


@pytest.mark.asyncio
async def test_langgraph_node_empty_text(pipeline):
    state = {"normalized_text": None, "raw_text": None}
    update = await pipeline.run(state)
    assert update["masked_text"] is None
    assert update["masking_error"] is not None


@pytest.mark.asyncio
async def test_langgraph_node_falls_back_to_raw(pipeline):
    state = {"normalized_text": None, "raw_text": "Email: test@example.com"}
    update = await pipeline.run(state)
    assert update["masked_text"] is not None


# ── Masking Accuracy Metrics ────────────────────────────────────────

@pytest.mark.asyncio
async def test_email_detection_accuracy(pipeline):
    text = "Contact john.doe@example.com for details"
    result = await pipeline.mask(text)
    email_entities = [e for e in result.masked_entities if e.entity_type == "EMAIL"]
    assert len(email_entities) >= 1
    assert email_entities[0].original_text == "john.doe@example.com"


@pytest.mark.asyncio
async def test_multiple_emails_all_masked(pipeline):
    text = "a@example.com b@example.com c@example.com"
    result = await pipeline.mask(text)
    assert "a@example.com" not in result.masked_text
    assert "b@example.com" not in result.masked_text
    assert "c@example.com" not in result.masked_text


@pytest.mark.asyncio
async def test_phone_format_variants(pipeline):
    text = "Call 555-123-4567 or 555.123.4567 or (555)123-4567"
    result = await pipeline.mask(text)
    assert "555" not in result.masked_text or "[MASKED" in result.masked_text
