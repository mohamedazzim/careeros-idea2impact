"""
Validation tests for MIME detection pipeline.
Tests content detection, integrity validation, corrupted file handling.
"""
import pytest
from src.services.resume.processing.mime_detector import (
    MimeDetectorPipeline,
    MimeValidationResult,
    MimeDetectionError,
    CorruptedFileError,
    UnsupportedFormatError,
)


@pytest.fixture
def detector():
    return MimeDetectorPipeline()


# ── Extension-based detection ───────────────────────────────────────

def test_detect_pdf_by_extension(detector):
    assert detector.detect_from_extension("resume.pdf") == "application/pdf"


def test_detect_docx_by_extension(detector):
    assert detector.detect_from_extension("resume.docx") == \
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_detect_txt_by_extension(detector):
    assert detector.detect_from_extension("notes.txt") == "text/plain"


def test_detect_unknown_extension(detector):
    assert detector.detect_from_extension("data.xyz") is None


# ── Content-based detection (magic numbers) ────────────────────────

def test_detect_pdf_by_magic_bytes(detector):
    content = b"%PDF-1.7\n%...\ntrailer\n%%EOF"
    assert detector.detect_from_content(content) == "application/pdf"


def test_detect_pdf2_by_magic_bytes(detector):
    content = b"%PDF-2.0\n...\n%%EOF"
    assert detector.detect_from_content(content) == "application/pdf"


def test_detect_rtf_by_magic_bytes(detector):
    content = b"{\\rtf1\\ansi\\deff0 {\\fonttbl {\\f0 Times New Roman;}}\nHello\n}"
    assert detector.detect_from_content(content) == "application/rtf"


def test_detect_png_by_magic_bytes(detector):
    content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    assert detector.detect_from_content(content) == "image/png"


def test_detect_jpeg_by_magic_bytes(detector):
    content = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01'
    assert detector.detect_from_content(content) == "image/jpeg"


def test_detect_gif_by_magic_bytes(detector):
    content = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04'
    assert detector.detect_from_content(content) == "image/gif"


def test_detect_plain_text_by_content(detector):
    content = b"This is a plain text resume.\nWith contact information.\n"
    assert detector.detect_from_content(content) == "text/plain"


def test_detect_html_by_content(detector):
    content = b"<html><head><title>Resume</title></head><body><h1>Name</h1></body></html>"
    assert detector.detect_from_content(content) == "text/html"


def test_detect_empty_content(detector):
    assert detector.detect_from_content(b"") is None


def test_detect_ascii_binary_not_text(detector):
    """Random binary data should not be detected as text."""
    content = bytes(range(256))
    detected = detector.detect_from_content(content)
    # Should not detect as any known type unless random bytes happen to match
    assert detected is None or detected.startswith("image/")


# ── Content integrity validation ───────────────────────────────────

def test_validate_valid_pdf(detector):
    content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"xref\n0 1\n0000000000 65535 f \n"
        b"trailer\n<< /Root 1 0 R >>\n"
        b"%%EOF"
    )
    is_valid, error = detector.validate_content_integrity(content, "application/pdf")
    assert is_valid is True
    assert error is None


def test_validate_pdf_missing_eof(detector):
    content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj"
    is_valid, error = detector.validate_content_integrity(content, "application/pdf")
    assert is_valid is False
    assert "EOF" in (error or "")


def test_validate_pdf_missing_header(detector):
    content = b"Not a PDF file!\n%%EOF"
    is_valid, error = detector.validate_content_integrity(content, "application/pdf")
    assert is_valid is False


def test_validate_docx_zip(detector):
    """Test DOCX validation with a minimally valid ZIP structure."""
    import zipfile, io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
        zf.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Test</w:t></w:r></w:p></w:body></w:document>')
    content = buf.getvalue()
    is_valid, error = detector.validate_content_integrity(content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert is_valid is True, f"Expected valid DOCX, got: {error}"


def test_validate_corrupted_docx(detector):
    content = b"PK\x03\x04not a real zip file\x00\x00"
    is_valid, error = detector.validate_content_integrity(content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert is_valid is False


def test_validate_too_small_pdf(detector):
    content = b"%PDF"
    is_valid, error = detector.validate_content_integrity(content, "application/pdf")
    assert is_valid is False


def test_validate_image_png_missing_iend(detector):
    """PNG without IEND chunk should be flagged."""
    content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
    is_valid, error = detector.validate_content_integrity(content, "image/png")
    assert is_valid is False


# ── Async detection ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_async_pdf(detector):
    mime = await detector.detect("resume.pdf", b"%PDF-1.4\n...\n%%EOF")
    assert mime == "application/pdf"


@pytest.mark.asyncio
async def test_detect_async_fallback_to_extension(detector):
    mime = await detector.detect("resume.docx")
    assert mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.mark.asyncio
async def test_detect_async_unknown(detector):
    with pytest.raises(MimeDetectionError):
        await detector.detect("data.xyz")


# ── Full validation ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_supported_format(detector):
    content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\ntrailer\n<<>>\n%%EOF"
    result = await detector.validate("resume.pdf", content)
    assert isinstance(result, MimeValidationResult)
    assert result.is_valid is True
    assert result.is_supported is True
    assert result.is_corrupted is False
    assert result.mime_type == "application/pdf"


@pytest.mark.asyncio
async def test_validate_unsupported_format(detector):
    # Generate a ZIP with XLSX content types — detected as ZIP but not a supported processing format
    import zipfile, io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '</Types>')
        zf.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>')
    content = buf.getvalue()
    with pytest.raises(UnsupportedFormatError):
        await detector.validate("spreadsheet.xlsx", content)


@pytest.mark.asyncio
async def test_validate_corrupted_content(detector):
    # PDF header but no structural integrity
    content = b"%PDF-1.4\n\xff\xfe\xfd\xfc" + b'\x00' * 100
    with pytest.raises(CorruptedFileError):
        await detector.validate("resume.pdf", content)


# ── Format helpers ─────────────────────────────────────────────────

def test_is_supported(detector):
    assert detector.is_supported("application/pdf") is True
    assert detector.is_supported("text/plain") is True
    assert detector.is_supported("audio/mp3") is False


def test_is_image(detector):
    assert detector.is_image("image/png") is True
    assert detector.is_image("image/jpeg") is True
    assert detector.is_image("application/pdf") is False


def test_get_extension(detector):
    assert detector.get_extension("application/pdf") == ".pdf"
    assert detector.get_extension("text/plain") == ".txt"


# ── DOCX ZIP detection ─────────────────────────────────────────────

def test_detect_docx_from_zip_content(detector):
    """DOCX should be detected as document, not generic ZIP."""
    import zipfile, io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/></Types>')
        zf.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:body></w:document>')
    content = buf.getvalue()
    mime = detector.detect_from_content(content)
    assert mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
