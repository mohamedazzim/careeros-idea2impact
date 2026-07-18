"""Production TheirStack Jobs API client with key rotation."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from src.core.config import settings

from .cache import TheirStackCache
from .credential_resolver import resolve_keys, KeySlot, get_next_valid_slot

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


class TheirStackClientError(RuntimeError):
    pass


@dataclass
class ClientAuditRecord:
    """Safe audit metadata for a single TheirStack API call attempt."""
    key_slot: str = ""
    status_code: int = 0
    is_rate_limited: bool = False
    is_invalid_key: bool = False
    billing_required: bool = False
    provider_blocked: bool = False
    cache_hit: bool = False
    error: Optional[str] = None
    success: bool = False
    data: Optional[Dict[str, Any]] = None
    fetched_count: int = 0


@dataclass
class ClientSearchResult:
    """Result of a TheirStack search with rotation metadata."""
    data: Dict[str, Any] = field(default_factory=dict)
    selected_key_slot: str = ""
    attempted_key_slots: List[str] = field(default_factory=list)
    rate_limited_slots: List[str] = field(default_factory=list)
    invalid_slots: List[str] = field(default_factory=list)
    billing_required: bool = False
    provider_blocked: bool = False
    provider_status_code: int = 0
    fetched_count: int = 0
    cache_hit: bool = False
    success: bool = False
    error: Optional[str] = None


class TheirStackClient:
    """Async client for TheirStack POST /v1/jobs/search with key rotation."""

    def __init__(self, api_key: Optional[str] = None):
        self.base_url = settings.THEIRSTACK_BASE_URL.rstrip("/")
        self.timeout = float(settings.THEIRSTACK_TIMEOUT_SECONDS)
        self.max_retries = int(settings.THEIRSTACK_MAX_RETRIES)
        self.backoff_base = float(settings.THEIRSTACK_RETRY_BACKOFF_BASE)
        self.cache = TheirStackCache()

        # If a specific key is passed (legacy path), use it directly
        if api_key:
            self._slots = [KeySlot(slot_name="primary", key=api_key)]
        else:
            resolved = resolve_keys()
            self._slots = resolved.slots

        self._last_audit: Optional[ClientAuditRecord] = None

    @property
    def configured(self) -> bool:
        return len(self._slots) > 0 and any(s.valid for s in self._slots)

    def _headers_for_key(self, key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CareerOS/2.0",
        }

    def _monitor_headers(self, headers: httpx.Headers) -> Dict[str, Dict[str, Any]]:
        quota = {}
        rate_limit = {}
        for key, value in headers.items():
            lowered = key.lower()
            if "quota" in lowered or "credit" in lowered:
                quota[key] = value
            if "rate" in lowered or "limit" in lowered or "retry-after" in lowered:
                rate_limit[key] = value
        return {"quota": quota, "rate_limit": rate_limit}

    def _safe_payload_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        for key in (
            "page",
            "limit",
            "posted_at_gte",
            "posted_at_lte",
            "posted_at_max_age_days",
            "company_type",
            "is_closed",
            "remote",
            "blur_company_data",
            "include_total_results",
        ):
            if key in payload:
                summary[key] = payload[key]

        for key in (
            "job_country_code_or",
            "job_title_or",
            "job_title_not",
            "job_description_contains_or",
            "job_description_contains_not",
            "employment_statuses_or",
            "property_exists_and",
            "property_exists_or",
            "url_domain_or",
            "url_domain_not",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                summary[key] = {
                    "count": len(value),
                    "sample": [str(item) for item in value[:5]],
                }
        return summary

    def _safe_response_snippet(self, text: str, limit: int = 240) -> str:
        cleaned = " ".join((text or "").split())
        return cleaned[:limit]

    def _is_retryable_status(self, status_code: int) -> bool:
        return status_code in RETRYABLE_STATUS_CODES

    def _is_rate_limit(self, status_code: int, response_text: str) -> bool:
        if status_code == 429:
            return True
        text_lower = response_text.lower()
        return any(marker in text_lower for marker in [
            "rate limit", "quota exceeded", "credit", "too many requests",
        ])

    def _is_invalid_key(self, status_code: int) -> bool:
        return status_code in (401, 403)

    def _is_billing_required(self, status_code: int, response_text: str) -> bool:
        if status_code == 402:
            return True
        text_lower = response_text.lower()
        return any(marker in text_lower for marker in [
            "payment required",
            "billing",
            "subscription expired",
            "credits exhausted",
            "quota exhausted",
        ])

    async def health_check(self) -> Dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured", "provider": "theirstack"}
        posted_at_gte = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        payload = {
            "posted_at_gte": posted_at_gte,
            "job_country_code_or": ["IN"],
            "company_type": "direct_employer",
            "is_closed": False,
            "property_exists_and": ["final_url"],
            "employment_statuses_or": ["full_time"],
            "limit": 1,
            "page": 0,
            "job_title_or": ["software engineer"],
        }
        try:
            result = await self.search_jobs(payload, use_cache=False)
            return {
                "status": "healthy",
                "provider": "theirstack",
                "key_slots_configured": len(self._slots),
                "selected_key_slot": result.selected_key_slot,
                "sample_count": result.fetched_count,
                "billing_required": result.billing_required,
                "provider_blocked": result.provider_blocked,
            }
        except Exception as exc:
            return {"status": "unhealthy", "provider": "theirstack", "error": str(exc)[:512]}

    async def search_jobs(
        self,
        payload: Dict[str, Any],
        use_cache: bool = True,
    ) -> ClientSearchResult:
        if not self.configured:
            return ClientSearchResult(
                success=False,
                error="No TheirStack API keys configured",
            )
        if "posted_at_max_age_days" not in payload and "posted_at_gte" not in payload:
            return ClientSearchResult(
                success=False,
                error="TheirStack search requires posted_at_gte or posted_at_max_age_days",
            )

        if use_cache:
            cached = await self.cache.get(payload)
            if cached:
                return ClientSearchResult(
                    data=cached,
                    cache_hit=True,
                    success=True,
                    fetched_count=len(self._extract_job_list(cached)),
                )

        url = f"{self.base_url}/v1/jobs/search"
        result = ClientSearchResult()
        slot = get_next_valid_slot(self._slots)

        while slot is not None:
            result.attempted_key_slots.append(slot.slot_name)
            attempt_result = await self._try_single_slot(url, payload, slot)

            if attempt_result.success:
                result.data = attempt_result.data
                result.selected_key_slot = slot.slot_name
                result.provider_status_code = attempt_result.status_code
                result.fetched_count = attempt_result.fetched_count
                result.cache_hit = attempt_result.cache_hit
                result.success = True

                if use_cache and attempt_result.data:
                    await self.cache.set(payload, attempt_result.data)
                break

            if attempt_result.billing_required:
                result.billing_required = True
                result.provider_blocked = True
                result.selected_key_slot = slot.slot_name
                result.provider_status_code = attempt_result.status_code
                result.error = attempt_result.error or "TheirStack billing required"
                logger.warning(
                    "TheirStack provider blocked by billing status slot=%s status=%s",
                    slot.slot_name,
                    attempt_result.status_code,
                )
                break

            if attempt_result.is_rate_limited:
                result.rate_limited_slots.append(slot.slot_name)
                logger.info(
                    "TheirStack key slot %s rate limited, rotating",
                    slot.slot_name,
                )

            if attempt_result.is_invalid_key:
                result.invalid_slots.append(slot.slot_name)
                slot.valid = False
                logger.info(
                    "TheirStack key slot %s invalid (401/403), marking invalid",
                    slot.slot_name,
                )

            slot = get_next_valid_slot(self._slots, after_slot=slot.slot_name)

        if not result.success:
            if result.provider_blocked:
                result.error = (
                    f"TheirStack provider blocked by billing. "
                    f"attempted={result.attempted_key_slots}, "
                    f"selected={result.selected_key_slot}, "
                    f"status_code={result.provider_status_code}"
                )
            else:
                result.error = (
                    f"TheirStack: no key succeeded. "
                    f"attempted={result.attempted_key_slots}, "
                    f"rate_limited={result.rate_limited_slots}, "
                    f"invalid={result.invalid_slots}"
                )

        return result

    async def _try_single_slot(
        self,
        url: str,
        payload: Dict[str, Any],
        slot: KeySlot,
    ) -> ClientAuditRecord:
        """Try a single key slot with retries for transient errors."""
        audit = ClientAuditRecord(key_slot=slot.slot_name)
        last_exc: Optional[Exception] = None

        logger.info(
            "TheirStack request slot=%s payload=%s",
            slot.slot_name,
            self._safe_payload_summary(payload),
        )

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
        ) as http_client:
            for attempt in range(self.max_retries):
                try:
                    response = await http_client.post(
                        url,
                        headers=self._headers_for_key(slot.key),
                        json=payload,
                    )
                    monitor = self._monitor_headers(response.headers)
                    audit.status_code = response.status_code

                    if response.status_code == 429:
                        audit.is_rate_limited = True
                        retry_after = response.headers.get("Retry-After")
                        delay = (
                            float(retry_after)
                            if retry_after
                            else min(self.backoff_base ** attempt, 30.0)
                        )
                        await asyncio.sleep(delay)
                        continue

                    if response.status_code in (401, 403):
                        audit.is_invalid_key = True
                        audit.error = f"HTTP {response.status_code}"
                        return audit

                    if self._is_billing_required(response.status_code, response.text):
                        audit.billing_required = True
                        audit.provider_blocked = True
                        body_snippet = self._safe_response_snippet(response.text)
                        audit.error = (
                            f"HTTP {response.status_code} Payment Required"
                            + (f": {body_snippet}" if body_snippet else "")
                        )
                        return audit

                    if self._is_retryable_status(response.status_code):
                        await asyncio.sleep(min(self.backoff_base ** attempt, 30.0))
                        continue

                    if response.status_code >= 400:
                        body_snippet = self._safe_response_snippet(response.text)
                        audit.error = f"HTTP {response.status_code}: {body_snippet}"
                        return audit

                    try:
                        data = response.json()
                    except ValueError:
                        audit.error = "Invalid JSON response"
                        return audit
                    if isinstance(data, dict):
                        data.setdefault("quota", monitor["quota"])
                        data.setdefault("rate_limit", monitor["rate_limit"])
                    audit.data = data if isinstance(data, dict) else {"data": data, **monitor}
                    audit.fetched_count = len(self._extract_job_list(audit.data))
                    audit.success = True
                    logger.info(
                        "TheirStack response slot=%s status=%s fetched=%s total_results=%s",
                        slot.slot_name,
                        response.status_code,
                        audit.fetched_count,
                        audit.data.get("metadata", {}).get("total_results") if isinstance(audit.data, dict) else None,
                    )
                    return audit

                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_exc = exc
                    logger.warning(
                        "TheirStack transient transport error slot=%s attempt=%s error=%s",
                        slot.slot_name,
                        attempt + 1,
                        str(exc)[:200],
                    )
                    await asyncio.sleep(min(self.backoff_base ** attempt, 30.0))

        audit.error = str(last_exc)[:256] if last_exc else "unknown"
        return audit

    def _extract_job_list(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        for key in ("data", "jobs", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []
