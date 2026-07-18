"""
Payload size monitoring for Qdrant vector storage.

Prevents payload bloat by monitoring bytes-per-vector, flagging oversized payloads,
and applying truncation safeguards to text fields.

Stateless, async-safe, observable.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List

from src.observability.metrics import (
    EMBED_PAYLOAD_BYTES,
    EMBED_PAYLOAD_BLOAT,
    EMBED_PAYLOAD_TRUNCATIONS,
)

logger = logging.getLogger(__name__)

# Payload size thresholds
MAX_PAYLOAD_BYTES = 50 * 1024          # 50KB per point soft limit
MAX_PAYLOAD_BYTES_HARD = 200 * 1024    # 200KB hard limit
MAX_TEXT_FIELD_BYTES = 32 * 1024       # 32KB per text field before truncation
MAX_METADATA_BYTES = 16 * 1024         # 16KB for metadata dict before stripping

# Fields that can be safely truncated
TRUNCATABLE_FIELDS = {"text", "embedding_text", "metadata"}
TEXT_FIELDS = {"text", "embedding_text"}


@dataclass
class PayloadSizeReport:
    """Report of payload size analysis for a batch."""
    total_points: int
    total_bytes: int
    avg_bytes_per_point: float
    max_bytes_per_point: int
    oversized_count: int
    truncated_count: int
    truncated_fields: Dict[str, int] = field(default_factory=dict)


def measure_payload_bytes(payload: Dict[str, Any]) -> int:
    """Measure the JSON-serialized size of a payload in bytes."""
    try:
        return len(json.dumps(payload, default=str).encode("utf-8"))
    except Exception:
        return -1


def truncate_text_field(text: str, max_bytes: int) -> str:
    """Truncate a text field to fit within max_bytes while preserving whole characters."""
    if not text:
        return text
    encoded = text.encode("utf-8", errors="ignore")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes]
    return truncated.decode("utf-8", errors="ignore")


def sanitize_payload(
    payload: Dict[str, Any],
    collection: str = "careeros_resumes",
    truncate: bool = True,
) -> Dict[str, Any]:
    """Validate and optionally truncate a payload to prevent bloat.

    Returns the (possibly truncated) payload.
    """
    sanitized = dict(payload)
    bytes_before = measure_payload_bytes(sanitized)

    # Track bytes
    if bytes_before > 0:
        EMBED_PAYLOAD_BYTES.labels(collection=collection).observe(bytes_before)

    # Check hard limit
    if bytes_before > MAX_PAYLOAD_BYTES_HARD:
        EMBED_PAYLOAD_BLOAT.labels(collection=collection).inc()
        logger.error(
            f"Payload exceeds hard limit ({bytes_before}B > {MAX_PAYLOAD_BYTES_HARD}B) "
            f"for collection '{collection}'"
        )
        if truncate:
            for field in TEXT_FIELDS:
                if field in sanitized and isinstance(sanitized[field], str):
                    sanitized[field] = truncate_text_field(
                        sanitized[field], MAX_TEXT_FIELD_BYTES
                    )
                    EMBED_PAYLOAD_TRUNCATIONS.labels(
                        collection=collection, field=field
                    ).inc()

            if "metadata" in sanitized and isinstance(sanitized["metadata"], dict):
                meta_json = json.dumps(sanitized["metadata"], default=str)
                if len(meta_json.encode("utf-8")) > MAX_METADATA_BYTES:
                    sanitized["metadata"] = {"_truncated": True}
                    EMBED_PAYLOAD_TRUNCATIONS.labels(
                        collection=collection, field="metadata"
                    ).inc()

    elif bytes_before > MAX_PAYLOAD_BYTES:
        logger.warning(
            f"Payload exceeds soft limit ({bytes_before}B > {MAX_PAYLOAD_BYTES}B) "
            f"for collection '{collection}'"
        )
        EMBED_PAYLOAD_BLOAT.labels(collection=collection).inc()

    return sanitized


def analyze_payload_batch(
    payloads: List[Dict[str, Any]],
    collection: str = "careeros_resumes",
) -> PayloadSizeReport:
    """Analyze a batch of payloads for size metrics.

    Returns a size report without modifying the payloads.
    """
    total_points = len(payloads)
    if total_points == 0:
        return PayloadSizeReport(
            total_points=0,
            total_bytes=0,
            avg_bytes_per_point=0.0,
            max_bytes_per_point=0,
            oversized_count=0,
            truncated_count=0,
        )

    total_bytes = 0
    max_bytes = 0
    oversized_count = 0

    for payload in payloads:
        size = measure_payload_bytes(payload)
        if size > 0:
            total_bytes += size
            max_bytes = max(max_bytes, size)
            EMBED_PAYLOAD_BYTES.labels(collection=collection).observe(size)
            if size > MAX_PAYLOAD_BYTES:
                oversized_count += 1

    return PayloadSizeReport(
        total_points=total_points,
        total_bytes=total_bytes,
        avg_bytes_per_point=round(total_bytes / total_points, 1),
        max_bytes_per_point=max_bytes,
        oversized_count=oversized_count,
        truncated_count=0,
    )


def sanitize_payload_batch(
    payloads: List[Dict[str, Any]],
    collection: str = "careeros_resumes",
) -> List[Dict[str, Any]]:
    """Sanitize an entire batch of payloads.

    Returns sanitized payloads and logs a summary.
    """
    if not payloads:
        return payloads

    sanitized = []
    truncated_count = 0
    truncated_fields: Dict[str, int] = {}

    for payload in payloads:
        result = sanitize_payload(payload, collection=collection, truncate=True)
        sanitized.append(result)

        original_bytes = measure_payload_bytes(payload)
        result_bytes = measure_payload_bytes(result)
        if result_bytes < original_bytes:
            truncated_count += 1
            for field in TRUNCATABLE_FIELDS:
                if payload.get(field) != result.get(field):
                    truncated_fields[field] = truncated_fields.get(field, 0) + 1

    if truncated_count > 0:
        logger.info(
            f"Payload sanitization: {truncated_count}/{len(payloads)} truncated "
            f"for collection '{collection}'"
        )

    return sanitized
