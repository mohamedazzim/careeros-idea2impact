"""Resume-driven TheirStack job synchronization with audit logging."""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.repositories.domain_repositories import JobRepository
from src.models.jobs import Job
from src.services.job_location_filter import classify_job_location

from .client import TheirStackClient, ClientSearchResult
from .normalizer import normalize_job
from .schemas import NormalizedTheirStackJob

logger = logging.getLogger(__name__)

_BILLING_BLOCKED_UNTIL: datetime | None = None
_BILLING_BLOCKED_SLOT_COUNT = 0


def _effective_theirstack_page_limit() -> int:
    requested_limit = max(
        int(settings.THEIRSTACK_JOB_FETCH_LIMIT),
        int(settings.THEIRSTACK_RESULTS_PER_QUERY),
    )
    configured_cap = int(getattr(settings, "THEIRSTACK_MAX_RESULTS_PER_REQUEST", 5) or 5)
    return max(1, min(requested_limit, configured_cap, 5))

INDIA_KEYWORDS = [
    "india", "bengaluru", "bangalore", "hyderabad", "chennai", "pune",
    "mumbai", "delhi", "gurugram", "gurgaon", "noida", "kolkata",
    "coimbatore", "kochi", "ahmedabad", "jaipur", "indore",
    "trivandrum", "thiruvananthapuram",
]

ROLE_HINTS_BY_SKILL = {
    "python": ["Python Developer", "Data Scientist", "Backend Engineer"],
    "sql": ["Data Analyst", "Analytics Engineer", "Business Intelligence Analyst"],
    "power bi": ["Power BI Analyst", "Business Intelligence Developer"],
    "machine learning": ["Machine Learning Engineer", "Data Scientist", "AI Engineer"],
    "ai": ["AI Engineer", "Applied AI Engineer"],
    "generative ai": ["Generative AI Engineer", "LLM Engineer"],
    "tensorflow": ["Machine Learning Engineer", "Deep Learning Engineer"],
    "pytorch": ["Machine Learning Engineer", "AI Research Engineer"],
    "react": ["Frontend Engineer", "React Developer"],
    "typescript": ["Frontend Engineer", "Full Stack Engineer"],
    "docker": ["DevOps Engineer", "Platform Engineer"],
    "fastapi": ["Python Backend Engineer", "API Engineer"],
}

DEFAULT_TECH_TITLE_HINTS = [
    "Software Engineer",
    "Backend Engineer",
    "Data Engineer",
    "Data Scientist",
    "Machine Learning Engineer",
    "Full Stack Engineer",
    "Frontend Engineer",
    "Platform Engineer",
    "DevOps Engineer",
    "MLOps Engineer",
    "Cloud Engineer",
    "Site Reliability Engineer",
    "Scrum Master",
    "Technical Program Manager",
    "System Support Engineer",
    "IT Support Engineer",
    "Production Support Engineer",
    "QA Engineer",
    "Automation Engineer",
]

NON_TECH_TITLE_EXCLUDES = [
    "intern",
    "internship",
    "trainee",
    "sales",
    "marketing",
    "business development",
    "human resources",
    "recruiter",
    "account manager",
    "customer success",
    "support",
    "operations",
    "finance",
    "legal",
    "assistant",
]


