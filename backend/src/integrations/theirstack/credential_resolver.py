"""TheirStack credential resolver with key rotation and legacy alias support.

Reads primary key and optional fallback keys from settings.
Supports legacy THEIRSTACK_API_URL_N aliases treated as keys.
Never prints or logs actual key values.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from src.core.config import settings

logger = logging.getLogger(__name__)

_LEGACY_ALIAS_WARNING = (
    "Using legacy %s as key alias for slot %s; "
    "rename to THEIRSTACK_API_KEY_N for clarity."
)
_LEGACY_ALIAS_SUMMARY_WARNING = (
    "Using %d legacy TheirStack key alias slot(s): %s. "
    "Rename THEIRSTACK_API_URL_N entries to THEIRSTACK_API_KEY_N for clarity."
)
_MAX_KEY_SLOTS = int(getattr(settings, "THEIRSTACK_MAX_KEY_SLOTS", 15) or 15)


@dataclass
class KeySlot:
    slot_name: str
    key: str
    is_legacy: bool = False
    valid: bool = True


@dataclass
class ResolverResult:
    """Result of resolving available TheirStack API keys."""
    slots: List[KeySlot] = field(default_factory=list)
    has_keys: bool = False
    total_slots: int = 0
    warnings: List[str] = field(default_factory=list)


def resolve_keys() -> ResolverResult:
    """Resolve all available TheirStack API key slots.

    Returns a ResolverResult with ordered slots from primary to fallback.
    Never logs or returns actual key values.
    """
    result = ResolverResult()
    legacy_aliases_used: List[str] = []

    # Primary key (legacy single-key name)
    primary = (settings.THEIRSTACK_API_KEY or "").strip()
    seen_keys: set = set()
    if primary:
        result.slots.append(KeySlot(slot_name="primary", key=primary))
        seen_keys.add(primary)
        result.total_slots += 1

    # Canonical KEY_1 through KEY_15
    # KEY_1 is an alias for the primary key — skip if primary already loaded
    loaded_slot_numbers: set = set()
    for i in range(1, _MAX_KEY_SLOTS + 1):
        attr = f"THEIRSTACK_API_KEY_{i}"
        value = getattr(settings, attr, None)
        if value and str(value).strip():
            val = str(value).strip()
            if val in seen_keys:
                continue
            if i == 1 and primary:
                continue
            slot_name = f"key_{i}"
            result.slots.append(KeySlot(slot_name=slot_name, key=val))
            seen_keys.add(val)
            loaded_slot_numbers.add(i)
            result.total_slots += 1

    # Legacy aliases: THEIRSTACK_API_URL_1 through URL_15 treated as keys
    # Skip if: (a) looks like a URL, (b) same value already loaded, (c) same slot number has canonical
    for i in range(1, _MAX_KEY_SLOTS + 1):
        attr = f"THEIRSTACK_API_URL_{i}"
        value = getattr(settings, attr, None)
        if value and str(value).strip():
            val_str = str(value).strip()
            if val_str.startswith("http://") or val_str.startswith("https://"):
                continue
            if val_str in seen_keys:
                continue
            if i in loaded_slot_numbers:
                continue
            slot_name = f"legacy_url_{i}"
            legacy_aliases_used.append(attr)
            result.slots.append(KeySlot(
                slot_name=slot_name,
                key=val_str,
                is_legacy=True,
            ))
            seen_keys.add(val_str)
            result.total_slots += 1

    if legacy_aliases_used:
        aliases_preview = ", ".join(legacy_aliases_used[:5])
        if len(legacy_aliases_used) > 5:
            aliases_preview = f"{aliases_preview}, ..."
        summary_warning = _LEGACY_ALIAS_SUMMARY_WARNING % (
            len(legacy_aliases_used),
            aliases_preview,
        )
        result.warnings.append(summary_warning)
        logger.warning(
            "%s",
            summary_warning,
        )

    result.has_keys = len(result.slots) > 0

    if not result.has_keys:
        logger.warning("No TheirStack API keys configured")

    return result


def mark_invalid(slots: List[KeySlot], slot_name: str) -> None:
    """Mark a key slot as invalid so it won't be retried."""
    for slot in slots:
        if slot.slot_name == slot_name:
            slot.valid = False
            break


def get_next_valid_slot(slots: List[KeySlot], after_slot: Optional[str] = None) -> Optional[KeySlot]:
    """Get the next valid slot after the given slot name."""
    found = after_slot is None
    for slot in slots:
        if not found:
            if slot.slot_name == after_slot:
                found = True
            continue
        if slot.valid:
            return slot
    return None
