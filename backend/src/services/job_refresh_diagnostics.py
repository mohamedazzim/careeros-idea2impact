"""Shared helpers for job refresh diagnostics and provider result summaries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def utc_iso(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_provider_query_context(
    source: str,
    *,
    found: int,
    limit: int | None = None,
    query: str | None = None,
    location: str | None = None,
    since: str | None = None,
    configured: bool = True,
    query_count: int | None = None,
    skill_terms: List[str] | None = None,
) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "provider": source,
        "query": query or "direct provider feed",
        "location": location or "India/Remote filters",
        "limit": limit or found or 0,
        "since": since or "not used",
        "configured": configured,
    }
    if query_count is not None:
        context["query_count"] = query_count
    if skill_terms is not None:
        context["skill_terms"] = skill_terms[:5]
    return context


def updated_fields(existing: Any, update_values: Dict[str, Any]) -> List[str]:
    changed: List[str] = []
    for key, new_value in update_values.items():
        current_value = getattr(existing, key, None)
        if current_value != new_value:
            changed.append(key)
    return changed


def updated_job_sample(
    *,
    source: str,
    source_job_id: str,
    job_data: Dict[str, Any],
    fetched_at: datetime,
    updated_fields: List[str],
) -> Dict[str, Any]:
    return {
        "title": str(job_data.get("title") or "")[:160],
        "company": str(job_data.get("company") or "")[:160],
        "provider": source,
        "external_job_id": source_job_id,
        "last_seen_at": utc_iso(fetched_at),
        "updated_fields": updated_fields[:8],
    }


def provider_refresh_message(
    source: str,
    *,
    found: int,
    added: int,
    updated: int,
    duplicates: int,
    expired: int,
) -> str:
    provider_name = source.replace("_", " ").title()
    if found <= 0:
        return f"{provider_name} returned no jobs for the current filters/query."
    if added <= 0 and updated > 0:
        return f"All {found} provider jobs already existed in CareerOS."
    if added <= 0 and updated <= 0 and duplicates > 0:
        return f"All {found} provider jobs were duplicates of existing records."
    if expired > 0 and added <= 0 and updated <= 0:
        return f"{provider_name} only refreshed stale inventory; no new visible jobs were added."
    if added > 0 and updated > 0:
        return f"{provider_name} added {added} new job(s) and refreshed {updated} existing job(s)."
    if added > 0:
        return f"{provider_name} added {added} new job(s)."
    if updated > 0:
        return f"{provider_name} refreshed {updated} existing job(s)."
    return f"{provider_name} completed without visible job changes."


def provider_result_payload(
    *,
    provider: str,
    display_name: str,
    status: str,
    configured: bool,
    provider_blocked: bool,
    billing_required: bool,
    provider_status_code: int,
    found: int,
    normalized: int,
    added: int,
    updated: int,
    duplicates_removed: int,
    expired_removed: int,
    error_count: int,
    message: str,
    query_context: Dict[str, Any] | None = None,
    sample_updated_jobs: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    payload = {
        "provider": provider,
        "display_name": display_name,
        "status": status,
        "configured": configured,
        "provider_blocked": provider_blocked,
        "billing_required": billing_required,
        "provider_status_code": provider_status_code,
        "found": found,
        "normalized": normalized,
        "added": added,
        "updated": updated,
        "duplicates_removed": duplicates_removed,
        "expired_removed": expired_removed,
        "error_count": error_count,
        "message": message,
    }
    if query_context is not None:
        payload["query_context"] = query_context
    if sample_updated_jobs is not None:
        payload["sample_updated_jobs"] = sample_updated_jobs
    return payload
