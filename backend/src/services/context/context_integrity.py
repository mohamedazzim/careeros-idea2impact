"""
Context integrity protection layer.

Validates citation integrity, chronology preservation, overlap corruption
detection, and token-budget overflow safeguards.

Stateless, async-safe, observable. Worker-safe.
"""
import logging
from typing import List, Dict, Any, Set

from src.schemas.retrieval import Citation, AssemblyBlock
from src.services.processing.tokenizer_utils import estimate_tokens
from src.core.config import settings
from src.observability.metrics import (
    CONTEXT_CITATION_ORPHAN,
    CONTEXT_CHRONOLOGY_VIOLATION,
    CONTEXT_OVERLAP_CORRUPTION,
    CONTEXT_OVERFLOW,
)

logger = logging.getLogger(__name__)


class ContextIntegrityGuard:
    """Validates and enforces context assembly integrity."""

    def validate_citations(
        self,
        blocks: List[AssemblyBlock],
        citations: List[Citation],
    ) -> Dict[str, Any]:
        """Validate that every citation references an existing block.

        Returns validation report with orphaned and dangling citations.
        """
        block_ids: Set[int] = {b.block_id for b in blocks}
        citation_ids: Set[int] = set()
        orphaned: List[int] = []
        duplicate_citations: List[int] = []

        for citation in citations:
            if citation.citation_id in citation_ids:
                duplicate_citations.append(citation.citation_id)
            citation_ids.add(citation.citation_id)
            if citation.citation_id not in block_ids:
                orphaned.append(citation.citation_id)

        return {
            "valid": len(orphaned) == 0 and len(duplicate_citations) == 0,
            "total_citations": len(citations),
            "total_blocks": len(blocks),
            "orphaned_citations": orphaned,
            "duplicate_citations": duplicate_citations,
            "citation_coverage": round(
                len(citation_ids) / max(len(block_ids), 1), 2
            ),
        }

    def validate_chronology(
        self,
        blocks: List[AssemblyBlock],
    ) -> Dict[str, Any]:
        """Check that blocks preserve chronological ordering.

        Returns violations if section-type blocks are out of order
        (experience should precede education, etc.).
        """
        section_order = {
            "summary": 0,
            "experience": 1,
            "skills": 2,
            "projects": 3,
            "education": 4,
            "certifications": 5,
            "awards": 6,
            "languages": 7,
            "publications": 8,
            "contact": 9,
            "preamble": 10,
            "general": 11,
        }

        violations: List[Dict[str, Any]] = []
        prev_order = -1

        for i, block in enumerate(blocks):
            block_section = block.section
            current_order = section_order.get(block_section, 11)
            if current_order < prev_order:
                violations.append({
                    "block_id": block.block_id,
                    "section": block_section,
                    "expected_order": f">= {prev_order}",
                    "actual_order": current_order,
                })
            prev_order = current_order

        return {
            "chronology_valid": len(violations) == 0,
            "violations": violations,
            "total_blocks": len(blocks),
        }

    def detect_overlap_corruption(
        self,
        blocks: List[AssemblyBlock],
        overlap_threshold: float = 0.85,
    ) -> Dict[str, Any]:
        """Detect if over-compression corrupted context by identifying
        chunks with suspiciously high overlap that were kept.

        Returns corruption report.
        """
        import re
        tokens_lists: List[Set[str]] = []
        for block in blocks:
            tokens = set(re.findall(r"\b[a-z]{3,}\b", block.text.lower()))
            tokens_lists.append(tokens)

        suspect_pairs: List[Dict[str, Any]] = []
        for i in range(len(tokens_lists)):
            for j in range(i + 1, len(tokens_lists)):
                if tokens_lists[i] and tokens_lists[j]:
                    union = len(tokens_lists[i] | tokens_lists[j])
                    intersection = len(tokens_lists[i] & tokens_lists[j])
                    overlap = intersection / union if union > 0 else 0.0
                    if overlap > overlap_threshold:
                        suspect_pairs.append({
                            "block_a": blocks[i].block_id,
                            "block_b": blocks[j].block_id,
                            "overlap": round(overlap, 4),
                            "severity": "high" if overlap > 0.92 else "medium",
                        })

        return {
            "corruption_detected": len(suspect_pairs) > 0,
            "suspect_pairs": suspect_pairs,
            "total_blocks": len(blocks),
        }

    def validate_token_budget(
        self,
        context: str,
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        """Validate assembled context fits within token budget.

        Returns overflow status and severity.
        """
        effective_max = max_tokens or settings.CONTEXT_MAX_TOKENS
        tokens = estimate_tokens(context, text_type="resume")
        overflow = tokens > effective_max

        severity = "ok"
        if overflow:
            ratio = tokens / max(effective_max, 1)
            if ratio > 1.5:
                severity = "critical"
            elif ratio > 1.25:
                severity = "high"
            elif ratio > 1.1:
                severity = "medium"
            else:
                severity = "low"

        if overflow and settings.CONTEXT_HARD_OVERFLOW_CUTOFF:
            logger.warning(
                f"Context overflow: {tokens}/{effective_max} tokens "
                f"(severity={severity})"
            )

        return {
            "overflow": overflow,
            "severity": severity,
            "actual_tokens": tokens,
            "max_tokens": effective_max,
            "utilization_pct": round(tokens / max(effective_max, 1) * 100, 1),
        }

    def repair(
        self,
        assembled: "ContextAssemblyResult",
        report: Dict[str, Any],
    ) -> "ContextAssemblyResult":
        """Auto-repair integrity violations detected by guard().

        Repairs: citation mismatches, chronology violations, token overflow,
        and duplicate source injection.
        """
        from copy import deepcopy

        fixed = deepcopy(assembled)

        # Fix citation mismatches: remove orphaned citations, add missing
        citation_report = report.get("citations", {})
        if not citation_report.get("valid", True):
            CONTEXT_CITATION_ORPHAN.inc()
            orphaned = set(citation_report.get("orphaned_citations", []))
            fixed.citations = [
                c for c in fixed.citations if c.citation_id not in orphaned
            ]
            block_ids = {b.block_id for b in fixed.blocks}
            existing_ids = {c.citation_id for c in fixed.citations}
            next_id = max(existing_ids | {0}) + 1
            for b in fixed.blocks:
                if b.block_id not in existing_ids:
                    from src.schemas.retrieval import Citation
                    fixed.citations.append(Citation(
                        citation_id=next_id,
                        source=b.source,
                        chunk_id=b.chunks[0]["chunk_id"] if b.chunks else None,
                    ))
                    next_id += 1

        # Fix chronology violations: reorder blocks
        chrono_report = report.get("chronology", {})
        if not chrono_report.get("chronology_valid", True):
            CONTEXT_CHRONOLOGY_VIOLATION.inc()
            section_order = {
                "summary": 0, "experience": 1, "skills": 2, "projects": 3,
                "education": 4, "certifications": 5, "awards": 6,
                "languages": 7, "publications": 8, "contact": 9,
                "preamble": 10, "general": 11,
            }
            fixed.blocks.sort(key=lambda b: section_order.get(b.section, 11))

        # Fix overlap corruption: remove suspect duplicates
        overlap_report = report.get("overlap_corruption", {})
        if overlap_report.get("corruption_detected", False):
            CONTEXT_OVERLAP_CORRUPTION.inc(
                labels={"severity": "high"} if any(
                    p.get("severity") == "high"
                    for p in overlap_report.get("suspect_pairs", [])
                ) else {"severity": "medium"}
            )
            suspect_ids = set()
            for pair in overlap_report.get("suspect_pairs", []):
                suspect_ids.add(pair.get("block_b"))
            fixed.blocks = [
                b for b in fixed.blocks if b.block_id not in suspect_ids
            ]

        # Fix token overflow: drop lowest-relevance blocks
        budget_report = report.get("token_budget", {})
        if budget_report.get("overflow", False):
            CONTEXT_OVERFLOW.labels(severity=budget_report.get("severity", "low")).inc()
            if settings.CONTEXT_HARD_OVERFLOW_CUTOFF:
                max_tokens = budget_report.get("max_tokens", settings.CONTEXT_MAX_TOKENS)
                fixed.blocks.sort(key=lambda b: b.relevance_score, reverse=True)
                from src.services.processing.tokenizer_utils import estimate_tokens
                current = 0
                kept = []
                for b in fixed.blocks:
                    bt = estimate_tokens(b.text, text_type="resume")
                    if current + bt <= max_tokens * 0.95:
                        kept.append(b)
                        current += bt
                fixed.blocks = kept

        # Rebuild context
        parts = []
        for b in fixed.blocks:
            header = f"[{b.block_id}] Source: {b.source}"
            if b.section and b.section != "general":
                header += f" | Section: {b.section}"
            parts.append(f"{header}\n{b.text}")
        fixed.context = "\n\n".join(parts)

        return fixed

    def guard(
        self,
        blocks: List[AssemblyBlock],
        citations: List[Citation],
        context: str,
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        """Full integrity guard check across all dimensions.

        Returns combined integrity report.
        """
        citation_report = self.validate_citations(blocks, citations)
        chronology_report = self.validate_chronology(blocks)
        overlap_report = self.detect_overlap_corruption(blocks)
        budget_report = self.validate_token_budget(context, max_tokens)

        all_valid = (
            citation_report["valid"]
            and chronology_report["chronology_valid"]
            and not overlap_report["corruption_detected"]
            and not budget_report["overflow"]
        )

        return {
            "integrity_valid": all_valid,
            "citations": citation_report,
            "chronology": chronology_report,
            "overlap_corruption": overlap_report,
            "token_budget": budget_report,
        }


_integrity_guard: ContextIntegrityGuard | None = None


def get_integrity_guard() -> ContextIntegrityGuard:
    global _integrity_guard
    if _integrity_guard is None:
        _integrity_guard = ContextIntegrityGuard()
    return _integrity_guard


def reset_integrity_guard() -> None:
    global _integrity_guard
    _integrity_guard = None


def __getattr__(name: str):
    if name == "integrity_guard":
        return get_integrity_guard()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
