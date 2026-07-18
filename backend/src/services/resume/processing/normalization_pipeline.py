"""
Production-grade normalization pipeline.
Whitespace normalization, Unicode normalization (NFKC), OCR cleanup,
section reconstruction, heading preservation, bullet normalization.

Stateless, async-safe, retry-safe, observable.
LangGraph node compatible.
"""
import asyncio
import logging
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Tuple

from src.observability.metrics import (
    NORMALIZATION_COUNT,
    NORMALIZATION_LATENCY,
    NORMALIZATION_FIXES,
)
from .interfaces import (
    NormalizationResult,
    ResumeSection,
    NormalizationMetrics,
    ProcessingStatus,
    RetryablePipelineError,
)

logger = logging.getLogger(__name__)

_NORM_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="normalizer-")

# ── Section Detection Patterns ──────────────────────────────────────

SECTION_PATTERNS: Dict[str, re.Pattern] = {
    "contact": re.compile(
        r'^(?:CONTACT|PERSONAL\s+INFORMATION|CONTACT\s+INFORMATION)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    "summary": re.compile(
        r'^(?:SUMMARY|PROFESSIONAL\s+SUMMARY|PROFILE|OBJECTIVE|CAREER\s+OBJECTIVE|'
        r'EXECUTIVE\s+SUMMARY|PERSONAL\s+STATEMENT)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    "experience": re.compile(
        r'^(?:EXPERIENCE|WORK\s+EXPERIENCE|EMPLOYMENT|PROFESSIONAL\s+EXPERIENCE|'
        r'WORK\s+HISTORY|CAREER\s+HISTORY|PROFESSIONAL\s+HISTORY|'
        r'EMPLOYMENT\s+HISTORY|RELEVANT\s+EXPERIENCE)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    "education": re.compile(
        r'^(?:EDUCATION|ACADEMIC|QUALIFICATIONS|ACADEMIC\s+QUALIFICATIONS|'
        r'EDUCATIONAL\s+QUALIFICATIONS|ACADEMIC\s+BACKGROUND|'
        r'EDUCATIONAL\s+BACKGROUND)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    "skills": re.compile(
        r'^(?:SKILLS?|TECHNICAL\s+SKILLS?|CORE\s+COMPETENCIES?|'
        r'TECHNICAL\s+COMPETENCIES?|KEY\s+SKILLS?|AREAS\s+OF\s+EXPERTISE|'
        r'TECHNOLOGIES?|TOOLS?\s*&?\s*TECHNOLOGIES?)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    "projects": re.compile(
        r'^(?:PROJECTS?|PERSONAL\s+PROJECTS?|KEY\s+PROJECTS?|'
        r'NOTABLE\s+PROJECTS?|RELEVANT\s+PROJECTS?|PORTFOLIO)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    "certifications": re.compile(
        r'^(?:CERTIFICATIONS?|CERTIFICATES?|PROFESSIONAL\s+CERTIFICATIONS?|'
        r'LICENSES?|CREDENTIALS?)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    "languages": re.compile(
        r'^(?:LANGUAGES?|LANGUAGE\s+SKILLS?|LANGUAGE\s+PROFICIENCY)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    "interests": re.compile(
        r'^(?:INTERESTS?|HOBBIES?|ACTIVITIES?|EXTRACURRICULAR)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    "publications": re.compile(
        r'^(?:PUBLICATIONS?|RESEARCH|PAPERS?|PATENTS?)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    "references": re.compile(
        r'^(?:REFERENCES?|REFEREES?)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    "awards": re.compile(
        r'^(?:AWARDS?|HONORS?|ACHIEVEMENTS?|RECOGNITION|DISTINCTIONS?)\s*:?\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
}

# Map alternative names to canonical section types
SECTION_ALIAS_MAP: Dict[str, str] = {
    "work experience": "experience",
    "employment": "experience",
    "work history": "experience",
    "career history": "experience",
    "professional history": "experience",
    "employment history": "experience",
    "relevant experience": "experience",
    "professional experience": "experience",
    "academic": "education",
    "qualifications": "education",
    "academic qualifications": "education",
    "educational qualifications": "education",
    "academic background": "education",
    "educational background": "education",
    "technical skills": "skills",
    "core competencies": "skills",
    "technical competencies": "skills",
    "key skills": "skills",
    "areas of expertise": "skills",
    "technologies": "skills",
    "tools & technologies": "skills",
    "personal projects": "projects",
    "key projects": "projects",
    "notable projects": "projects",
    "relevant projects": "projects",
    "portfolio": "projects",
    "professional certifications": "certifications",
    "licenses": "certifications",
    "credentials": "certifications",
    "profile": "summary",
    "objective": "summary",
    "career objective": "summary",
    "executive summary": "summary",
    "personal statement": "summary",
    "contact information": "contact",
    "personal information": "contact",
    "language skills": "languages",
    "language proficiency": "languages",
    "hobbies": "interests",
    "activities": "interests",
    "extracurricular": "interests",
    "research": "publications",
    "papers": "publications",
    "patents": "publications",
    "honors": "awards",
    "achievements": "awards",
    "recognition": "awards",
    "distinctions": "awards",
}

# ── OCR Cleanup Patterns ────────────────────────────────────────────

OCR_GARBAGE_RE = re.compile(r'[|]{2,}|_{3,}|-{4,}|={3,}|~{3,}|#{3,}')
OCR_PAGE_NUMBER_RE = re.compile(r'^\s*\d{1,4}\s*$', re.MULTILINE)
OCR_ARTIFACT_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
OCR_LIGATURE_MAP: Dict[str, str] = {
    '\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl',
    '\ufb03': 'ffi', '\ufb04': 'ffl', '\ufb05': 'st',
    '\ufb06': 'st',
}

# ── Bullet Patterns ─────────────────────────────────────────────────

BULLET_PATTERNS = [
    re.compile(r'^[\s]*[•‣⁃◦◉◈▪▫◆◇○●◎⚫⚪][\s]+'),
    re.compile(r'^[\s]*[–—−-][\s]+'),
    re.compile(r'^[\s]*[*][\s]+'),
    re.compile(r'^[\s]*\d+\.[\s]+'),
    re.compile(r'^[\s]*[a-zA-Z]\)[\s]+'),
    re.compile(r'^[\s]*\([a-zA-Z\d]+\)[\s]+'),
    re.compile(r'^[\s]*[a-zA-Z]\.[\s]+'),
]

STANDARD_BULLET = '• '


class NormalizationPipeline:
    """
    Production-grade text normalization pipeline.

    Capabilities:
    - Unicode NFKC normalization
    - Whitespace normalization (collapse multiple spaces, normalize newlines)
    - OCR artifact cleanup (garbage lines, page numbers, ligatures, control chars)
    - Section detection and reconstruction
    - Heading preservation with confidence scoring
    - Bullet point normalization and standardization
    - Duplicate line removal
    """

    def __init__(self):
        self._section_boundaries: List[Tuple[int, int, str, str]] = []

    async def normalize(
        self,
        text: str,
        entities: Optional[Dict] = None,
        ocr_mode: bool = False,
        enable_section_reconstruction: bool = True,
    ) -> NormalizationResult:
        """
        Normalize resume text through the full pipeline.

        Args:
            text: Raw text to normalize
            entities: Optional extracted entities
            ocr_mode: Enable aggressive OCR-specific cleanup
            enable_section_reconstruction: Detect and preserve section structure

        Returns:
            NormalizationResult with normalized text, sections, and metrics
        """
        if not text:
            raise RetryablePipelineError("Empty text provided for normalization")

        start = time.monotonic()
        metrics = NormalizationMetrics()
        raw_length = len(text)

        logger.info(f"Normalizing text (length: {raw_length}, ocr_mode: {ocr_mode})")

        try:
            loop = asyncio.get_event_loop()

            # Stage 1: Unicode normalization
            text, uc_fixes = await loop.run_in_executor(
                _NORM_EXECUTOR, self._normalize_unicode, text
            )
            metrics.unicode_fixes = uc_fixes

            # Stage 2: OCR cleanup (always run, more aggressive in ocr_mode)
            text, ocr_fixes = await loop.run_in_executor(
                _NORM_EXECUTOR, self._clean_ocr_artifacts, text, ocr_mode
            )
            metrics.ocr_fixes = ocr_fixes

            # Stage 3: Whitespace normalization
            text, ws_fixes = await loop.run_in_executor(
                _NORM_EXECUTOR, self._normalize_whitespace, text
            )
            metrics.whitespace_fixes = ws_fixes

            # Stage 4: Duplicate line removal
            text, dup_count = await loop.run_in_executor(
                _NORM_EXECUTOR, self._remove_duplicate_lines, text
            )
            metrics.duplicate_lines_removed = dup_count

            # Stage 5: Bullet normalization
            text, bullet_count = await loop.run_in_executor(
                _NORM_EXECUTOR, self._normalize_bullets, text
            )
            metrics.bullets_normalized = bullet_count

            # Stage 6: Section detection and reconstruction
            sections: List[ResumeSection] = []
            if enable_section_reconstruction:
                sections_raw = await loop.run_in_executor(
                    _NORM_EXECUTOR, self._detect_and_reconstruct_sections, text
                )
                sections = sections_raw
                metrics.section_headers_detected = len(sections)

            elapsed = time.monotonic() - start
            metrics.preprocessing_duration_ms = round(elapsed * 1000, 2)

            NORMALIZATION_COUNT.labels(status="success").inc()
            NORMALIZATION_LATENCY.observe(elapsed)

            if metrics.whitespace_fixes:
                NORMALIZATION_FIXES.labels(fix_type="whitespace").inc(metrics.whitespace_fixes)
            if metrics.unicode_fixes:
                NORMALIZATION_FIXES.labels(fix_type="unicode").inc(metrics.unicode_fixes)
            if metrics.ocr_fixes:
                NORMALIZATION_FIXES.labels(fix_type="ocr").inc(metrics.ocr_fixes)
            if metrics.bullets_normalized:
                NORMALIZATION_FIXES.labels(fix_type="bullet").inc(metrics.bullets_normalized)

            result = NormalizationResult(
                normalized_text=text,
                sections=sections,
                section_count=len(sections),
                metrics=metrics,
                metadata={
                    "original_length": raw_length,
                    "normalized_length": len(text),
                    "length_change_pct": round(
                        (len(text) - raw_length) / max(raw_length, 1) * 100, 2
                    ),
                    "ocr_mode": ocr_mode,
                    "preprocessing_duration_ms": metrics.preprocessing_duration_ms,
                },
            )

            logger.info(
                "Normalization complete",
                extra={
                    "original_length": raw_length,
                    "normalized_length": len(text),
                    "sections_found": len(sections),
                    "fixes": {
                        "whitespace": ws_fixes,
                        "unicode": uc_fixes,
                        "ocr": ocr_fixes,
                        "bullets": bullet_count,
                        "duplicates": dup_count,
                    },
                },
            )

            return result

        except Exception as e:
            NORMALIZATION_COUNT.labels(status="error").inc()
            logger.error(f"Normalization failed: {e}")
            raise RetryablePipelineError(f"Content normalization failed: {e}")

    # ── Unicode Normalization ────────────────────────────────────────

    def _normalize_unicode(self, text: str) -> Tuple[str, int]:
        """Apply NFKC normalization and fix common Unicode issues."""
        fixes = 0
        original = text

        # NFKC normalization (decompose + recompose)
        text = unicodedata.normalize("NFKC", text)

        # Replace smart quotes with ASCII
        quote_map = {
            '\u2018': "'", '\u2019': "'",  # single quotes
            '\u201c': '"', '\u201d': '"',  # double quotes
            '\u2013': '-', '\u2014': '—',  # en/em dashes
            '\u00a0': ' ',                  # non-breaking space
            '\u2026': '...',               # ellipsis
            '\u00b4': "'",                 # acute accent used as quote
            '\u2032': "'", '\u2033': '"',  # prime marks
            '\u2039': '<', '\u203a': '>',  # single guillemets
            '\u00ab': '<<', '\u00bb': '>>',# double guillemets
            '\u00b7': '-',                 # middle dot → hyphen
            '\u2212': '-',                 # minus sign
            '\u00d7': 'x',                 # multiplication sign
            '\u2044': '/',                 # fraction slash
        }
        for orig, repl in quote_map.items():
            count = text.count(orig)
            if count > 0:
                text = text.replace(orig, repl)
                fixes += count

        # Replace common OCR ligature confusions
        for lig, replacement in OCR_LIGATURE_MAP.items():
            if lig in text:
                count = text.count(lig)
                text = text.replace(lig, replacement)
                fixes += count

        if text != original:
            logger.debug(f"Unicode normalization: {fixes} fixes applied")

        return text, fixes

    # ── OCR Artifact Cleanup ─────────────────────────────────────────

    def _clean_ocr_artifacts(self, text: str, aggressive: bool = False) -> Tuple[str, int]:
        """Remove OCR artifacts: garbage lines, control chars, stray marks."""
        fixes = 0

        # Remove control characters (except standard whitespace)
        text, ctrl_count = OCR_ARTIFACT_RE.subn('', text)
        fixes += ctrl_count

        # Remove garbage separator lines (long runs of single characters)
        text, garbage_count = OCR_GARBAGE_RE.subn('', text)
        fixes += garbage_count

        # Process line by line for remaining cleanup
        lines = text.splitlines()
        cleaned_lines: List[str] = []

        for line in lines:
            stripped = line.strip()

            # Skip standalone page numbers
            if OCR_PAGE_NUMBER_RE.match(stripped) and len(stripped) <= 4:
                fixes += 1
                continue

            # Skip lines that are only special characters
            if aggressive and re.match(r'^[\s\W]*$', stripped):
                fixes += 1
                continue

            # Skip extremely short garbage lines in aggressive mode
            if aggressive and len(stripped) < 3 and not stripped.isalpha():
                fixes += 1
                continue

            # Fix OCR-specific letter confusions
            if aggressive:
                ocr_fix_map = {
                    '|': 'l',  # pipe confused with 'l'
                    '0': 'O',  # zero for capital O in middle of words
                }
                # Only fix '|' if it appears in word-like contexts
                if '|' in stripped:
                    stripped, pipe_count = re.subn(
                        r'(?<=\w)\|(?=\w)', 'l', stripped
                    )
                    fixes += pipe_count

            cleaned_lines.append(stripped)

        return '\n'.join(cleaned_lines), fixes

    # ── Whitespace Normalization ─────────────────────────────────────

    def _normalize_whitespace(self, text: str) -> Tuple[str, int]:
        """Normalize whitespace: collapse spaces, normalize line endings."""
        fixes = 0

        # Normalize line endings to \n
        old_len = len(text)
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        fixes += old_len - len(text)

        # Collapse multiple spaces to single space (preserve line structure)
        text, space_count = re.subn(r'[^\S\n]{2,}', ' ', text)
        fixes += space_count

        # Remove trailing whitespace from each line
        text, trail_count = re.subn(r'[ \t]+$', '', text, flags=re.MULTILINE)
        fixes += trail_count

        # Remove leading whitespace from each line (preserve intentional indentation? No — normalize)
        text, lead_count = re.subn(r'^[ \t]+', '', text, flags=re.MULTILINE)
        fixes += lead_count

        # Collapse 3+ blank lines to exactly 2 (preserve section separation)
        text, blank_count = re.subn(r'\n{3,}', '\n\n', text)
        fixes += blank_count

        # Remove blank lines at start/end
        text = text.strip() + '\n'

        return text, fixes

    # ── Duplicate Line Removal ───────────────────────────────────────

    def _remove_duplicate_lines(self, text: str) -> Tuple[str, int]:
        """Remove consecutive duplicate lines (common OCR artifact)."""
        lines = text.splitlines()
        deduped: List[str] = []
        prev = None
        removed = 0

        for line in lines:
            stripped = line.strip()
            if stripped == prev and len(stripped) > 0:
                removed += 1
                continue
            prev = stripped
            deduped.append(line)

        return '\n'.join(deduped), removed

    # ── Bullet Normalization ─────────────────────────────────────────

    def _normalize_bullets(self, text: str) -> Tuple[str, int]:
        """Standardize all bullet types to '• ' prefix."""
        lines = text.splitlines()
        normalized_lines: List[str] = []
        bullet_count = 0

        for line in lines:
            matched = False
            for pattern in BULLET_PATTERNS:
                m = pattern.match(line)
                if m:
                    bullet_end = m.end()
                    content = line[bullet_end:].strip()
                    normalized_lines.append(f"{STANDARD_BULLET}{content}")
                    bullet_count += 1
                    matched = True
                    break
            if not matched:
                normalized_lines.append(line)

        return '\n'.join(normalized_lines), bullet_count

    # ── Section Detection & Reconstruction ───────────────────────────

    def _detect_and_reconstruct_sections(self, text: str) -> List[ResumeSection]:
        """
        Detect resume sections, reconstruct boundaries, and return structured sections.

        Strategy:
        1. Scan line-by-line for section header patterns
        2. Group content between headers into sections
        3. Assign canonical section types
        4. Preserve heading formatting
        5. Calculate character offsets
        """
        sections: List[ResumeSection] = []
        lines = text.splitlines()
        section_breaks: List[Tuple[int, str, str]] = []  # (line_idx, raw_heading, canonical_type)

        for i, line in enumerate(lines):
            stripped = line.strip().upper()
            if len(stripped) > 40:  # Section headers are typically short
                continue

            for section_type, pattern in SECTION_PATTERNS.items():
                if pattern.match(stripped):
                    section_breaks.append((i, line.strip(), section_type))
                    break

        # If no sections found, treat entire text as one "general" section
        if not section_breaks:
            full_content = text.strip()
            char_end = len(full_content) if full_content else 0
            sections.append(
                ResumeSection(
                    section_type="general",
                    heading="",
                    content=full_content,
                    normalized_content=full_content,
                    char_start=0,
                    char_end=char_end,
                    metadata={"auto_detected": True, "line_count": len(lines)},
                )
            )
            return sections

        # Group content between section breaks
        char_offset = 0
        for idx, (break_line, heading, sec_type) in enumerate(section_breaks):
            # Determine content range
            content_start = break_line + 1
            if idx + 1 < len(section_breaks):
                content_end = section_breaks[idx + 1][0]
            else:
                content_end = len(lines)

            # Extract content lines
            content_lines = lines[content_start:content_end]
            content = '\n'.join(content_lines).strip()

            # Calculate character offsets in the full text
            heading_idx_in_text = text.find(heading)
            if heading_idx_in_text >= 0:
                char_start = heading_idx_in_text
                if idx + 1 < len(section_breaks):
                    next_heading = section_breaks[idx + 1][1]
                    next_idx = text.find(next_heading, char_start + len(heading))
                    char_end = next_idx if next_idx >= 0 else len(text)
                else:
                    char_end = len(text)
            else:
                char_start = char_offset
                char_end = char_start + len(content) + len(heading) + 1

            char_offset = char_end

            sections.append(
                ResumeSection(
                    section_type=sec_type,
                    heading=heading,
                    content=content,
                    normalized_content=content,
                    char_start=char_start,
                    char_end=char_end,
                    metadata={
                        "heading_line": break_line,
                        "line_count": len(content_lines),
                        "word_count": len(content.split()) if content else 0,
                        "auto_detected": True,
                        "confidence": 0.95,
                    },
                )
            )

        # Check for content before the first section header (usually contact info)
        if section_breaks and section_breaks[0][0] > 0:
            preamble_lines = lines[: section_breaks[0][0]]
            preamble = '\n'.join(preamble_lines).strip()
            if preamble and len(preamble.split()) >= 2:
                # Calculate character offset for preamble
                preamble_end = text.find(section_breaks[0][1]) if section_breaks[0][1] in text else len(preamble)
                sections.insert(
                    0,
                    ResumeSection(
                        section_type="preamble",
                        heading="",
                        content=preamble,
                        normalized_content=preamble,
                        char_start=0,
                        char_end=preamble_end if preamble_end > 0 else len(preamble),
                        metadata={
                            "auto_detected": True,
                            "line_count": len(preamble_lines),
                            "word_count": len(preamble.split()),
                            "confidence": 0.85,
                        },
                    ),
                )

        return sections

    # ── LangGraph Node Interface ─────────────────────────────────────

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node entry point for normalization.

        Args:
            state: ProcessingState dict

        Returns:
            State update dict with normalized_text, normalized_sections, normalization_metrics
        """
        text = state.get("masked_text") or state.get("raw_text")
        entities = state.get("entities")

        if isinstance(entities, dict) and "entities" in entities:
            entities = entities["entities"]

        if not text:
            return {
                "normalized_text": None,
                "normalized_sections": None,
                "normalization_error": "No text to normalize",
                "status": ProcessingStatus.FAILED,
            }

        # Check if OCR was used (for aggressive cleanup mode)
        ocr_text = state.get("ocr_text")
        ocr_mode = bool(ocr_text and len(ocr_text) > 50)

        try:
            result = await self.normalize(
                text=text,
                entities=entities,
                ocr_mode=ocr_mode,
                enable_section_reconstruction=True,
            )

            return {
                "normalized_text": result.normalized_text,
                "normalized_sections": [s.to_dict() for s in result.sections],
                "normalization_metrics": {
                    "whitespace_fixes": result.metrics.whitespace_fixes,
                    "unicode_fixes": result.metrics.unicode_fixes,
                    "ocr_fixes": result.metrics.ocr_fixes,
                    "section_headers_detected": result.metrics.section_headers_detected,
                    "bullets_normalized": result.metrics.bullets_normalized,
                    "duplicate_lines_removed": result.metrics.duplicate_lines_removed,
                    "preprocessing_duration_ms": result.metrics.preprocessing_duration_ms,
                    "original_length": result.metadata["original_length"],
                    "normalized_length": result.metadata["normalized_length"],
                },
                "normalization_error": None,
                "status": ProcessingStatus.CHUNKING,
            }

        except RetryablePipelineError as e:
            return {
                "normalized_text": None,
                "normalization_error": str(e),
                "status": ProcessingStatus.NORMALIZING,
            }


normalization_pipeline = NormalizationPipeline()
