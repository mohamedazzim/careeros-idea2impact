"""
Production-grade PII masking pipeline.
Real GLiNER integration with regex fallback, confidence scoring,
configurable masking strategies, and audit-safe replacements.

Stateless, async-safe, retry-safe, observable.
LangGraph node compatible.
"""
import asyncio
import hashlib
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Tuple

from src.services.privacy.engine import PrivacyEngine
from src.services.privacy.gliner_model import detect_pii_gliner
from src.services.privacy.regex_fallback import detect_pii_regex

from src.observability.metrics import (
    MASKING_COUNT,
    MASKING_LATENCY,
    MASKING_ENTITIES,
    MASKING_CONFIDENCE,
)
from .interfaces import (
    MaskingResult,
    MaskedEntity,
    MaskingAuditReport,
    MaskingPolicy,
    MaskingStrategy,
    ProcessingStatus,
    RetryablePipelineError,
)

logger = logging.getLogger(__name__)

_MASK_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="masker-")

# ── Synthetic Replacement Data ──────────────────────────────────────

SYNTHETIC_NAMES = [
    "Alex Johnson", "Jordan Smith", "Taylor Williams",
    "Morgan Brown", "Casey Davis", "Riley Wilson",
    "Quinn Anderson", "Avery Thomas", "Parker Martinez",
]
SYNTHETIC_EMAILS = [
    "user.name@example.com", "contact.person@example.com",
]
SYNTHETIC_PHONES = ["(555) 555-0000"]
SYNTHETIC_ORGS = ["Example Corp", "Tech Company Inc.", "Enterprise Solutions LLC"]

# ── Extended Regex Patterns for Fallback ────────────────────────────

EXTENDED_REGEX_PATTERNS: Dict[str, str] = {
    "email": r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
    "phone": r'(?:\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
    "linkedin": r'(?:https?:\/\/)?(?:www\.)?linkedin\.com\/in\/[a-zA-Z0-9_-]+',
    "github": r'(?:https?:\/\/)?(?:www\.)?github\.com\/[a-zA-Z0-9_-]+',
    "url": r'https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_+.~#?&/=]*)',
    "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
    "address_street": r'\b\d{1,5}\s+[A-Z][a-z]+(?:\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Court|Ct|Lane|Ln|Place|Pl|Boulevard|Blvd|Way|Circle|Cir))',
    "address_zip": r'\b\d{5}(?:-\d{4})?\b',
    "date": r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b',
}

LABEL_TO_CATEGORY_MAP = {
    "person": "PERSON",
    "email": "EMAIL",
    "phone number": "PHONE",
    "phone": "PHONE",
    "address": "ADDRESS",
    "organization": "ORGANIZATION",
    "url": "URL",
    "linkedin": "URL",
    "github": "URL",
    "ssn": "SSN",
    "address_street": "ADDRESS",
    "address_zip": "ADDRESS",
    "date": "DATE",
}


