"""
Citation alignment: evidence-to-claim mapping and source verification.

Maps Claude's response claims back to retrieval citations, detects orphan
citations, identifies unsupported statements, and preserves evidence lineage.

Stateless, async-safe, observable. Worker-safe.
"""
import logging
import re
from typing import Dict, Any, List, Optional

from src.schemas.intelligence import GroundedClaim, EvidenceReference
from src.schemas.retrieval import Citation

logger = logging.getLogger(__name__)


class CitationAlignment:
    """Aligns Claude claims with retrieval citations and verifies evidence sources."""

    def align(
        self,
        claims: List[str],
        context: str,
        citations: List[Citation],
    ) -> List[GroundedClaim]:
        """Align extracted claims with retrieval citations.

        Each claim is mapped to supporting evidence references.
        Unsupported claims are flagged.
        """
        grounded: List[GroundedClaim] = []

        for claim in claims:
            evidence = self._find_evidence(claim, context, citations)
            supported = len(evidence) > 0

            grounded.append(
                GroundedClaim(
                    claim=claim,
                    confidence=min(1.0, 0.3 + (len(evidence) * 0.2)),
                    evidence=evidence,
                    unsupported=not supported,
                )
            )

        return grounded

    def _find_evidence(
        self,
        claim: str,
        context: str,
        citations: List[Citation],
    ) -> List[EvidenceReference]:
        """Find citation evidence supporting a claim."""
        refs: List[EvidenceReference] = []
        claim_lower = claim.lower()
        claim_tokens = set(re.findall(r"\b[a-z]{3,}\b", claim_lower))

        for cit in citations:
            # Check if claim references this citation's content
            if cit.source and cit.source.lower() in claim_lower:
                refs.append(EvidenceReference(
                    citation_id=cit.citation_id,
                    source=cit.source,
                    chunk_id=cit.chunk_id,
                    snippet=claim[:100],
                ))
                continue

            # Token overlap check
            if cit.chunk_id:
                cit_text = f"{cit.source or ''} {cit.chunk_id}".lower()
                cit_tokens = set(re.findall(r"\b[a-z]{3,}\b", cit_text))
                overlap = len(claim_tokens & cit_tokens) / max(len(claim_tokens), 1)
                if overlap >= 0.2:
                    refs.append(EvidenceReference(
                        citation_id=cit.citation_id,
                        source=cit.source,
                        chunk_id=cit.chunk_id,
                        snippet=claim[:100],
                    ))

        return refs

    def extract_claims(self, response: Dict[str, Any]) -> List[str]:
        """Extract claims from a structured Claude response."""
        claims: List[str] = []
        response_text = json_dump_safe(response)

        # Extract sentences that look like claims (>30 chars, ends with period)
        sentences = re.findall(r"[A-Z][^.!?]*[.!?]", response_text)
        for s in sentences:
            if len(s) > 30 and any(
                w in s.lower()
                for w in ["is", "has", "does", "shows", "indicates", "demonstrates",
                          "requires", "lacks", "contains", "aligns", "matches"]
            ):
                claims.append(s.strip())

        return claims

    def detect_unsupported(
        self,
        response: Dict[str, Any],
        context: str,
    ) -> List[str]:
        """Detect statements in response with no support in context."""
        claims = self.extract_claims(response)
        context_tokens = set(re.findall(r"\b[a-z]{3,}\b", context.lower()))

        unsupported: List[str] = []
        for claim in claims:
            claim_tokens = set(re.findall(r"\b[a-z]{3,}\b", claim.lower()))
            overlap = len(claim_tokens & context_tokens) / max(len(claim_tokens), 1)
            if overlap < 0.2:
                unsupported.append(claim)

        return unsupported

    def verify_orphan_citations(
        self,
        citations: List[Citation],
        response: Dict[str, Any],
    ) -> List[int]:
        """Find citations that are never referenced in the response."""
        response_text = json_dump_safe(response)
        cited_ids: set = set()
        for match in re.finditer(r"\[(\d+)\]", response_text):
            cited_ids.add(int(match.group(1)))
        orphan = [c.citation_id for c in citations if c.citation_id not in cited_ids]
        return orphan


def json_dump_safe(obj: Any) -> str:
    try:
        import json
        return json.dumps(obj, default=str)
    except Exception:
        return str(obj)


_alignment: Optional[CitationAlignment] = None


def get_citation_alignment() -> CitationAlignment:
    global _alignment
    if _alignment is None:
        _alignment = CitationAlignment()
    return _alignment


def reset_citation_alignment() -> None:
    global _alignment
    _alignment = None


def __getattr__(name: str):
    if name == "citation_alignment":
        return get_citation_alignment()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