def build_theirstack_indian_tech_jobs_payload(
    limit: int,
    page: int,
    since_days: int = 7,
    preview: bool = False,
    discovered_at_gte: Optional[datetime] = None,
    exclude_job_ids: Optional[List[str]] = None,
    country_codes: Optional[List[str]] = None,
    company_type: Optional[str] = None,
    employment_statuses: Optional[List[str]] = None,
    title_terms: Optional[List[str]] = None,
    negative_title_terms: Optional[List[str]] = None,
    skill_terms: Optional[List[str]] = None,
    remote: Optional[bool] = None,
) -> Dict[str, Any]:
    posted_at_gte = (datetime.now(timezone.utc) - timedelta(days=since_days)).date().isoformat()
    effective_limit = max(1, min(int(limit or 5), int(getattr(settings, "THEIRSTACK_MAX_RESULTS_PER_REQUEST", 5) or 5), 5))
    payload: Dict[str, Any] = {
        "page": page,
        "limit": 1 if preview else effective_limit,
        "posted_at_gte": posted_at_gte,
        "job_country_code_or": country_codes or ["IN"],
        "company_type": company_type or "direct_employer",
        "is_closed": False,
        "employment_statuses_or": employment_statuses or ["full_time"],
        "property_exists_and": ["final_url"],
        "job_title_or": title_terms or DEFAULT_TECH_TITLE_HINTS,
        "job_title_not": negative_title_terms or NON_TECH_TITLE_EXCLUDES,
    }
    if skill_terms:
        payload["job_description_contains_or"] = skill_terms
    if remote is not None:
        payload["remote"] = remote
    if preview:
        payload["blur_company_data"] = True
        payload["include_total_results"] = True

    # TheirStack incremental exclusion support is not relied on by default.
    # If the caller explicitly provides known-safe provider filters, include them.
    if discovered_at_gte is not None:
        payload["discovered_at_gte"] = discovered_at_gte.date().isoformat()
    if exclude_job_ids:
        payload["job_id_not"] = exclude_job_ids
    return payload