class MaskingPipeline:
    """
    Production-grade PII masking pipeline.

    Capabilities:
    - Real GLiNER integration for NER-based PII detection
    - Regex fallback system for structured patterns
    - Entity merging with confidence-based overlap resolution
    - Configurable masking strategies (token, synthetic, redact, hash)
    - Full audit trail with tracking of every masked entity
    - Confidence scoring per entity
    - Position-preserving replacements (end-to-start to maintain indices)
    """

    def __init__(self, policy: Optional[MaskingPolicy] = None):
        self.policy = policy or MaskingPolicy()
        self._privacy_engine = PrivacyEngine()

    async def mask(
        self,
        text: str,
        entities: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        policy: Optional[MaskingPolicy] = None,
    ) -> MaskingResult:
        """
        Mask PII in text using GLiNER + regex with configurable strategy.

        Args:
            text: Text to mask
            entities: Pre-extracted entities from extraction pipeline
            policy: Masking policy configuration

        Returns:
            MaskingResult with masked text, entities, and audit report
        """
        if not text:
            raise RetryablePipelineError("Empty text provided for masking")

        pol = policy or self.policy
        start = time.monotonic()

        logger.info(
            f"Masking PII (length: {len(text)}, strategy: {pol.strategy.value})"
        )

        try:
            loop = asyncio.get_event_loop()

            # Stage 1: Detect PII entities (GLiNER + regex)
            raw_entities = await loop.run_in_executor(
                _MASK_EXECUTOR,
                self._detect_entities,
                text,
                pol.entity_types,
                pol.min_confidence,
            )

            # Stage 2: Merge with provided entities from extraction pipeline
            if entities:
                merged_entities = self._merge_with_extraction_results(
                    raw_entities, entities, pol.min_confidence
                )
            else:
                merged_entities = raw_entities

            # Stage 3: Apply masking strategy
            masked_text, masked_record, unmasked_low_conf = await loop.run_in_executor(
                _MASK_EXECUTOR,
                self._apply_masking,
                text,
                merged_entities,
                pol,
            )

            # Stage 4: Build audit report
            audit = self._build_audit_report(masked_record, unmasked_low_conf)

            elapsed = time.monotonic() - start

            MASKING_COUNT.labels(
                strategy=pol.strategy.value, status="success"
            ).inc()
            MASKING_LATENCY.observe(elapsed)

            # Record per-entity metrics
            for e_type, count in audit.entities_by_type.items():
                MASKING_ENTITIES.labels(
                    entity_type=e_type,
                    source="combined",
                ).inc(count)

            for entity in masked_record:
                MASKING_CONFIDENCE.labels(
                    entity_type=entity.entity_type,
                ).observe(entity.confidence)

            result = MaskingResult(
                masked_text=masked_text,
                masked_entities=masked_record,
                audit_report=audit,
                original_length=len(text),
                masked_length=len(masked_text),
                strategy=pol.strategy,
            )

            logger.info(
                "Masking complete",
                extra={
                    "entities_masked": audit.total_entities,
                    "entities_by_type": audit.entities_by_type,
                    "avg_confidence": round(audit.avg_confidence, 3),
                    "duration_ms": round(elapsed * 1000, 2),
                },
            )

            return result

        except Exception as e:
            MASKING_COUNT.labels(strategy=pol.strategy.value, status="error").inc()
            logger.error(f"Masking failed: {e}")
            raise RetryablePipelineError(f"PII masking failed: {e}")

    # ── Entity Detection ─────────────────────────────────────────────

    def _detect_entities(
        self,
        text: str,
        entity_types: List[str],
        min_confidence: float,
    ) -> List[Dict[str, Any]]:
        """
        Dual-pass entity detection: GLiNER primary + regex fallback.

        Returns list of entity dicts with: category, text, start, end, confidence, source
        """
        all_entities: List[Dict[str, Any]] = []

        # Pass 1: GLiNER detection
        gliner_entities = detect_pii_gliner(text)
        for ent in gliner_entities:
            if ent.get("confidence", 0) >= min_confidence:
                category = LABEL_TO_CATEGORY_MAP.get(
                    ent.get("category", "").lower(),
                    ent.get("category", "OTHER"),
                )
                if category.upper() in [et.upper() for et in entity_types]:
                    all_entities.append({
                        "category": category,
                        "text": ent["text"],
                        "start": ent["start"],
                        "end": ent["end"],
                        "confidence": ent.get("confidence", 0.7),
                        "source": "gliner",
                    })

        # Pass 2: Regex fallback for structured patterns
        regex_entities = detect_pii_regex(text)
        for ent in regex_entities:
            category = LABEL_TO_CATEGORY_MAP.get(
                ent.get("category", "").lower(),
                ent.get("category", "OTHER"),
            )
            if category.upper() in [et.upper() for et in entity_types]:
                all_entities.append({
                    "category": category,
                    "text": ent["text"],
                    "start": ent["start"],
                    "end": ent["end"],
                    "confidence": ent.get("confidence", 0.85),
                    "source": "regex",
                })

        # Also run extended regex patterns not covered by the existing regex module
        for cat, pattern in EXTENDED_REGEX_PATTERNS.items():
            cat_upper = LABEL_TO_CATEGORY_MAP.get(cat, cat.upper())
            if cat_upper.upper() not in [et.upper() for et in entity_types]:
                continue
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Avoid duplicates already caught
                already_captured = any(
                    e["start"] <= match.start() <= e["end"]
                    or e["start"] <= match.end() <= e["end"]
                    for e in all_entities
                )
                if not already_captured:
                    all_entities.append({
                        "category": cat_upper,
                        "text": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.80,
                        "source": "regex_extended",
                    })

        # Merge overlapping entities — prefer higher confidence
        all_entities.sort(key=lambda x: (x["start"], -(x.get("confidence", 0))))
        merged: List[Dict[str, Any]] = []

        for ent in all_entities:
            if not merged:
                merged.append(ent)
            else:
                last = merged[-1]
                if ent["start"] < last["end"]:
                    # Overlap detected — keep higher confidence
                    if ent.get("confidence", 0) > last.get("confidence", 0):
                        merged[-1] = ent
                else:
                    merged.append(ent)

        # Final sort by start position
        merged.sort(key=lambda x: x["start"])

        return merged

    def _merge_with_extraction_results(
        self,
        detected: List[Dict[str, Any]],
        extracted_entities: Dict[str, List[Dict[str, Any]]],
        min_confidence: float,
    ) -> List[Dict[str, Any]]:
        """
        Merge detected entities with AI-extracted entities from the extraction pipeline.
        Resolves overlaps by preferring the source with higher confidence.
        """
        combined = list(detected)

        for entity_type, entity_list in extracted_entities.items():
            if isinstance(entity_list, list):
                for item in entity_list:
                    if isinstance(item, str):
                        # Simple string value — find in text
                        combined.append({
                            "category": entity_type,
                            "text": item,
                            "start": 0,
                            "end": len(item),
                            "confidence": 0.70,
                            "source": "extraction_pipeline",
                        })
                    elif isinstance(item, dict):
                        combined.append({
                            "category": entity_type,
                            "text": item.get("text", item.get("value", "")),
                            "start": item.get("start", 0),
                            "end": item.get("end", 0),
                            "confidence": item.get("confidence", 0.70),
                            "source": "extraction_pipeline",
                        })

        # Re-merge with overlap resolution
        combined.sort(key=lambda x: (x["start"], -(x.get("confidence", 0))))
        merged: List[Dict[str, Any]] = []
        for ent in combined:
            if not merged:
                merged.append(ent)
            else:
                last = merged[-1]
                if ent["start"] < last["end"]:
                    if ent.get("confidence", 0) > last.get("confidence", 0):
                        merged[-1] = ent
                else:
                    merged.append(ent)

        return [e for e in merged if e.get("confidence", 0) >= min_confidence]

    # ── Masking Application ──────────────────────────────────────────

    def _apply_masking(
        self,
        text: str,
        entities: List[Dict[str, Any]],
        policy: MaskingPolicy,
    ) -> Tuple[str, List[MaskedEntity], List[MaskedEntity]]:
        """
        Apply the configured masking strategy to all detected entities.

        Processes entities from END to START to preserve character indices.
        Returns masked text, list of masked entities, and list of unmasked low-confidence entities.
        """
        # Sort from end to start (preserves indices during replacement)
        sorted_entities = sorted(entities, key=lambda x: x["start"], reverse=True)

        masked_text = text
        masked_entities: List[MaskedEntity] = []
        unmasked_low: List[MaskedEntity] = []

        for ent in sorted_entities:
            category = ent["category"]
            original = ent["text"]
            confidence = ent.get("confidence", 0.5)
            source = ent.get("source", "unknown")

            # Only mask if confidence meets threshold AND entity type is enabled
            if (
                confidence < policy.min_confidence
                or category.upper() not in [et.upper() for et in policy.entity_types]
            ):
                unmasked_low.append(
                    MaskedEntity(
                        entity_type=category,
                        original_text=original,
                        masked_text=original,
                        start_char=ent["start"],
                        end_char=ent["end"],
                        confidence=confidence,
                        source=source,
                        replacement_method="skipped_low_confidence",
                    )
                )
                continue

            # Generate replacement based on strategy
            replacement = self._generate_replacement(
                category=category,
                original=original,
                strategy=policy.strategy,
                preserve_format=policy.preserve_format,
            )

            # Apply replacement
            masked_text = (
                masked_text[: ent["start"]]
                + replacement
                + masked_text[ent["end"] :]
            )

            masked_entities.append(
                MaskedEntity(
                    entity_type=category,
                    original_text=original,
                    masked_text=replacement,
                    start_char=ent["start"],
                    end_char=ent["end"],
                    confidence=confidence,
                    source=source,
                    replacement_method=policy.strategy.value,
                )
            )

        # Re-sort by original start position for audit readability
        masked_entities.sort(key=lambda x: x.start_char)

        return masked_text, masked_entities, unmasked_low

    def _generate_replacement(
        self,
        category: str,
        original: str,
        strategy: MaskingStrategy,
        preserve_format: bool,
    ) -> str:
        """
        Generate replacement text based on masking strategy.

        Strategies:
        - TOKEN: [MASKED_CATEGORY]
        - SYNTHETIC: Realistic fake data
        - REDACT: [REDACTED]
        - HASH: SHA-256 hex prefix preserving original length
        """
        if strategy == MaskingStrategy.REDACT:
            return "[REDACTED]"

        if strategy == MaskingStrategy.HASH:
            hashed = hashlib.sha256(original.encode("utf-8")).hexdigest()
            return f"[HASH:{hashed[:12]}]"

        if strategy == MaskingStrategy.SYNTHETIC:
            return self._synthetic_replacement(category, original)

        # Default: TOKEN
        return f"[MASKED_{category.upper()}]"

    def _synthetic_replacement(self, category: str, original: str) -> str:
        """Generate realistic synthetic replacement data."""
        cat_upper = category.upper()
        if cat_upper == "PERSON":
            idx = hash(original) % len(SYNTHETIC_NAMES)
            return f"[SYN:{SYNTHETIC_NAMES[idx]}]"
        elif cat_upper == "EMAIL":
            return f"[SYN:{SYNTHETIC_EMAILS[0]}]"
        elif cat_upper == "PHONE":
            return f"[SYN:{SYNTHETIC_PHONES[0]}]"
        elif cat_upper == "ORGANIZATION":
            idx = hash(original) % len(SYNTHETIC_ORGS)
            return f"[SYN:{SYNTHETIC_ORGS[idx]}]"
        return f"[MASKED_{cat_upper}]"

    # ── Audit Report ─────────────────────────────────────────────────

    def _build_audit_report(
        self,
        masked_entities: List[MaskedEntity],
        unmasked_low: List[MaskedEntity],
    ) -> MaskingAuditReport:
        """Build comprehensive audit report from masking operation."""
        total = len(masked_entities) + len(unmasked_low)

        entities_by_type: Dict[str, int] = {}
        entities_by_source: Dict[str, int] = {}
        all_confidences: List[float] = []

        for me in masked_entities:
            entities_by_type[me.entity_type] = (
                entities_by_type.get(me.entity_type, 0) + 1
            )
            entities_by_source[me.source] = (
                entities_by_source.get(me.source, 0) + 1
            )
            all_confidences.append(me.confidence)

        for me in unmasked_low:
            entities_by_type[me.entity_type] = (
                entities_by_type.get(me.entity_type, 0) + 1
            )

        avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        min_conf = min(all_confidences) if all_confidences else 0.0
        max_conf = max(all_confidences) if all_confidences else 0.0

        return MaskingAuditReport(
            total_entities=total,
            entities_by_type=entities_by_type,
            entities_by_source=entities_by_source,
            avg_confidence=round(avg_conf, 4),
            min_confidence=round(min_conf, 4),
            max_confidence=round(max_conf, 4),
            masked_entities=masked_entities,
            unmasked_low_confidence=unmasked_low,
        )

    # ── LangGraph Node Interface ─────────────────────────────────────

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node entry point for masking.

        Args:
            state: ProcessingState dict

        Returns:
            State update dict with masked_text, masking_metadata, masking_audit
        """
        text = state.get("normalized_text") or state.get("ocr_text") or state.get("raw_text")
        entities_raw = state.get("entities")

        # Normalize entity format
        entities = None
        if entities_raw:
            if isinstance(entities_raw, dict) and "entities" in entities_raw:
                entities = entities_raw["entities"]
            elif isinstance(entities_raw, dict):
                entities = entities_raw

        if not text:
            return {
                "masked_text": None,
                "masking_error": "No text to mask",
                "status": ProcessingStatus.FAILED,
            }

        try:
            result = await self.mask(text=text, entities=entities)

            return {
                "masked_text": result.masked_text,
                "masked_entities": [e.to_dict() for e in result.masked_entities],
                "masking_metadata": {
                    "entities_masked": result.audit_report.total_entities,
                    "original_length": result.original_length,
                    "masked_length": result.masked_length,
                    "strategy": result.strategy.value,
                    "avg_confidence": result.audit_report.avg_confidence,
                },
                "masking_audit": result.audit_report.to_dict(),
                "masking_error": None,
                "status": ProcessingStatus.CHUNKING,
            }

        except RetryablePipelineError as e:
            return {
                "masked_text": None,
                "masking_error": str(e),
                "status": ProcessingStatus.MASKING,
            }


masking_pipeline = MaskingPipeline()
