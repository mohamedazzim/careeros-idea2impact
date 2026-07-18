"""
Production-grade semantic chunking pipeline.
Section-aware, token-aware, overlap strategy, metadata preservation.
Stateless, async-safe, retry-safe, observable.
LangGraph node compatible.
"""
import asyncio
import hashlib
import logging
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional

from src.observability.metrics import (
    CHUNKING_COUNT,
    CHUNKING_LATENCY,
    CHUNK_SIZE_HIST,
)
from .interfaces import (
    ChunkResult,
    SemanticChunk,
    SectionBoundary,
    ChunkingStrategy,
    ProcessingStatus,
    RetryablePipelineError,
)

logger = logging.getLogger(__name__)

_CHUNK_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="chunker-")

# ── Resume Section Detection ────────────────────────────────────────

SECTION_KEYWORDS: Dict[str, List[str]] = {
    "experience": [
        "experience", "employment", "work history", "career history",
        "professional experience", "employment history",
    ],
    "education": [
        "education", "academic", "qualifications", "academic background",
        "educational background", "degrees",
    ],
    "skills": [
        "skills", "technical skills", "core competencies", "technologies",
        "tools", "expertise", "proficiencies",
    ],
    "summary": [
        "summary", "profile", "objective", "executive summary",
        "professional summary", "career objective",
    ],
    "contact": [
        "contact", "personal information", "contact information",
    ],
    "projects": [
        "projects", "project experience", "portfolio", "key projects",
    ],
    "certifications": [
        "certifications", "certificates", "licenses", "credentials",
    ],
    "education_train": [
        "training", "workshops", "courses", "professional development",
    ],
    "languages": [
        "languages", "language skills", "language proficiency",
    ],
    "awards": [
        "awards", "honors", "achievements", "recognition",
    ],
    "publications": [
        "publications", "papers", "research", "patents",
    ],
}

SECTION_HEADER_RE = re.compile(
    r'^('
    r'[A-Z][A-Z\s&]{1,40}'
    r'|(?:EXPERIENCE|EDUCATION|SKILLS?|PROJECTS?|CERTIFICATIONS?|'
    r'SUMMARY|PROFILE|OBJECTIVE|ACHIEVEMENTS?|LANGUAGES?|'
    r'PUBLICATIONS?|AWARDS?|HONORS?|TRAINING|REFERENCES?|'
    r'INTERESTS?|EXTRACURRICULAR|COURSES?|TECHNICAL\s+SKILLS?|'
    r'WORK\s+HISTORY|PROFESSIONAL\s+EXPERIENCE|EMPLOYMENT|'
    r'PERSONAL\s+INFORMATION|CONTACT)'
    r')\s*:?\s*$',
    re.IGNORECASE | re.MULTILINE,
)