class TheirStackSyncService:
    def __init__(self, client: TheirStackClient | None = None):
        self.client = client or TheirStackClient()
        self.last_query_context: Dict[str, Any] = {}
        self.last_updated_jobs: List[Dict[str, Any]] = []

    def _dedupe_terms(self, values: Iterable[Any], limit: int | None = None) -> List[str]:
        terms: List[str] = []
        seen: set[str] = set()
        for raw in values:
            term = " ".join(str(raw).split()).strip()
            if not term:
                continue
            lowered = term.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            terms.append(term)
            if limit is not None and len(terms) >= limit:
                break
        return terms

    def _build_title_terms(
        self,
        resume_profile: Dict[str, Any],
        preferences: Dict[str, Any] | None = None,
    ) -> List[str]:
        preferences = preferences or {}
        roles: List[str] = []
        for role in (
            preferences.get("target_role"),
            resume_profile.get("target_role"),
            resume_profile.get("role"),
        ):
            if role:
                roles.append(str(role))

        skills = [str(s).strip() for s in resume_profile.get("skills", []) if str(s).strip()]
        skill_terms = [skill.lower() for skill in skills]
        for skill in skill_terms:
            roles.extend(ROLE_HINTS_BY_SKILL.get(skill, []))

        education_text = " ".join(
            str(item).strip() for item in (resume_profile.get("education") or []) if str(item).strip()
        ).lower()
        if "mca" in education_text:
            roles.extend(["Software Engineer", "Backend Engineer", "Data Engineer"])
        if "bca" in education_text:
            roles.extend(["Software Engineer", "Data Analyst", "Support Engineer"])

        roles.extend(DEFAULT_TECH_TITLE_HINTS)

        return self._dedupe_terms(roles, limit=20)

    def _build_skill_terms(
        self,
        resume_profile: Dict[str, Any],
        preferences: Dict[str, Any] | None = None,
    ) -> List[str]:
        preferences = preferences or {}
        skills: List[str] = []
        for value in resume_profile.get("skills", []) or []:
            if value:
                skills.append(str(value))
        for value in preferences.get("skills", []) or []:
            if value:
                skills.append(str(value))
        skills.extend([
            "python", "sql", "power bi", "machine learning", "ai", "gen ai", "generative ai",
            "tensorflow", "pytorch", "fastapi", "django", "docker", "kubernetes", "aws",
            "azure", "gcp", "devops", "mlops", "ci/cd", "react", "typescript", "node",
            "linux", "support", "scrum", "jira", "agile",
        ])
        return self._dedupe_terms(skills, limit=20)

    def build_search_payload(
        self,
        resume_profile: Dict[str, Any],
        preferences: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        preferences = preferences or {}
        country_codes = self._dedupe_terms(settings.THEIRSTACK_COUNTRY_CODES, limit=5) or ["IN"]
        employment_statuses = self._dedupe_terms(settings.THEIRSTACK_EMPLOYMENT_STATUSES, limit=5) or ["full_time"]

        title_terms = self._build_title_terms(resume_profile, preferences)
        skill_terms = self._build_skill_terms(resume_profile, preferences)

        target_location = str(preferences.get("target_location") or resume_profile.get("location") or "").strip()
        remote_flag: Optional[bool] = None
        if target_location:
            lowered_location = target_location.lower()
            if "remote" in lowered_location:
                remote_flag = True

        if preferences.get("remote") is not None:
            remote_flag = bool(preferences["remote"])

        return build_theirstack_indian_tech_jobs_payload(
            limit=_effective_theirstack_page_limit(),
            page=0,
            since_days=int(settings.THEIRSTACK_JOB_FETCH_DAYS),
            preview=False,
            discovered_at_gte=preferences.get("discovered_at_gte"),
            exclude_job_ids=preferences.get("exclude_job_ids"),
            country_codes=country_codes,
            company_type=settings.THEIRSTACK_COMPANY_TYPE,
            employment_statuses=employment_statuses,
            title_terms=title_terms,
            negative_title_terms=self._dedupe_terms(NON_TECH_TITLE_EXCLUDES, limit=12),
            skill_terms=skill_terms,
            remote=remote_flag,
        )

    def build_broad_search_payload(
        self,
        resume_profile: Dict[str, Any],
        preferences: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Fallback payload that keeps India/tech constraints but removes tight skill/title gating.

        The primary resume-driven query can be too restrictive for sparse provider coverage or
        incomplete resume skill extraction. This broader query keeps the feed useful without
        leaving the India technical surface area.
        """
        preferences = preferences or {}
        country_codes = self._dedupe_terms(settings.THEIRSTACK_COUNTRY_CODES, limit=5) or ["IN"]
        employment_statuses = self._dedupe_terms(settings.THEIRSTACK_EMPLOYMENT_STATUSES, limit=5) or ["full_time"]

        target_location = str(preferences.get("target_location") or resume_profile.get("location") or "").strip()
        remote_flag: Optional[bool] = None
        if target_location:
            lowered_location = target_location.lower()
            if "remote" in lowered_location:
                remote_flag = True

        if preferences.get("remote") is not None:
            remote_flag = bool(preferences["remote"])

        return build_theirstack_indian_tech_jobs_payload(
            limit=_effective_theirstack_page_limit(),
            page=0,
            since_days=max(int(settings.THEIRSTACK_JOB_FETCH_DAYS), 30),
            preview=False,
            discovered_at_gte=preferences.get("discovered_at_gte"),
            exclude_job_ids=preferences.get("exclude_job_ids"),
            country_codes=country_codes,
            company_type=settings.THEIRSTACK_COMPANY_TYPE,
            employment_statuses=employment_statuses,
            title_terms=[
                "Software Engineer",
                "Backend Engineer",
                "Full Stack Engineer",
                "Frontend Engineer",
                "Data Engineer",
                "Data Scientist",
                "Machine Learning Engineer",
                "DevOps Engineer",
                "Platform Engineer",
                "Support Engineer",
                "Scrum Master",
                "Technical Program Manager",
            ],
            negative_title_terms=self._dedupe_terms(NON_TECH_TITLE_EXCLUDES, limit=12),
            remote=remote_flag,
        )

    def build_preview_payload(
        self,
        resume_profile: Dict[str, Any],
        preferences: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        preferences = preferences or {}
        payload = self.build_search_payload(resume_profile, preferences)
        return build_theirstack_indian_tech_jobs_payload(
            limit=_effective_theirstack_page_limit(),
            page=int(payload.get("page", 0)),
            since_days=int(settings.THEIRSTACK_JOB_FETCH_DAYS),
            preview=True,
            discovered_at_gte=preferences.get("discovered_at_gte"),
            exclude_job_ids=preferences.get("exclude_job_ids"),
            country_codes=payload.get("job_country_code_or"),
            company_type=payload.get("company_type"),
            employment_statuses=payload.get("employment_statuses_or"),
            title_terms=payload.get("job_title_or"),
            negative_title_terms=payload.get("job_title_not"),
            skill_terms=payload.get("job_description_contains_or"),
            remote=payload.get("remote"),
        )

    def build_search_queries(
        self,
        resume_profile: Dict[str, Any],
        preferences: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        preferences = preferences or {}
        search_mode = str(preferences.get("search_mode") or "resume").strip().lower()
        if search_mode == "broad":
            base_payload = self.build_broad_search_payload(resume_profile, preferences)
        else:
            search_mode = "resume"
            base_payload = self.build_search_payload(resume_profile, preferences)
        return [{**base_payload, "page": 0, "include_total_results": False, "_search_mode": search_mode}]

    async def health_check(self) -> Dict[str, Any]:
        return await self.client.health_check()

    async def search_from_resume(
        self,
        resume_profile: Dict[str, Any],
        preferences: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        global _BILLING_BLOCKED_UNTIL, _BILLING_BLOCKED_SLOT_COUNT

        key_slots_configured = len(getattr(self.client, "_slots", []) or [])
        provider_blocked = False
        billing_required = False
        provider_status_code = 0
        selected_key_slot = ""
        attempted_key_slots: List[str] = []
        rate_limited_slots: List[str] = []
        invalid_slots: List[str] = []

        if not self.client.configured:
            return {
                "provider": "theirstack",
                "configured": False,
                "found": 0,
                "normalized": 0,
                "jobs": [],
                "preview": None,
                "queries": self.build_search_queries(resume_profile, preferences),
                "errors": ["No TheirStack API keys configured"],
                "audit": {
                    "selected_key_slot": "",
                    "attempted_key_slots": [],
                    "rate_limited_slots": [],
                    "invalid_slots": [],
                    "provider_status_code": 0,
                    "billing_required": False,
                    "provider_blocked": False,
                },
                "provider_health": {
                    "provider": "theirstack",
                    "status": "not_configured",
                    "configured": False,
                    "billing_required": False,
                    "provider_blocked": False,
                    "key_slots_configured": 0,
                },
            }

        now = datetime.now(timezone.utc)
        cooldown_seconds = int(getattr(settings, "THEIRSTACK_BILLING_COOLDOWN_SECONDS", 1800) or 0)
        if (
            cooldown_seconds > 0
            and _BILLING_BLOCKED_UNTIL is not None
            and _BILLING_BLOCKED_UNTIL > now
            and _BILLING_BLOCKED_SLOT_COUNT == key_slots_configured
        ):
            self.last_query_context = {
                "provider": "theirstack",
                "display_name": "TheirStack",
                "query": "resume-driven technical feed",
                "location": "India/Remote filters",
                "limit": _effective_theirstack_page_limit(),
                "since": f"{int(settings.THEIRSTACK_JOB_FETCH_DAYS)} days",
                "configured": True,
                "query_count": 1,
                "search_mode": str((preferences or {}).get("search_mode") or "resume").strip().lower(),
            }
            retry_at = _BILLING_BLOCKED_UNTIL.isoformat().replace("+00:00", "Z")
            return {
                "provider": "theirstack",
                "configured": True,
                "provider_blocked": True,
                "billing_required": True,
                "provider_status_code": 402,
                "found": 0,
                "normalized": 0,
                "india_likely": 0,
                "non_india_rejected": 0,
                "skipped_missing_apply": 0,
                "skipped_duplicates": 0,
                "skipped_invalid_jobs": 0,
                "provider_http_call_count": 0,
                "credit_upper_bound": 0,
                "jobs": [],
                "preview": None,
                "queries": [],
                "errors": [f"TheirStack billing cooldown is active until {retry_at}."],
                "audit": {
                    "selected_key_slot": "",
                    "attempted_key_slots": [],
                    "rate_limited_slots": [],
                    "invalid_slots": [],
                    "provider_status_code": 402,
                    "billing_required": True,
                    "provider_blocked": True,
                    "provider_http_call_count": 0,
                    "billing_cooldown_until": retry_at,
                },
                "provider_health": {
                    "provider": "theirstack",
                    "status": "blocked",
                    "configured": True,
                    "billing_required": True,
                    "provider_blocked": True,
                    "key_slots_configured": key_slots_configured,
                    "selected_key_slot": "",
                    "attempted_key_slots": [],
                    "rate_limited_slots": [],
                    "invalid_slots": [],
                    "provider_status_code": 402,
                    "provider_http_call_count": 0,
                    "billing_cooldown_until": retry_at,
                },
            }

        jobs: List[NormalizedTheirStackJob] = []
        request_evidence = []
        errors: List[str] = []
        seen_ids: set[str] = set()
        total_fetched = 0
        last_search_result: ClientSearchResult | None = None
        skipped_missing_apply = 0
        skipped_duplicates = 0
        skipped_invalid_jobs = 0
        provider_http_call_count = 0
        search_mode = str((preferences or {}).get("search_mode") or "resume").strip().lower()
        if search_mode not in {"resume", "broad"}:
            search_mode = "resume"

        payload = self.build_search_payload(resume_profile, preferences)
        query_payloads = self.build_search_queries(resume_profile, preferences)
        title_terms = [str(term) for term in payload.get("job_title_or", []) if str(term).strip()]
        skill_terms = [str(term) for term in payload.get("job_description_contains_or", []) if str(term).strip()]
        target_location = str((preferences or {}).get("target_location") or resume_profile.get("location") or "").strip()
        self.last_query_context = {
            "provider": "theirstack",
            "display_name": "TheirStack",
            "query": " OR ".join(title_terms[:5]) if title_terms else "resume-driven technical feed",
            "location": target_location or "India/Remote filters",
            "limit": int(payload.get("limit") or _effective_theirstack_page_limit()),
            "since": f"{int(settings.THEIRSTACK_JOB_FETCH_DAYS)} days",
            "configured": True,
            "query_count": len(query_payloads),
            "skill_terms": skill_terms[:5],
            "search_mode": search_mode,
        }
        self.last_updated_jobs = []
        preview_result: Dict[str, Any] | None = None
        logger.info(
            "TheirStack search configuration preview_enabled=%s limit=%s pages=%s posted_at_gte=%s countries=%s",
            settings.THEIRSTACK_ENABLE_FREE_COUNT_PREVIEW,
            payload.get("limit"),
            len(query_payloads),
            payload.get("posted_at_gte"),
            payload.get("job_country_code_or"),
        )
        # User-triggered refreshes are quota-bounded to a single paid provider
        # request. Preview/count probes are intentionally not dispatched here.

        for idx, query_payload in enumerate(query_payloads):
            try:
                paid_query_payload = {k: v for k, v in query_payload.items() if not k.startswith("_")}
                result = await self.client.search_jobs(paid_query_payload, use_cache=(idx == 0))
                last_search_result = result
                provider_http_call_count += int(result.provider_http_call_count or 0)
                attempted_key_slots = list(result.attempted_key_slots)
                rate_limited_slots = list(result.rate_limited_slots)
                invalid_slots = list(result.invalid_slots)

                if result.success:
                    raw_jobs = self._extract_jobs(result.data)
                    total_fetched += len(raw_jobs)
                    max_accept_count = min(int(paid_query_payload.get("limit") or 5), 5)
                    request_evidence.append({
                        "type": "search",
                        "query": paid_query_payload,
                        "fetched": len(raw_jobs),
                        "key_slot": result.selected_key_slot,
                        "cache_hit": result.cache_hit,
                        "provider_http_call_count": result.provider_http_call_count,
                        "credit_upper_bound": min(len(raw_jobs), int(paid_query_payload.get("limit") or 5), 5),
                        "search_mode": query_payload.get("_search_mode", search_mode),
                        "total_results": result.data.get("metadata", {}).get("total_results") if isinstance(result.data, dict) else None,
                        "total_companies": result.data.get("metadata", {}).get("total_companies") if isinstance(result.data, dict) else None,
                    })

                    for raw in raw_jobs[:max_accept_count]:
                        if not raw.get("final_url") and not raw.get("apply_url") and not raw.get("url") and not raw.get("source_url"):
                            skipped_missing_apply += 1
                            continue
                        normalized = normalize_job(raw)
                        if not normalized:
                            skipped_invalid_jobs += 1
                            continue
                        if normalized.source_job_id in seen_ids:
                            skipped_duplicates += 1
                            continue
                        seen_ids.add(normalized.source_job_id)
                        jobs.append(normalized)

                        if len(raw_jobs) < int(query_payload.get("limit", 0) or 0):
                            break
                elif result.billing_required:
                    provider_blocked = True
                    billing_required = True
                    provider_status_code = result.provider_status_code or 402
                    selected_key_slot = result.selected_key_slot
                    errors.append(result.error or "TheirStack billing required")
                    break
                elif result.error:
                    errors.append(result.error)
                    break
            except Exception as exc:
                logger.warning("TheirStack query failed: %s", exc)
                errors.append(str(exc)[:256])
                break

        india_count = sum(1 for j in jobs if self._is_likely_india(j))
        non_india_count = len(jobs) - india_count

        audit = {}
        if last_search_result:
            selected_key_slot = selected_key_slot or last_search_result.selected_key_slot
            provider_status_code = provider_status_code or last_search_result.provider_status_code
            audit = {
                "selected_key_slot": selected_key_slot or last_search_result.selected_key_slot,
                "attempted_key_slots": attempted_key_slots or last_search_result.attempted_key_slots,
                "rate_limited_slots": rate_limited_slots or last_search_result.rate_limited_slots,
                "invalid_slots": invalid_slots or last_search_result.invalid_slots,
                "provider_status_code": provider_status_code or last_search_result.provider_status_code,
                "billing_required": billing_required or last_search_result.billing_required,
                "provider_blocked": provider_blocked or last_search_result.provider_blocked,
                "provider_http_call_count": provider_http_call_count,
                "requested_limit": int(payload.get("limit") or _effective_theirstack_page_limit()),
                "returned_count": total_fetched,
                "accepted_count": len(jobs),
                "rejected_count": skipped_missing_apply + skipped_duplicates + skipped_invalid_jobs,
                "duplicate_count": skipped_duplicates,
                "cache_hit": bool(last_search_result.cache_hit),
                "search_mode": search_mode,
                "credit_upper_bound": min(total_fetched, int(payload.get("limit") or 5), 5),
            }
        provider_health = {
            "provider": "theirstack",
            "status": "blocked" if provider_blocked else ("degraded" if errors else "healthy"),
            "configured": True,
            "billing_required": billing_required,
            "provider_blocked": provider_blocked,
            "key_slots_configured": key_slots_configured,
            "selected_key_slot": selected_key_slot,
            "attempted_key_slots": attempted_key_slots,
            "rate_limited_slots": rate_limited_slots,
            "invalid_slots": invalid_slots,
            "provider_status_code": provider_status_code,
            "provider_http_call_count": provider_http_call_count,
            "credit_upper_bound": min(total_fetched, int(payload.get("limit") or 5), 5),
        }
        if (
            cooldown_seconds > 0
            and provider_blocked
            and billing_required
            and key_slots_configured > 0
            and len(set(rate_limited_slots)) >= key_slots_configured
        ):
            _BILLING_BLOCKED_UNTIL = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
            _BILLING_BLOCKED_SLOT_COUNT = key_slots_configured
            retry_at = _BILLING_BLOCKED_UNTIL.isoformat().replace("+00:00", "Z")
            audit["billing_cooldown_until"] = retry_at
            provider_health["billing_cooldown_until"] = retry_at
            logger.warning(
                "TheirStack billing/quota cooldown activated for %s seconds after all configured key slots were blocked",
                cooldown_seconds,
            )

        log_msg = (
            "TheirStack sync: fetched=%d, normalized=%d, india_likely=%d, "
            "non_india=%d, errors=%d, slot=%s, rate_limited=%s, billing_required=%s"
        )
        logger.info(
            log_msg,
            total_fetched,
            len(jobs),
            india_count,
            non_india_count,
            len(errors),
            audit.get("selected_key_slot", ""),
            audit.get("rate_limited_slots", []),
            billing_required,
        )

        return {
            "provider": "theirstack",
            "configured": True,
            "provider_blocked": provider_blocked,
            "billing_required": billing_required,
            "provider_status_code": provider_status_code,
            "found": total_fetched,
            "normalized": len(jobs),
            "india_likely": india_count,
            "non_india_rejected": non_india_count,
            "skipped_missing_apply": skipped_missing_apply,
            "skipped_duplicates": skipped_duplicates,
            "skipped_invalid_jobs": skipped_invalid_jobs,
            "provider_http_call_count": provider_http_call_count,
            "credit_upper_bound": min(total_fetched, int(payload.get("limit") or 5), 5),
            "jobs": jobs,
            "preview": preview_result,
            "queries": request_evidence or query_payloads,
            "errors": errors,
            "audit": audit,
            "provider_health": provider_health,
        }

    def _is_likely_india(self, job: NormalizedTheirStackJob) -> bool:
        loc = (job.location or "").lower()
        for kw in INDIA_KEYWORDS:
            if kw in loc:
                return True
        return False

    def _extract_jobs(self, response: Any) -> List[Dict[str, Any]]:
        if isinstance(response, dict):
            for key in ("data", "jobs", "results"):
                value = response.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        if isinstance(response, list):
            return [item for item in response if isinstance(item, dict)]
        return []

    async def upsert_jobs(
        self,
        db: AsyncSession,
        normalized_jobs: Iterable[NormalizedTheirStackJob],
    ) -> Tuple[int, int, int]:
        repo = JobRepository(db)
        added = updated = expired = 0
        fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
        seen_source_ids: set[str] = set()
        updated_samples: List[Dict[str, Any]] = []

        for job_data in normalized_jobs:
            seen_source_ids.add(job_data.source_job_id)
            job_uid = hashlib.sha256(
                f"theirstack|{job_data.apply_url}|{job_data.title.lower().strip()}".encode("utf-8")
            ).hexdigest()[:64]

            existing_result = await db.execute(select(Job).where(
                Job.source == "theirstack",
                or_(
                    Job.source_job_id == job_data.source_job_id,
                    Job.job_uid == job_uid,
                ),
            ).limit(1))
            existing = existing_result.scalar_one_or_none()
            is_stale = job_data.freshness_bucket == "stale"

            loc_decision = classify_job_location(
                location_raw=job_data.location,
                title=job_data.title,
                description=job_data.full_description,
            )

            from src.services.job_role_filter import classify_tech_role, extract_job_experience_requirement
            tech_decision = classify_tech_role(
                title=job_data.title,
                description=job_data.full_description,
                skills=job_data.extracted_skills,
            )
            exp_decision = extract_job_experience_requirement(
                title=job_data.title,
                description=job_data.full_description,
            )
            is_non_tech = not tech_decision["is_tech_role"] and tech_decision["confidence"] >= 0.7

            values = {
                "job_uid": job_uid,
                "title": job_data.title,
                "company": job_data.company,
                "location": job_data.location,
                "description": job_data.full_description,
                "source": "theirstack",
                "source_provider": "theirstack",
                "source_job_id": job_data.source_job_id,
                "source_url": job_data.apply_url,
                "apply_url": job_data.apply_url,
                "posted_date": job_data.posted_at,
                "fetched_at": fetched_at,
                "salary_range": job_data.salary or "",
                "skills_required": job_data.extracted_skills,
                "original_provider_metadata": job_data.original_provider_metadata,
                "freshness_score": job_data.freshness_score,
                "freshness_bucket": job_data.freshness_bucket,
                "provider_quality_score": job_data.provider_quality_score,
                "salary_quality_score": job_data.salary_quality_score,
                "apply_url_valid": job_data.apply_url_valid,
                "status": "expired" if is_stale else "active",
                "lifecycle_state": "EXPIRED" if is_stale else "NEW",
                "deleted_at": fetched_at if is_stale else None,
                "updated_at": fetched_at,
                "location_country": loc_decision.location_country,
                "location_region": loc_decision.location_region,
                "location_city": loc_decision.location_city,
                "is_remote": loc_decision.is_remote,
                "remote_region": loc_decision.remote_region,
                "is_india_eligible": loc_decision.is_india_eligible and not is_stale,
                "exclusion_reason": loc_decision.exclusion_reason,
                "eligibility_checked_at": fetched_at,
                "is_tech_role": tech_decision["is_tech_role"],
                "tech_role_category": tech_decision["tech_role_category"],
                "tech_role_confidence": tech_decision["confidence"],
                "role_classification_reason": tech_decision["reason"],
                "experience_min_years": exp_decision["min_years"],
                "experience_max_years": exp_decision["max_years"],
                "seniority_level": exp_decision["seniority_level"],
                "experience_filter_status": "active",
            }

            if is_non_tech:
                values["status"] = "excluded"
                values["lifecycle_state"] = "EXCLUDED"
                values["exclusion_reason"] = f"non_tech_role: {tech_decision['reason']}"
            elif not loc_decision.is_india_eligible:
                values["status"] = "excluded"
                values["lifecycle_state"] = "EXCLUDED"
            elif is_stale:
                values["status"] = "expired"
                values["lifecycle_state"] = "EXPIRED"

            create_values = dict(values)
            update_values = {k: v for k, v in values.items() if k != "job_uid"}
            if existing:
                changed_fields = [
                    key for key, new_value in update_values.items()
                    if getattr(existing, key, None) != new_value
                ]
                await repo.update(existing.id, **update_values, updated_by="theirstack_sync")
                updated += 1
                if len(updated_samples) < 3:
                    updated_samples.append({
                        "title": str(job_data.title or "")[:160],
                        "company": str(job_data.company or "")[:160],
                        "provider": "theirstack",
                        "external_job_id": job_data.source_job_id,
                        "last_seen_at": fetched_at.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
                        "updated_fields": (changed_fields or ["last_seen_at"])[:8],
                    })
            else:
                await repo.create(**create_values, ingested_at=fetched_at, created_by="theirstack_sync")
                added += 1

        if seen_source_ids:
            current = await db.execute(select(Job).where(
                Job.source == "theirstack",
                Job.status == "active",
                Job.deleted_at.is_(None),
            ))
            for job in current.scalars().all():
                if job.source_job_id not in seen_source_ids:
                    job.status = "expired"
                    job.lifecycle_state = "EXPIRED"
                    job.deleted_at = fetched_at
                    job.updated_at = fetched_at
                    expired += 1
            await db.commit()

        self.last_updated_jobs = updated_samples

        logger.info(
            "TheirStack upsert: added=%d, updated=%d, expired=%d",
            added, updated, expired,
        )
        return added, updated, expired
