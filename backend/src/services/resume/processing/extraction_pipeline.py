"""
Production-grade entity extraction pipeline.
Real GLiNER NER integration for resume entity extraction.
Stateless, async-safe, retry-safe, observable.
LangGraph node compatible.
"""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional

try:
    from src.services.privacy.gliner_model import gliner_model
except ImportError:
    gliner_model = None

from src.observability.metrics import (
    AGENT_NODE_LATENCY_HIST,
    AGENT_RETRIES,
)
from .interfaces import (
    ExtractionResult,
    ProcessingStatus,
    RetryablePipelineError,
)

logger = logging.getLogger(__name__)

_EXTRACT_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="extractor-")

# GLiNER labels for resume entity extraction
RESUME_LABELS = [
    "person",
    "email",
    "phone number",
    "address",
    "organization",
    "job title",
    "skill",
    "degree",
    "school",
    "date",
    "location",
    "url",
    "certification",
    "language",
]

LABEL_MAP = {
    "person": "PERSON",
    "email": "EMAIL",
    "phone number": "PHONE",
    "address": "ADDRESS",
    "organization": "ORGANIZATION",
    "job title": "JOB_TITLE",
    "skill": "SKILL",
    "degree": "DEGREE",
    "school": "SCHOOL",
    "date": "DATE",
    "location": "LOCATION",
    "url": "URL",
    "certification": "CERTIFICATION",
    "language": "LANGUAGE",
}