class ChunkingPipeline:
    """
    Production-grade semantic chunking pipeline.

    Capabilities:
    - Section-aware chunking (preserves resume section boundaries)
    - Token-aware chunk sizing (approximated via word-based tokens)
    - Sliding window overlap strategy
    - Metadata preservation (section, position, boundaries, token count)
    - Sentence-boundary respect
    - Chunk ID generation (deterministic hash-based)
    """

    def __init__(self, strategy: Optional[ChunkingStrategy] = None):
        self.strategy = strategy or ChunkingStrategy()
        self._approx_tokens_per_word = 1.3

    async def chunk(
        self,
        text: str,
        sections: Optional[List[Dict[str, Any]]] = None,
        strategy: Optional[ChunkingStrategy] = None,
    ) -> ChunkResult:
        """
        Chunk text into semantically meaningful segments.

        Args:
            text: Text to chunk
            sections: Pre-detected sections from normalization pipeline
            strategy: Chunking strategy configuration

        Returns:
            ChunkResult with semantic chunks and section boundaries
        """
        if not text:
            raise RetryablePipelineError("Empty text provided for chunking")

        strat = strategy or self.strategy
        start = time.monotonic()

        logger.info(
            f"Semantic chunking (length: {len(text)}, "
            f"max_tokens: {strat.max_chunk_tokens}, overlap: {strat.overlap_tokens})"
        )

        try:
            loop = asyncio.get_event_loop()

            result = await loop.run_in_executor(
                _CHUNK_EXECUTOR,
                self._chunk_sync,
                text,
                sections,
                strat,
            )

            elapsed = time.monotonic() - start

            CHUNKING_COUNT.labels(method="semantic", status="success").inc()
            CHUNKING_LATENCY.labels(method="semantic").observe(elapsed)

            # Record chunk size distribution
            for chunk in result.chunks:
                section_label = chunk.section if chunk.section else "unknown"
                CHUNK_SIZE_HIST.labels(section=section_label).observe(chunk.token_count)

            return result

        except Exception as e:
            CHUNKING_COUNT.labels(method="semantic", status="error").inc()
            logger.error(f"Chunking failed: {e}")
            raise RetryablePipelineError(f"Semantic chunking failed: {e}")

    def _chunk_sync(
        self,
        text: str,
        sections: Optional[List[Dict[str, Any]]],
        strat: ChunkingStrategy,
    ) -> ChunkResult:
        """
        Synchronous chunking logic (runs in thread pool).

        Algorithm:
        1. Detect section boundaries from text OR use provided sections
        2. Split text into section-level blocks
        3. Within each section, split into token-bounded chunks
        4. Apply overlapping window strategy
        5. Generate metadata for each chunk
        """
        # Detect section boundaries
        boundaries = self._detect_section_boundaries(text, sections)

        # Split into sections and chunk each independently
        all_chunks: List[SemanticChunk] = []
        max_tokens = strat.max_chunk_tokens
        overlap_tokens = strat.overlap_tokens
        chunk_idx = 0

        if not boundaries:
            # No sections detected — chunk entire text as one block
            text_chunks = self._split_text_into_token_chunks(
                text, max_tokens, overlap_tokens, strat.preserve_sentence_boundaries
            )
            for tc in text_chunks:
                chunk_id = self._generate_chunk_id(text, tc["char_start"], tc["char_end"])
                all_chunks.append(
                    SemanticChunk(
                        chunk_id=chunk_id,
                        text=tc["text"],
                        char_start=tc["char_start"],
                        char_end=tc["char_end"],
                        section="general",
                        chunk_type="general",
                        token_count=tc["token_count"],
                        word_count=tc["word_count"],
                        sentence_count=tc["sentence_count"],
                        overlap_with_previous=tc.get("has_overlap_prev", False),
                        overlap_with_next=tc.get("has_overlap_next", False),
                        metadata={
                            "boundary_type": "no_sections",
                            "chunk_global_index": chunk_idx,
                        },
                    )
                )
                chunk_idx += 1
        else:
            # Chunk within each section
            for b_idx, boundary in enumerate(boundaries):
                section_text = text[boundary.char_start:boundary.char_end]
                section_chunks = self._split_text_into_token_chunks(
                    section_text,
                    max_tokens,
                    overlap_tokens,
                    strat.preserve_sentence_boundaries,
                )

                for tc in section_chunks:
                    global_char_start = boundary.char_start + tc["char_start"]
                    global_char_end = boundary.char_start + tc["char_end"]
                    chunk_id = self._generate_chunk_id(
                        section_text, tc["char_start"], tc["char_end"]
                    )

                    all_chunks.append(
                        SemanticChunk(
                            chunk_id=chunk_id,
                            text=tc["text"],
                            char_start=global_char_start,
                            char_end=global_char_end,
                            section=boundary.normalized_name,
                            chunk_type="section_content",
                            token_count=tc["token_count"],
                            word_count=tc["word_count"],
                            sentence_count=tc["sentence_count"],
                            overlap_with_previous=tc.get("has_overlap_prev", False),
                            overlap_with_next=tc.get("has_overlap_next", False),
                            metadata={
                                "boundary_type": "section",
                                "section_name": boundary.name,
                                "section_confidence": boundary.confidence,
                                "chunk_global_index": chunk_idx,
                                "section_chunk_index": len(
                                    [c for c in all_chunks if c.section == boundary.normalized_name]
                                ),
                                "section_char_start": boundary.char_start,
                                "section_char_end": boundary.char_end,
                            },
                        )
                    )
                    chunk_idx += 1

        # Calculate statistics
        if all_chunks:
            avg_size = sum(c.word_count for c in all_chunks) // len(all_chunks)
            avg_tokens = sum(c.token_count for c in all_chunks) // len(all_chunks)
        else:
            avg_size = 0
            avg_tokens = 0

        # Compute section distribution
        section_dist = {}
        for c in all_chunks:
            section_dist[c.section] = section_dist.get(c.section, 0) + 1

        return ChunkResult(
            chunks=all_chunks,
            section_boundaries=boundaries,
            chunk_count=len(all_chunks),
            avg_chunk_size=avg_size,
            avg_chunk_tokens=avg_tokens,
            metadata={
                "method": "semantic_section_aware",
                "max_chunk_tokens": max_tokens,
                "overlap_tokens": overlap_tokens,
                "preserve_sentence_boundaries": strat.preserve_sentence_boundaries,
                "sections_detected": len(boundaries),
                "section_distribution": section_dist,
                "total_tokens": sum(c.token_count for c in all_chunks),
                "total_words": sum(c.word_count for c in all_chunks),
                "chunking_duration_ms": 0,
            },
        )

    # ── Section Boundary Detection ───────────────────────────────────

    def _detect_section_boundaries(
        self,
        text: str,
        provided_sections: Optional[List[Dict[str, Any]]] = None,
    ) -> List[SectionBoundary]:
        """
        Detect resume section boundaries.

        Uses provided sections from normalization pipeline OR scans text
        for section header patterns.
        """
        # Use provided sections if available and valid
        if provided_sections:
            return self._boundaries_from_provided_sections(text, provided_sections)

        # Fallback: scan for section headers
        return self._scan_section_boundaries(text)

    def _boundaries_from_provided_sections(
        self, text: str, sections: List[Dict[str, Any]]
    ) -> List[SectionBoundary]:
        """Convert provided section dicts to SectionBoundary objects."""
        boundaries = []
        for i, sec in enumerate(sections):
            char_start = sec.get("char_start", 0)
            char_end = sec.get("char_end", len(text))

            # Determine end by finding next section's start
            if i + 1 < len(sections):
                next_start = sections[i + 1].get("char_start", len(text))
                if next_start > char_start:
                    char_end = next_start

            boundaries.append(
                SectionBoundary(
                    name=sec.get("heading", sec.get("section_type", "")),
                    normalized_name=sec.get("section_type", "general"),
                    char_start=char_start,
                    char_end=min(char_end, len(text)),
                    confidence=sec.get("metadata", {}).get("confidence", 0.9),
                    heading_level=1,
                )
            )

        return boundaries

    def _scan_section_boundaries(self, text: str) -> List[SectionBoundary]:
        """
        Scan text for section header patterns and build boundaries.
        Falls back when no pre-detected sections are available.
        """
        boundaries = []
        lines = text.splitlines()
        current_section_start = 0
        current_section_name = "preamble"
        char_pos = 0

        line_starts: List[int] = []
        running_pos = 0
        for line in lines:
            line_starts.append(running_pos)
            running_pos += len(line) + 1  # +1 for newline

        for i, line in enumerate(lines):
            stripped = line.strip()
            match = SECTION_HEADER_RE.match(stripped)

            if match and len(stripped) < 50:
                # End previous section
                if i > 0 and line_starts[i] > current_section_start:
                    boundaries.append(
                        SectionBoundary(
                            name=current_section_name,
                            normalized_name=self._normalize_section_name(
                                current_section_name
                            ),
                            start_line=0,
                            char_start=current_section_start,
                            char_end=min(line_starts[i], len(text)),
                            confidence=0.8,
                        )
                    )

                # Start new section
                current_section_name = stripped
                text_pos = line_starts[i]
                # Find actual start offset in text
                heading_idx = text.find(stripped, text_pos if text_pos < len(text) else 0)
                current_section_start = heading_idx if heading_idx >= 0 else text_pos
                char_pos = current_section_start

        # Add final section
        if current_section_start < len(text):
            boundaries.append(
                SectionBoundary(
                    name=current_section_name,
                    normalized_name=self._normalize_section_name(
                        current_section_name
                    ),
                    start_line=0,
                    char_start=current_section_start,
                    char_end=len(text),
                    confidence=0.8,
                )
            )

        return boundaries

    def _normalize_section_name(self, name: str) -> str:
        """Map raw section header to canonical section type."""
        name_lower = name.lower().strip().rstrip(':')
        for canonical, keywords in SECTION_KEYWORDS.items():
            if name_lower in keywords:
                return canonical
            for kw in keywords:
                if name_lower.startswith(kw) or kw in name_lower:
                    return canonical
        return "general"

    # ── Token-Aware Chunk Splitting ──────────────────────────────────

    def _split_text_into_token_chunks(
        self,
        text: str,
        max_tokens: int,
        overlap_tokens: int,
        preserve_sentences: bool,
    ) -> List[Dict[str, Any]]:
        """
        Split text into token-bounded chunks with optional overlap.

        Strategy:
        1. Split text into sentences (respect sentence boundaries)
        2. Build chunks sentence-by-sentence until nearing max_tokens
        3. Slide window forward by (chunk_size - overlap_tokens) for next chunk
        4. Track character offsets for each chunk
        """
        if not text.strip():
            return []

        # Split into sentences
        sentences = self._split_sentences(text) if preserve_sentences else [text]

        # Build token-bounded chunks
        chunks: List[Dict[str, Any]] = []
        current_start_sentence = 0
        current_tokens = 0
        current_chars = 0
        current_sents: List[str] = []

        effective_max = max(max_tokens, 50)  # Minimum chunk size
        effective_overlap = min(overlap_tokens, effective_max // 3)

        for s_idx, sentence in enumerate(sentences):
            sent_tokens = self._estimate_tokens(sentence)
            sent_chars = len(sentence)

            if current_tokens + sent_tokens > effective_max and current_sents:
                # Flush current chunk
                chunk_text = self._join_sentences(current_sents)
                chunks.append({
                    "text": chunk_text,
                    "char_start": current_chars,
                    "char_end": current_chars + len(chunk_text),
                    "token_count": current_tokens,
                    "word_count": len(chunk_text.split()),
                    "sentence_count": len(current_sents),
                    "has_overlap_prev": len(chunks) > 0,
                    "has_overlap_next": True,
                })

                # Calculate overlap: keep last N sentences that fit within overlap_tokens
                overlap_sents = []
                overlap_tok = 0
                for sent in reversed(current_sents):
                    st = self._estimate_tokens(sent)
                    if overlap_tok + st <= effective_overlap:
                        overlap_sents.insert(0, sent)
                        overlap_tok += st
                    else:
                        break

                # Start new chunk with overlap
                current_sents = overlap_sents
                current_tokens = overlap_tok
                current_chars = current_chars + len(chunk_text) - sum(
                    len(s) + 1 for s in overlap_sents
                )

            current_sents.append(sentence)
            current_tokens += sent_tokens

        # Flush final chunk
        if current_sents:
            chunk_text = self._join_sentences(current_sents)
            chunks.append({
                "text": chunk_text,
                "char_start": current_chars,
                "char_end": current_chars + len(chunk_text),
                "token_count": current_tokens,
                "word_count": len(chunk_text.split()),
                "sentence_count": len(current_sents),
                "has_overlap_prev": len(chunks) > 0,
                "has_overlap_next": False,
            })

        # Fix: recalculate char_start/end relative to section text
        char_pos = 0
        for chunk in chunks:
            chunk["char_start"] = char_pos
            chunk["char_end"] = char_pos + len(chunk["text"])
            char_pos = chunk["char_end"] + 1  # +1 for potential separator

        # Mark overlaps
        for i in range(len(chunks)):
            if i == 0:
                chunks[i]["has_overlap_prev"] = False
            if i == len(chunks) - 1:
                chunks[i]["has_overlap_next"] = False

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using a simple regex.
        Avoids heavy NLP dependencies while being reasonably accurate.
        """
        # Split on sentence-ending punctuation followed by space+capital or newline
        sentence_end_re = re.compile(
            r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\n+',
        )

        # Also handle bullet-point lines as sentence-like units
        lines = text.splitlines()
        all_sentences: List[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Treat bullet points and short lines as single sentences
            if stripped.startswith('•') or len(stripped) < 80:
                all_sentences.append(stripped)
            else:
                parts = sentence_end_re.split(stripped)
                all_sentences.extend(p.strip() for p in parts if p.strip())

        return all_sentences

    def _join_sentences(self, sentences: List[str]) -> str:
        """Join sentences with appropriate separators."""
        if not sentences:
            return ""
        return ' '.join(s.strip() for s in sentences if s.strip())

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count from word count.
        Approximation: ~1.3 tokens per word for English text.
        Falls back to character-based estimation (chars/4) for long single 'words'.
        """
        words = text.split()
        if not words:
            return 0
        tokens = sum(max(1, math.ceil(len(w) * 0.3)) for w in words)
        return max(1, tokens)

    def _generate_chunk_id(self, text: str, start: int, end: int) -> str:
        """Generate deterministic chunk ID based on content and position."""
        snippet = text[start:end]
        hasher = hashlib.sha256()
        hasher.update(snippet.encode('utf-8', errors='ignore'))
        hasher.update(f":{start}:{end}".encode())
        return hasher.hexdigest()[:16]

    # ── LangGraph Node Interface ─────────────────────────────────────

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node entry point for chunking.

        Args:
            state: ProcessingState dict

        Returns:
            State update dict with chunks, semantic_chunks, section_boundaries
        """
        # Prefer normalized text, fall back to masked, then raw
        text = (
            state.get("normalized_text")
            or state.get("masked_text")
            or state.get("raw_text")
        )

        if not text:
            return {
                "chunks": None,
                "chunking_error": "No text to chunk",
                "status": ProcessingStatus.FAILED,
            }

        # Get section boundaries from normalization
        sections = state.get("normalized_sections", [])

        try:
            result = await self.chunk(text=text, sections=sections)

            return {
                "chunks": [c.to_dict() for c in result.chunks],
                "semantic_chunks": [c.to_dict() for c in result.chunks],
                "section_boundaries": [b.to_dict() for b in result.section_boundaries],
                "chunking_error": None,
                "status": ProcessingStatus.PREPARING,
            }

        except RetryablePipelineError as e:
            return {
                "chunks": None,
                "chunking_error": str(e),
                "status": ProcessingStatus.CHUNKING,
            }


chunking_pipeline = ChunkingPipeline()
