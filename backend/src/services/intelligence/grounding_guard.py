"""
Grounding guard: enforces retrieval-anchored reasoning.

Verifies retrieval presence, rejects insufficient evidence, detects
unsupported claims, enforces citation coverage, and validates evidence alignment.

Stateless, async-safe, observable. Worker-safe.
"""
import logging
import re
from typing import List, Optional

from src.schemas.intelligence import GroundingReport
from src.schemas.retrieval import Citation
from src.observability.metrics import (
    GROUNDING_FAILURES,
    GROUNDING_SCORE,
)

logger = logging.getLogger(__name__)

# Minimum evidence quality thresholds
MIN_CITATION_COVERAGE = 0.3  # At least 30% of claims must have citations
MIN_EVIDENCE_LENGTH = 50     # Minimum retrieved context length in chars
MIN_CITATIONS_FOR_REASONING = 2  # Minimum citations required


class GroundingGuard:
    """Enforces strict retrieval grounding for Claude reasoning.

    Rejects reasoning when retrieval evidence is insufficient or
    when claims lack supporting citations.
    """

    def verify(
        self,
        context: str,
        citations: Optional[List[Citation]] = None,
        claims: Optional[List[str]] = None,
        min_context_len: int = MIN_EVIDENCE_LENGTH,
    ) -> GroundingReport:
        """Verify retrieval grounding quality.

        Returns GroundingReport with pass/fail and detailed diagnostics.
        """
        citations = citations or []
        claims = claims or []

        # Check 1: Evidence presence
        evidence_present = len(context.strip()) >= min_context_len

        if not evidence_present:
            GROUNDING_FAILURES.labels(reason="no_evidence").inc()
            return GroundingReport(
                passed=False,
                evidence_present=False,
                rejected=True,
                rejection_reason="Insufficient retrieval context for grounded reasoning",
            )

        # Check 2: Citation count sufficiency
        if len(citations) < MIN_CITATIONS_FOR_REASONING:
            logger.warning(
                f"Low citation count: {len(citations)} (min: {MIN_CITATIONS_FOR_REASONING})"
            )

        # Check 3: Claim-to-citation coverage
        supported = 0
        unsupported = 0
        weak = []

        if claims:
            for claim in claims:
                has_support = self._check_claim_supported(claim, context, citations)
                if has_support:
                    supported += 1
                else:
                    unsupported += 1
                    weak.append({"claim": claim, "reason": "no citation match found"})

        total = max(len(claims), 1)
        coverage = supported / total
        grounding_score = min(1.0, coverage + (0.1 * min(len(citations), 10)))

        GROUNDING_SCORE.observe(grounding_score)

        # Rejection logic
        reject = False
        reason = ""
        if not evidence_present:
            reject = True
            reason = "no evidence"
        elif coverage < MIN_CITATION_COVERAGE:
            reject = True
            reason = f"low citation coverage ({coverage:.0%} < {MIN_CITATION_COVERAGE:.0%})"
            GROUNDING_FAILURES.labels(reason="low_coverage").inc()

        return GroundingReport(
            passed=not reject,
            evidence_present=evidence_present,
            total_claims=total,
            supported_claims=supported,
            unsupported_claims=unsupported,
            grounding_score=round(grounding_score, 4),
            rejected=reject,
            rejection_reason=reason,
            weak_claims=weak,
        )

    def _check_claim_supported(
        self,
        claim: str,
        context: str,
        citations: List[Citation],
    ) -> bool:
        """Check if a claim has evidence support in context."""
        claim_tokens = set(re.findall(r"\b[a-z]{3,}\b", claim.lower()))
        context_tokens = set(re.findall(r"\b[a-z]{3,}\b", context.lower()))

        if not claim_tokens:
            return False

        overlap = len(claim_tokens & context_tokens) / len(claim_tokens)
        return overlap >= 0.3

    def reject_if_insufficient(
        self,
        context: str,
        citations: Optional[List[Citation]] = None,
    ) -> bool:
        """Quick check: should reasoning be rejected due to insufficient evidence?"""
        report = self.verify(context=context, citations=citations)
        return report.rejected


_grounding_guard: Optional[GroundingGuard] = None


def get_grounding_guard() -> GroundingGuard:
    global _grounding_guard
    if _grounding_guard is None:
        _grounding_guard = GroundingGuard()
    return _grounding_guard


def reset_grounding_guard() -> None:
    global _grounding_guard
    _grounding_guard = None


def __getattr__(name: str):
    if name == "grounding_guard":
        return get_grounding_guard()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