class ExtractionPipeline:
    """
    Production-grade entity extraction pipeline using GLiNER.

    Capabilities:
    - Real GLiNER NER for resume-specific entity types
    - Batch processing for long texts
    - Confidence filtering
    - Entity deduplication
    - Structured output for downstream pipelines
    - Graceful degradation when GLiNER model unavailable
    """

    ENTITY_TYPES = ["PERSON", "ORGANIZATION", "LOCATION", "DATE", "EMAIL",
                    "PHONE", "SKILL", "JOB_TITLE", "DEGREE", "SCHOOL",
                    "CERTIFICATION", "LANGUAGE", "URL"]

    def __init__(self):
        self._model_available = None  # Lazy check on first use

    def _ensure_model(self):
        """Lazy-load and check GLiNER model availability."""
        if self._model_available is not None:
            return self._model_available
        try:
            from src.services.privacy.gliner_model import gliner_model, _ensure_model
            _ensure_model()
            self._model_available = gliner_model is not None
        except Exception:
            self._model_available = False
        if not self._model_available:
            logger.warning("GLiNER model not loaded — extraction will use regex fallback only")
        return self._model_available

    async def extract(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
        confidence_threshold: float = 0.4,
    ) -> ExtractionResult:
        """
        Extract entities from resume text using GLiNER.

        Args:
            text: Resume text to analyze
            entity_types: Optional list of entity types to extract
            confidence_threshold: Minimum confidence score (0-1)

        Returns:
            ExtractionResult with structured entities
        """
        if not text:
            raise RetryablePipelineError("Empty text provided for extraction")

        start = time.monotonic()
        logger.info(f"Extracting entities (length: {len(text)})")

        try:
            loop = asyncio.get_event_loop()

            entities = await loop.run_in_executor(
                _EXTRACT_EXECUTOR,
                self._extract_sync,
                text,
                confidence_threshold,
            )

            # Map GLiNER labels to standard entity types
            mapped = self._map_entities(entities, entity_types)

            total_count = sum(len(v) for v in mapped.values())

            elapsed = time.monotonic() - start
            AGENT_NODE_LATENCY_HIST.labels(node="extraction").observe(elapsed)

            result = ExtractionResult(
                entities=mapped,
                entity_count=total_count,
                metadata={
                    "model": "gliner" if self._ensure_model() else "regex_fallback",
                    "text_length": len(text),
                    "entity_types_used": entity_types or self.ENTITY_TYPES,
                    "confidence_threshold": confidence_threshold,
                    "extraction_duration_ms": round(elapsed * 1000, 2),
                },
            )

            logger.info(
                "Entity extraction complete",
                extra={
                    "entity_count": total_count,
                    "entity_types": list(mapped.keys()),
                    "model_used": "gliner" if self._ensure_model() else "fallback",
                },
            )

            return result

        except Exception as e:
            AGENT_RETRIES.labels(node="extraction").inc()
            logger.error(f"Entity extraction failed: {e}")
            raise RetryablePipelineError(f"Entity extraction failed: {e}")

    def _extract_sync(
        self,
        text: str,
        confidence_threshold: float,
    ) -> List[Dict[str, Any]]:
        """
        Synchronous extraction logic.

        Uses GLiNER model or falls back to regex.
        For long texts, splits into overlapping chunks to avoid
        GLiNER context window limits.
        """
        max_text_length = 4000  # GLiNER works best with shorter texts
        if len(text) <= max_text_length:
            return self._extract_from_chunk(text, confidence_threshold)

        # Split long text into overlapping chunks
        all_entities = []
        chunk_size = max_text_length
        overlap = 500

        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            chunk_entities = self._extract_from_chunk(chunk, confidence_threshold)
            # Adjust offsets to original text positions
            for e in chunk_entities:
                e["start"] += i
                e["end"] += i
            all_entities.extend(chunk_entities)

        # Deduplicate overlapping entities
        return self._deduplicate_entities(all_entities)

    def _extract_from_chunk(
        self,
        text: str,
        confidence_threshold: float,
    ) -> List[Dict[str, Any]]:
        """Extract entities from a single text chunk."""
        if self._ensure_model() and gliner_model is not None:
            return self._extract_with_gliner(text, confidence_threshold)
        else:
            return self._extract_with_regex(text)

    def _extract_with_gliner(
        self,
        text: str,
        confidence_threshold: float,
    ) -> List[Dict[str, Any]]:
        """Extract entities using GLiNER model."""
        try:
            predictions = gliner_model.predict_entities(
                text, RESUME_LABELS, threshold=confidence_threshold
            )
            entities = []
            for pred in predictions:
                category = LABEL_MAP.get(pred["label"], pred["label"].upper())
                entities.append({
                    "type": category,
                    "text": pred["text"],
                    "start": pred["start"],
                    "end": pred["end"],
                    "confidence": round(pred.get("score", 0.6), 4),
                    "source": "gliner",
                })
            return entities
        except Exception as e:
            logger.error(f"GLiNER prediction error: {e}")
            return []

    def _extract_with_regex(self, text: str) -> List[Dict[str, Any]]:
        """
        Regex-based entity extraction fallback.
        Used when GLiNER model is unavailable.
        """
        import re
        entities = []

        patterns = {
            "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
            "PHONE": r'(?:\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
            "URL": r'https?://(?:www\.)?[-\w@:%.+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-\w@:%+.~#?&/=]*)',
            "DATE": r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b',
        }

        for entity_type, pattern in patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Check for overlap with already detected entities
                overlap = any(
                    e["start"] <= match.start() < e["end"]
                    or e["start"] < match.end() <= e["end"]
                    for e in entities
                )
                if not overlap:
                    entities.append({
                        "type": entity_type,
                        "text": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.85,
                        "source": "regex",
                    })

        return entities

    def _deduplicate_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate entities (same text + overlapping positions)."""
        if not entities:
            return []

        entities.sort(key=lambda x: (x["start"], -x["confidence"]))
        deduped = []

        for ent in entities:
            if not deduped:
                deduped.append(ent)
                continue

            last = deduped[-1]
            # Check if this entity overlaps with the previous one
            if ent["start"] < last["end"]:
                # Keep the one with higher confidence
                if ent["confidence"] > last["confidence"]:
                    deduped[-1] = ent
            else:
                deduped.append(ent)

        return deduped

    def _map_entities(
        self,
        raw_entities: List[Dict[str, Any]],
        requested_types: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Map raw entities into grouped dictionary by entity type.

        Returns:
            Dict with entity type as key and list of entity dicts as value.
            Each entity dict contains: text, start, end, confidence, source.
        """
        mapped: Dict[str, List[Dict[str, Any]]] = {}
        allowed = set(requested_types) if requested_types else None

        for ent in raw_entities:
            etype = ent.get("type", "OTHER")
            if allowed and etype not in allowed:
                continue

            if etype not in mapped:
                mapped[etype] = []

            mapped[etype].append({
                "text": ent["text"],
                "start": ent.get("start", 0),
                "end": ent.get("end", 0),
                "confidence": ent.get("confidence", 0.5),
                "source": ent.get("source", "unknown"),
            })

        # Sort entities within each type by start position
        for etype in mapped:
            mapped[etype].sort(key=lambda x: x["start"])

        return mapped

    # ── LangGraph Node Interface ─────────────────────────────────────

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node entry point for entity extraction.

        Args:
            state: ProcessingState dict

        Returns:
            State update dict with entities
        """
        # Prefer normalized text for better entity recognition
        text = state.get("normalized_text") or state.get("raw_text")

        if not text:
            return {
                "entities": None,
                "extraction_error": "No text to extract from",
                "status": ProcessingStatus.FAILED,
            }

        try:
            result = await self.extract(text)

            return {
                "entities": {
                    "entities": result.entities,
                    "entity_count": result.entity_count,
                    "metadata": result.metadata,
                },
                "extraction_error": None,
                "status": ProcessingStatus.MASKING,
            }

        except RetryablePipelineError as e:
            return {
                "entities": None,
                "extraction_error": str(e),
                "status": ProcessingStatus.EXTRACTING,
            }


extraction_pipeline = ExtractionPipeline()
