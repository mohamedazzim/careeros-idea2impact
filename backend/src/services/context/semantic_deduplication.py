"""
Semantic deduplication service for retrieval context optimization.

Reduces redundant chunks while preserving meaningful content.
- Lexical deduplication (exact/approximate match)
- Semantic overlap reduction (text similarity-based)
- Token-budget-aware compression

Stateless, async-safe, observable. Worker-safe.
"""
import hashlib
import logging
import re
from typing import List, Set

from src.schemas.retrieval import FusedResult

logger = logging.getLogger(__name__)

# N-gram size for overlap detection
NGRAM_SIZE = 4
# Minimum text length to apply overlap detection
MIN_OVERLAP_TEXT_LENGTH = 30
# Overlap ratio threshold (above = considered duplicate)
OVERLAP_THRESHOLD = 0.60


class SemanticDeduplicator:
    """Removes duplicate and highly overlapping chunks."""

    def deduplicate(
        self,
        chunks: List[FusedResult],
        dedup_method: str = "content_hash",
    ) -> List[FusedResult]:
        """Remove duplicates using content-based hashing."""
        if not chunks:
            return []

        seen_hashes: Set[str] = set()
        unique: List[FusedResult] = []

        for chunk in chunks:
            text_hash = hashlib.sha256(
                chunk.text.strip().lower().encode("utf-8", errors="ignore")
            ).hexdigest()

            if text_hash not in seen_hashes:
                seen_hashes.add(text_hash)
                unique.append(chunk)

        removed = len(chunks) - len(unique)
        if removed > 0:
            logger.debug(f"Deduplication removed {removed} duplicate chunks")

        return unique

    def reduce_overlaps(
        self,
        chunks: List[FusedResult],
    ) -> List[FusedResult]:
        """Reduce overlapping chunks using n-gram similarity.

        Preserves the chunk with the higher RRF score when overlaps
        are detected.
        """
        if len(chunks) < 2:
            return chunks

        ngrams: List[Set[str]] = []
        for chunk in chunks:
            tokens = re.findall(r"\b[a-z]{2,}\b", chunk.text.lower())
            ngs = set()
            for i in range(len(tokens) - NGRAM_SIZE + 1):
                ngs.add(" ".join(tokens[i : i + NGRAM_SIZE]))
            ngrams.append(ngs)

        keep: List[FusedResult] = []
        removed: Set[int] = set()

        for i, chunk in enumerate(chunks):
            if i in removed:
                continue
            if len(chunk.text) < MIN_OVERLAP_TEXT_LENGTH:
                keep.append(chunk)
                continue

            for j in range(i + 1, len(chunks)):
                if j in removed:
                    continue
                if len(chunks[j].text) < MIN_OVERLAP_TEXT_LENGTH:
                    continue

                if ngrams[i] and ngrams[j]:
                    union = len(ngrams[i] | ngrams[j])
                    intersection = len(ngrams[i] & ngrams[j])
                    overlap = intersection / union if union > 0 else 0.0

                    if overlap > OVERLAP_THRESHOLD:
                        # Keep higher-scored chunk
                        if chunks[i].rrf_score >= chunks[j].rrf_score:
                            removed.add(j)
                        else:
                            removed.add(i)
                            break

        for i, chunk in enumerate(chunks):
            if i not in removed:
                keep.append(chunk)

        if removed:
            logger.debug(f"Overlap reduction removed {len(removed)} overlapping chunks")

        return keep
