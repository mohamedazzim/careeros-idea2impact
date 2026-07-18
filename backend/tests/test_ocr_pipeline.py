"""
Integration and unit tests for the production OCR pipeline.
Tests Tesseract OCR with real image data, confidence scoring,
fallback chain, and scanned PDF handling.
"""
import io
import os
import shutil
import pytest
from pathlib import Path
from src.services.resume.processing.ocr_pipeline import (
    OcrPipeline,
    OcrPageResult,
    OcrDocumentResult,
    OcrTimeoutError,
    RetryablePipelineError,
    PermanentPipelineError,
)
from PIL import Image, ImageDraw, ImageFont

TEST_FILES_DIR = Path(__file__).parent / "test_files"

requires_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None and os.getenv("RUN_OCR_TESTS") != "true",
    reason="OCR integration test requires tesseract binary",
)

tesseract_or_integration = pytest.mark.skipif(
    shutil.which("tesseract") is None and os.getenv("RUN_INTEGRATION_TESTS") != "true",
    reason="OCR integration test requires tesseract binary or RUN_INTEGRATION_TESTS=true",
)


@pytest.fixture(autouse=True)
def ensure_test_files():
    TEST_FILES_DIR.mkdir(exist_ok=True)


@pytest.fixture
def ocr():
    return OcrPipeline()


# ── Helpers ─────────────────────────────────────────────────────────

