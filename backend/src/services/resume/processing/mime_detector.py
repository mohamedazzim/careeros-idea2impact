"""
Production-grade MIME type detection and content validation pipeline.
Deep content inspection, corrupted file detection, and format verification.
Stateless — ready for LangGraph node extraction.
"""
import logging
import zipfile
import io
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

from src.observability.metrics import (
    MIME_DETECTION_COUNT,
    MIME_CORRUPTED_COUNT,
    MIME_UNSUPPORTED_COUNT,
    PARSER_LATENCY,
)
from src.observability.langsmith import traceable

logger = logging.getLogger(__name__)


class MimeDetectionError(Exception):
    """Raised when MIME detection fails."""
    pass


class CorruptedFileError(MimeDetectionError):
    """Raised when file structure is corrupted."""
    pass


class UnsupportedFormatError(MimeDetectionError):
    """Raised when format is not supported."""
    pass


class ExtensionMismatchError(MimeDetectionError):
    """Raised when extension does not match detected content."""
    pass


@dataclass
class MimeValidationResult:
    """Complete result of MIME detection and validation."""
    mime_type: str
    detected_method: str  # "magic_bytes", "extension", "zip_inspection"
    is_valid: bool
    is_supported: bool
    is_corrupted: bool
    extension_matches_content: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class MimeDetectorPipeline:
    """
    Production-grade MIME type detection and content validation.
    Stateless — can be used as LangGraph node.
    """

    EXTENSION_TO_MIME = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
        ".md": "text/plain",
        ".rtf": "application/rtf",
        ".html": "text/html",
        ".htm": "text/html",
        ".odt": "application/vnd.oasis.opendocument.text",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }

    MIME_TO_EXTENSION = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/msword": ".doc",
        "application/rtf": ".rtf",
        "application/vnd.oasis.opendocument.text": ".odt",
        "text/html": ".html",
        "text/plain": ".txt",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "image/tiff": ".tiff",
    }

    SUPPORTED_PROCESSING_TYPES = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "application/rtf",
        "text/html",
        "application/vnd.oasis.opendocument.text",
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/bmp",
        "image/tiff",
    }

    # Minimum valid file sizes (bytes)
    MIN_VALID_SIZES = {
        "application/pdf": 5,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": 38,
        "application/vnd.oasis.opendocument.text": 38,
        "image/png": 33,
        "image/jpeg": 107,
    }

    # Maximum file size for MIME detection scrutiny (100MB)
    MAX_SCRUTINY_SIZE = 100 * 1024 * 1024

    # PDF version markers
    PDF_VERSIONS = (b'%PDF-1.', b'%PDF-2.')

    # Image magic numbers
    PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
    JPEG_MAGIC = b'\xff\xd8\xff'
    GIF87_MAGIC = b'GIF87a'
    GIF89_MAGIC = b'GIF89a'
    BMP_MAGIC = b'BM'
    TIFF_LE_MAGIC = b'II*\x00'
    TIFF_BE_MAGIC = b'MM\x00*'

    def detect_from_extension(self, filename: str) -> Optional[str]:
        """Detect MIME type from filename extension."""
        suffix = Path(filename.lower()).suffix
        return self.EXTENSION_TO_MIME.get(suffix)

    def detect_from_content(self, content: bytes) -> Optional[str]:
        """Detect MIME type from file content using magic numbers."""
        if not content:
            return None

        # PDF detection — check for %PDF header
        if self._is_pdf(content):
            return "application/pdf"

        # ZIP-based formats (DOCX, ODT, etc.)
        if content.startswith(b'PK\x03\x04'):
            return self._detect_zip_format(content)

        # RTF
        if content.startswith(b'{\\rtf') or content.startswith(b'{\\RTF'):
            return "application/rtf"

        # HTML
        if self._is_html(content):
            return "text/html"

        # Image formats
        image_type = self._detect_image_format(content)
        if image_type:
            return image_type

        # Plain text heuristic — try UTF-8 decode
        try:
            text = content[:4096].decode('utf-8', errors='strict')
            if self._looks_like_text(text):
                return "text/plain"
        except UnicodeDecodeError:
            pass

        return None

    def _is_pdf(self, content: bytes) -> bool:
        """Verify content is a valid PDF by checking header and structure."""
        if len(content) < 8:
            return False
        return content[:5] == b'%PDF-' and content[5] in (0x31, 0x32)  # '1' or '2'

    def _is_html(self, content: bytes) -> bool:
        """Detect HTML content by checking for tags or doctype."""
        head = content[:1024].lstrip().upper()
        return (
            head.startswith(b'<!DOCTYPE HTML') or
            head.startswith(b'<HTML') or
            head.startswith(b'<HEAD') or
            head.startswith(b'<BODY') or
            head.startswith(b'<META') or
            (head.startswith(b'<') and b'</' in content[:4096])
        )

    def _looks_like_text(self, text: str) -> bool:
        """Heuristic check if decoded content looks like text (not random binary)."""
        if not text.strip():
            return False
        printable_ratio = sum(1 for c in text if c.isprintable() or c in '\n\r\t') / max(len(text), 1)
        return printable_ratio > 0.90

    def _detect_zip_format(self, content: bytes) -> Optional[str]:
        """Inspect ZIP contents to determine the actual format (DOCX, ODT, XLSX, etc.)."""
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = [info.filename.lower() for info in zf.infolist()]

                if '[content_types].xml' in names:
                    with zf.open('[Content_Types].xml') as f:
                        ct_xml = f.read().decode('utf-8', errors='ignore')

                    if 'wordprocessingml' in ct_xml:
                        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    elif 'spreadsheetml' in ct_xml:
                        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    elif 'presentationml' in ct_xml:
                        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"

                if 'mimetype' in names:
                    with zf.open('mimetype') as f:
                        mime = f.read().decode('utf-8', errors='ignore').strip()
                        if mime == 'application/vnd.oasis.opendocument.text':
                            return "application/vnd.oasis.opendocument.text"

                if 'word/document.xml' in names:
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

                return None
        except (zipfile.BadZipFile, zipfile.LargeZipFile, Exception) as e:
            logger.warning(f"ZIP inspection failed: {e}")
            return None

    def _detect_image_format(self, content: bytes) -> Optional[str]:
        """Detect image format from magic bytes."""
        if len(content) < 8:
            return None

        if content.startswith(self.PNG_MAGIC):
            return "image/png"
        if content.startswith(self.JPEG_MAGIC):
            return "image/jpeg"
        if content.startswith(self.GIF87_MAGIC) or content.startswith(self.GIF89_MAGIC):
            return "image/gif"
        if content.startswith(self.BMP_MAGIC):
            return "image/bmp"
        if content.startswith(self.TIFF_LE_MAGIC) or content.startswith(self.TIFF_BE_MAGIC):
            return "image/tiff"

        return None

    def validate_content_integrity(self, content: bytes, mime_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validate content integrity for the detected MIME type.
        Checks structural requirements to detect corruption.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not content:
            return False, "Empty content"

        # Check minimum size for known formats
        min_size = self.MIN_VALID_SIZES.get(mime_type)
        if min_size and len(content) < min_size:
            return False, f"File too small for {mime_type}: {len(content)} bytes"

        if mime_type == "application/pdf":
            return self._validate_pdf_integrity(content)

        if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return self._validate_docx_integrity(content)

        if mime_type == "application/vnd.oasis.opendocument.text":
            return self._validate_odt_integrity(content)

        if mime_type == "application/rtf":
            return self._validate_rtf_integrity(content)

        if mime_type in ("image/png", "image/jpeg", "image/gif", "image/bmp"):
            return self._validate_image_integrity(content, mime_type)

        # Text-based formats — just check decodability
        if mime_type in ("text/plain", "text/html"):
            try:
                content[:102400].decode('utf-8', errors='strict')
                return True, None
            except UnicodeDecodeError:
                try:
                    content[:102400].decode('latin-1', errors='strict')
                    return True, None
                except Exception:
                    return False, "Content is not valid text"

        return True, None

    def _validate_pdf_integrity(self, content: bytes) -> Tuple[bool, Optional[str]]:
        """Validate PDF structural integrity."""
        if not content.startswith(b'%PDF-'):
            return False, "Missing PDF header"

        # Check for EOF marker
        if not content.rstrip().endswith(b'%%EOF'):
            return False, "Missing PDF EOF marker"

        # Cross-reference table check
        if b'xref' not in content:
            return False, "Missing PDF xref table"

        # Check for trailer
        if b'trailer' not in content:
            return False, "Missing PDF trailer"

        return True, None

    def _validate_docx_integrity(self, content: bytes) -> Tuple[bool, Optional[str]]:
        """Validate DOCX (ZIP) structural integrity."""
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = [info.filename.lower() for info in zf.infolist()]

                if '[content_types].xml' not in names:
                    return False, "Missing [Content_Types].xml"

                if 'word/document.xml' not in names:
                    return False, "Missing word/document.xml"

                # Test that word/document.xml is readable
                with zf.open('word/document.xml') as f:
                    f.read(1)

                return True, None
        except zipfile.BadZipFile:
            return False, "Corrupted ZIP structure"
        except Exception as e:
            return False, f"DOCX validation failed: {e}"

    def _validate_odt_integrity(self, content: bytes) -> Tuple[bool, Optional[str]]:
        """Validate ODT (ZIP) structural integrity."""
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = [info.filename.lower() for info in zf.infolist()]

                if 'mimetype' not in names:
                    return False, "Missing mimetype file"

                if 'content.xml' not in names:
                    return False, "Missing content.xml"

                # Verify mimetype matches
                with zf.open('mimetype') as f:
                    mime = f.read().decode('utf-8', errors='ignore').strip()
                    if mime != 'application/vnd.oasis.opendocument.text':
                        return False, f"Invalid ODT mimetype: {mime}"

                return True, None
        except zipfile.BadZipFile:
            return False, "Corrupted ZIP structure"
        except Exception as e:
            return False, f"ODT validation failed: {e}"

    def _validate_rtf_integrity(self, content: bytes) -> Tuple[bool, Optional[str]]:
        """Validate RTF structural integrity."""
        if not (content.startswith(b'{\\rtf') or content.startswith(b'{\\RTF')):
            return False, "Missing RTF header"

        # Check for closing brace
        try:
            text = content.decode('ascii', errors='ignore')
            if text.count('{') != text.count('}'):
                return False, "Mismatched RTF braces"
        except Exception:
            return False, "RTF decode failed"

        return True, None

    def _validate_image_integrity(self, content: bytes, mime_type: str) -> Tuple[bool, Optional[str]]:
        """Validate image structural integrity for common formats."""
        if mime_type == "image/png":
            if len(content) < 33 or not content.startswith(self.PNG_MAGIC):
                return False, "Corrupted PNG header"
            # Check IEND chunk presence
            if b'IEND' not in content:
                return False, "Missing PNG IEND chunk"

        elif mime_type == "image/jpeg":
            if not content.startswith(self.JPEG_MAGIC):
                return False, "Corrupted JPEG header"
            # Check for end marker
            if not content.rstrip().endswith(b'\xff\xd9'):
                return False, "Missing JPEG EOI marker"

        elif mime_type == "image/gif":
            if not (content.startswith(b'GIF87a') or content.startswith(b'GIF89a')):
                return False, "Corrupted GIF header"
            if not content.endswith(b'\x3b'):
                return False, "Missing GIF trailer"

        return True, None

    @traceable(name="detect_mime_type", run_type="chain")
    async def detect(self, filename: str, content: Optional[bytes] = None) -> str:
        """
        Detect MIME type using filename and content inspection.
        Content-based detection takes priority over extension.

        Args:
            filename: Original filename
            content: Optional file content for magic number detection

        Returns:
            Detected MIME type

        Raises:
            MimeDetectionError: If type cannot be determined
        """
        mime_type = None
        detection_method = "extension"

        if content:
            mime_type = self.detect_from_content(content)
            detection_method = "magic_bytes" if mime_type else "extension"

        if not mime_type:
            mime_type = self.detect_from_extension(filename)

        if mime_type:
            MIME_DETECTION_COUNT.labels(method=detection_method, result="detected").inc()
            logger.debug(f"MIME detected: {mime_type} (method={detection_method})", extra={
                "filename": filename,
                "mime_type": mime_type,
                "method": detection_method
            })
            return mime_type

        MIME_DETECTION_COUNT.labels(method="none", result="undetected").inc()
        logger.warning(f"Could not detect MIME type for: {filename}")
        raise MimeDetectionError(f"Could not detect MIME type for: {filename}")

    @traceable(name="validate_document", run_type="chain")
    async def validate(
        self,
        filename: str,
        content: bytes,
    ) -> MimeValidationResult:
        """
        Full validation: detect MIME, check integrity, verify extension match,
        check support status. Single comprehensive validation call.

        Args:
            filename: Original filename
            content: File content bytes

        Returns:
            MimeValidationResult with complete validation details

        Raises:
            UnsupportedFormatError: If format is not supported for processing
            CorruptedFileError: If the file structure is corrupted
            ExtensionMismatchError: If extension doesn't match content (warning-level)
        """
        warnings = []
        start = time.monotonic()

        # Step 1: Detect MIME type from content (most reliable)
        content_mime = self.detect_from_content(content)
        detection_method = "magic_bytes" if content_mime else "extension"

        # Step 2: If content detection failed, try extension
        extension_mime = self.detect_from_extension(filename)

        if content_mime:
            mime_type = content_mime
        elif extension_mime:
            mime_type = extension_mime
            warnings.append(f"Content-based detection failed, using extension: {extension_mime}")
        else:
            MIME_DETECTION_COUNT.labels(method="none", result="undetected").inc()
            raise MimeDetectionError(f"Could not detect MIME type for: {filename}")

        # Step 3: Check if content MIME matches extension MIME
        extension_matches = True
        if content_mime and extension_mime and content_mime != extension_mime:
            # Special case: .txt files auto-detected as text/plain are fine
            if not (extension_mime == "text/plain" and content_mime == "text/plain"):
                extension_matches = False
                warnings.append(
                    f"Extension mismatch: filename suggests {extension_mime}, "
                    f"content is {content_mime}"
                )

        # Step 4: Validate content integrity
        is_valid = True
        is_corrupted = False
        integrity_error = None

        if len(content) > self.MAX_SCRUTINY_SIZE:
            # For very large files, skip deep validation
            warnings.append("File exceeds scrutiny size limit, skipping deep validation")
        else:
            is_valid, integrity_error = self.validate_content_integrity(content, mime_type)
            if not is_valid:
                is_corrupted = True
                warnings.append(f"Content integrity issue: {integrity_error}")
                MIME_CORRUPTED_COUNT.labels(format=mime_type).inc()

        # Step 5: Check processing support
        is_supported = self.is_supported(mime_type)
        if not is_supported:
            MIME_UNSUPPORTED_COUNT.labels(detected_type=mime_type).inc()

        # Build metadata
        metadata = {
            "filename": filename,
            "detected_mime": mime_type,
            "extension_mime": extension_mime,
            "content_matches_extension": extension_matches,
            "content_size_bytes": len(content),
            "integrity_error": integrity_error,
            "detection_method": detection_method,
        }

        elapsed = time.monotonic() - start
        PARSER_LATENCY.labels(format="mime_validation").observe(elapsed)

        MIME_DETECTION_COUNT.labels(
            method=detection_method,
            result="supported" if is_supported else "unsupported"
        ).inc()

        result = MimeValidationResult(
            mime_type=mime_type,
            detected_method=detection_method,
            is_valid=is_valid,
            is_supported=is_supported,
            is_corrupted=is_corrupted,
            extension_matches_content=extension_matches,
            metadata=metadata,
            warnings=warnings,
        )

        if is_corrupted:
            logger.error(f"Corrupted file detected: {filename} — {integrity_error}")
            raise CorruptedFileError(f"File appears corrupted: {integrity_error}")

        if not is_supported:
            raise UnsupportedFormatError(
                f"Unsupported file type for processing: {mime_type}"
            )

        if warnings:
            logger.warning(f"MIME validation warnings for {filename}: {warnings}")

        return result

    def is_supported(self, mime_type: str) -> bool:
        """Check if MIME type is supported for document processing."""
        return mime_type in self.SUPPORTED_PROCESSING_TYPES

    def is_image(self, mime_type: str) -> bool:
        """Check if MIME type is an image format (requires OCR path)."""
        return mime_type in {
            "image/png", "image/jpeg", "image/gif",
            "image/bmp", "image/tiff"
        }

    def get_extension(self, mime_type: str) -> Optional[str]:
        """Get preferred file extension for a MIME type."""
        return self.MIME_TO_EXTENSION.get(mime_type)

    # LangGraph node interface
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node entry point.

        Args:
            state: ProcessingState dict

        Returns:
            State update dict
        """
        from .interfaces import ProcessingStatus

        filename = state["filename"]
        content = state.get("_content")

        try:
            if content:
                validation = await self.validate(filename, content)
                return {
                    "content_type": validation.mime_type,
                    "status": ProcessingStatus.PARSING
                }

            mime_type = await self.detect(filename, content)

            if not self.is_supported(mime_type):
                return {
                    "content_type": mime_type,
                    "status": ProcessingStatus.FAILED,
                    "error_message": f"Unsupported file type: {mime_type}"
                }

            return {
                "content_type": mime_type,
                "status": ProcessingStatus.PARSING
            }

        except (MimeDetectionError, CorruptedFileError, UnsupportedFormatError) as e:
            return {
                "content_type": None,
                "status": ProcessingStatus.FAILED,
                "error_message": str(e)
            }


mime_detector = MimeDetectorPipeline()