def _create_text_image(text: str, size=(800, 200)) -> bytes:
    """Create a PNG image with embedded text for OCR testing."""
    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except (OSError, IOError):
        font = ImageFont.load_default()
    draw.text((20, 20), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _write_test_file(name: str, content: bytes) -> Path:
    path = TEST_FILES_DIR / name
    path.write_bytes(content)
    return path


# ── Detect Needs OCR ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_needs_ocr_image_file(ocr):
    needs = await ocr._detect_needs_ocr("photo.png", "/tmp/photo.png")
    assert needs is True


@pytest.mark.asyncio
async def test_detect_needs_ocr_jpeg(ocr):
    needs = await ocr._detect_needs_ocr("scan.jpg", "/tmp/scan.jpg")
    assert needs is True


@pytest.mark.asyncio
async def test_detect_needs_ocr_low_text(ocr):
    needs = await ocr._detect_needs_ocr("resume.pdf", "/tmp/resume.pdf", existing_text="A")
    assert needs is True


@pytest.mark.asyncio
async def test_detect_needs_ocr_sufficient_text(ocr):
    text = "Experienced software engineer with 10 years of Python development."
    needs = await ocr._detect_needs_ocr("resume.pdf", "/tmp/resume.pdf", existing_text=text)
    assert needs is False


@pytest.mark.asyncio
async def test_detect_needs_ocr_image_based_pages(ocr):
    needs = await ocr._detect_needs_ocr(
        "resume.pdf", "/tmp/resume.pdf",
        existing_text="Some text that is long enough to reach the threshold minimum",
        image_based_pages=[0, 2],
    )
    assert needs is True


# ── Image OCR (real Tesseract) ─────────────────────────────────────

@pytest.mark.integration
@requires_tesseract
@pytest.mark.asyncio
async def test_ocr_single_image(ocr):
    """Real OCR on a generated image with text."""
    img_bytes = _create_text_image("John Doe\nSoftware Engineer\nPython Developer")
    path = _write_test_file("ocr_test.png", img_bytes)
    result = await ocr.process("ocr_test.png", str(path), content_type="image/png")
    text_lower = result.text.lower()
    assert any(word in text_lower for word in ["john", "doe", "software", "engineer", "python"]), \
        f"Expected recognizable text, got: {result.text[:100]}"


@pytest.mark.integration
@requires_tesseract
@pytest.mark.asyncio
async def test_ocr_image_confidence(ocr):
    """OCR should produce a confidence score between 0 and 1."""
    img_bytes = _create_text_image("John Smith\n123 Main St\nSoftware Engineer")
    path = _write_test_file("conf_test.png", img_bytes)
    result = await ocr.process("conf_test.png", str(path), content_type="image/png")
    conf = result.confidence
    assert 0.0 <= conf <= 1.0, f"Expected confidence between 0 and 1, got {conf}"


@pytest.mark.asyncio
async def test_ocr_clean_text_no_need(ocr):
    """Document with clean text should skip OCR."""
    text = "John Doe\nSoftware Engineer\nSkills: Python, React, TypeScript\nExperience: 5 years"
    path = _write_test_file("clean_pdf.pdf", b"%PDF-1.4\n...\n%%EOF")
    result = await ocr.process("clean_pdf.pdf", str(path), existing_text=text)
    assert result.metadata.get("ocr_applied") is False
    assert text in result.text


@pytest.mark.integration
@requires_tesseract
@pytest.mark.asyncio
async def test_ocr_scanned_pdf(ocr):
    """Real OCR on a PDF with embedded image pages."""
    import fitz
    path = str(TEST_FILES_DIR / "scanned.pdf")
    doc = fitz.open()
    page = doc.new_page()
    img_bytes = _create_text_image("Jane Doe\nData Scientist\nSkills: Python, R, SQL")
    img_rect = fitz.Rect(0, 0, 612, 792)
    page.insert_image(img_rect, stream=img_bytes)
    doc.save(path)
    doc.close()
    result = await ocr.process("scanned.pdf", str(path), content_type="application/pdf")
    text_lower = result.text.lower()
    has_text = any(w in text_lower for w in ["jane", "doe", "data", "python", "sql"])
    assert has_text, f"OCR should extract text from scanned PDF, got: {result.text[:200]}"


# ── Fallback chain ─────────────────────────────────────────────────

@pytest.mark.integration
@requires_tesseract
def test_ocr_image_bytes_with_fallback_raw(ocr):
    """Raw pass-through should work with clean images."""
    img_bytes = _create_text_image("TEST WORD")
    text, conf, method = ocr._ocr_image_bytes_with_fallback(img_bytes)
    assert isinstance(text, str)
    assert 0.0 <= conf <= 1.0
    assert method in ("none", "grayscale", "sharpen", "contrast_boost", "binarize_fallback")


@pytest.mark.integration
@requires_tesseract
def test_ocr_image_bytes_preprocessing_methods(ocr):
    """Each preprocessing method should return a valid tuple."""
    img_bytes = _create_text_image("TEST OUTPUT")
    for method in ("none", "grayscale", "sharpen", "contrast_boost", "binarize"):
        text, conf = ocr._ocr_image_bytes(img_bytes, preprocess=method)
        assert isinstance(text, str), f"Method {method} should return string"
        assert 0.0 <= conf <= 1.0, f"Method {method} confidence out of range: {conf}"


def test_aggregate_confidence(ocr):
    page_results = [
        OcrPageResult(page_num=0, text="Hello world what is up", confidence=0.90, preprocess_used="none", duration_ms=100),
        OcrPageResult(page_num=1, text="Another page text here with more words", confidence=0.80, preprocess_used="grayscale", duration_ms=150),
    ]
    conf = ocr._aggregate_confidence(page_results)
    assert 0.80 <= conf <= 0.95, f"Expected weighted avg ~0.84, got {conf}"


def test_aggregate_confidence_empty(ocr):
    conf = ocr._aggregate_confidence([])
    assert conf == 0.0


# ── Text Merging ───────────────────────────────────────────────────

def test_merge_texts_ocr_supplements(ocr):
    native = "John Doe"
    ocr_text = "John Doe\nSoftware Engineer\nSkills: Python, React, TypeScript\nExperience: 5 years at Acme Corp"
    result = ocr._merge_texts(native, ocr_text)
    assert result == ocr_text


def test_merge_texts_native_richer(ocr):
    native = "John Doe\nSoftware Engineer\nSkills: Python, React, TypeScript\nExperience: 5 years at Acme Corp"
    ocr_text = "John Doe"
    result = ocr._merge_texts(native, ocr_text)
    assert result == native


def test_merge_texts_none_inputs(ocr):
    assert ocr._merge_texts(None, "Hello") == "Hello"
    assert ocr._merge_texts("Hello", "") == "Hello"


# ── Error handling ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ocr_missing_file(ocr):
    with pytest.raises(RetryablePipelineError):
        await ocr.process("missing.png", "/nonexistent/file.png", content_type="image/png")


# ── LangGraph node interface ───────────────────────────────────────

@pytest.mark.integration
@requires_tesseract
@pytest.mark.asyncio
async def test_ocr_langgraph_node(ocr):
    img_bytes = _create_text_image("John Doe\nSoftware Engineer")
    path = _write_test_file("lg_ocr.png", img_bytes)
    state = {
        "filename": "lg_ocr.png",
        "storage_path": str(path),
        "content_type": "image/png",
        "raw_text": None,
    }
    update = await ocr.run(state)
    assert update["ocr_text"] is not None
    assert update["ocr_confidence"] > 0.0
    assert update["ocr_error"] is None


@pytest.mark.asyncio
async def test_ocr_langgraph_node_error(ocr):
    state = {
        "filename": "missing.png",
        "storage_path": "/does/not/exist.png",
        "content_type": "image/png",
        "raw_text": None,
    }
    update = await ocr.run(state)
    assert update["ocr_text"] is None
    assert update["ocr_error"] is not None
