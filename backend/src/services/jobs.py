"""
Real job board ingestion engine.

Connectors for RemoteOK, Arbeitnow, Adzuna, USAJobs, Greenhouse, and Lever job boards.
Normalization, deduplication, enrichment, and storage via PostgreSQL.
No mock data, no stub implementations, no disabled features.
"""

import hashlib
import logging
import uuid
from datetime import datetime
from typing import Awaitable, Callable, Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from src.core.config import settings
from src.observability.tracing import trace_async
from src.services.job_refresh_diagnostics import (
    build_provider_query_context,
    provider_refresh_message,
    provider_result_payload,
    updated_fields,
    updated_job_sample,
)
from src.services.job_location_filter import classify_job_location
from src.db.repositories.domain_repositories import JobRepository

logger = logging.getLogger(__name__)

JOB_SYNC_LOCK_KEY = "jobs:provider_sync_lock"
JOB_SYNC_LOCK_TTL_SECONDS = 900
JOB_SYNC_WAIT_SECONDS = 90
JOB_SYNC_WAIT_INTERVAL_SECONDS = 2

GREENHOUSE_TARGET_COMPANIES = [
    "anthropic",
    "stripe",
    "cloudflare",
    "vercel",
    "datadog",
    "coinbase",
    "rubrik",
    "postman",
    "okta",
    "gitlab",
]

LEVER_TARGET_COMPANIES = [
    "mindtickle",
    "meesho",
    "zeta",
    "cred",
]


class JobIngestionEngine:
    """Multi-provider job board ingestion with normalization and deduplication."""

    def __init__(self):
        self._client_timeout = 15.0

    def _make_job_uid(self, source: str, source_job_id: str, source_url: str, title: str) -> str:
        key = str(source_job_id or "").strip()
        if not key:
            key = f"{source_url}|{title.lower().strip()}"
        raw = f"{source}|{key}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]

    def _source_job_id(self, source: str, job_data: Dict[str, Any]) -> str:
        board_slug = str(job_data.get("board_slug") or job_data.get("source_board") or "").strip()
        explicit = str(job_data.get("source_job_id") or "").strip()
        if source == "greenhouse" and board_slug and explicit:
            return f"{board_slug}:{explicit}"[:128]
        if explicit:
            return explicit[:128]
        if source == "greenhouse" and board_slug:
            raw = f"{source}|{board_slug}|{job_data.get('source_url', '')}|{job_data.get('title', '').lower().strip()}"
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]
        raw = f"{source}|{job_data.get('source_url', '')}|{job_data.get('title', '').lower().strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]

    def _is_direct_posting_url(self, url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        path = parsed.path.rstrip("/").lower()
        if parsed.netloc.lower().endswith("remoteok.com") and path == "/remote-jobs":
            return False
        lowered = url.lower()
        query = parsed.query.lower()
        search_markers = [
            "/jobs/search",
            "/search/",
            "/search?",
            "/srp/results",
            "keywords=",
            "/internships/keywords-",
            "-jobs-in-india",
        ]
        if any(marker in lowered for marker in search_markers):
            return False
        return "q=" not in query

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            try:
                return datetime.utcfromtimestamp(float(value))
            except (OverflowError, ValueError):
                return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

    def _freshness(self, posted_at: Optional[datetime]) -> tuple[float, str]:
        if not posted_at:
            return 50.0, "unknown"
        age_hours = max(0.0, (datetime.utcnow() - posted_at).total_seconds() / 3600)
        if age_hours <= 24:
            return 100.0, "fresh"
        if age_hours <= 72:
            return 85.0, "recent"
        if age_hours <= 24 * 7:
            return 70.0, "active"
        if age_hours <= 24 * 30:
            return 40.0, "aging"
        return 0.0, "stale"

    def _provider_quality(self, source: str) -> float:
        source = (source or "").lower()
        if source in {"theirstack", "greenhouse", "lever", "ashby"}:
            return 95.0
        if source == "remoteok":
            return 85.0
        if source == "arbeitnow":
            return 80.0
        return 50.0

    @staticmethod
    def _provider_display_name(source: str) -> str:
        mapping = {
            "theirstack": "TheirStack",
            "remoteok": "RemoteOK",
            "arbeitnow": "Arbeitnow",
            "adzuna": "Adzuna",
            "usajobs": "USAJobs",
            "greenhouse": "Greenhouse",
            "lever": "Lever",
        }
        normalized = (source or "").lower()
        return mapping.get(normalized, (source or "").title() or "Unknown")

    def _build_refresh_reason(
        self,
        *,
        resume_profile: Optional[Dict[str, Any]],
        provider_results: List[Dict[str, Any]],
        total_found: int,
        total_added: int,
        total_updated: int,
        total_duplicates: int,
        total_expired: int,
        errors: int,
    ) -> Dict[str, Any]:
        blocked_provider = next(
            (
                result
                for result in provider_results
                if result.get("provider_blocked") or result.get("status") == "blocked"
            ),
            None,
        )
        if blocked_provider:
            provider_name = blocked_provider.get("display_name") or blocked_provider.get("provider") or "a provider"
            if blocked_provider.get("billing_required"):
                return {
                    "code": "provider_billing_required",
                    "message": f"{provider_name} returned a billing-required response, so no new jobs could be fetched from that source.",
                }
            return {
                "code": "provider_blocked",
                "message": f"{provider_name} was blocked, so its jobs were not included in the refresh.",
            }

        if total_found <= 0:
            if errors > 0:
                return {
                    "code": "provider_error",
                    "message": "The providers returned no jobs and one or more provider errors were recorded.",
                }
            return {
                "code": "no_provider_results",
                "message": "The refresh ran successfully, but no direct provider jobs were returned.",
            }

        if total_added <= 0 and total_updated > 0:
            return {
                "code": "providers_returned_only_existing_jobs",
                "message": f"Providers returned {total_found} jobs, but all matched existing records, so no new job cards were added.",
            }

        if total_added <= 0 and total_updated <= 0:
            if total_duplicates > 0 and total_found > 0:
                return {
                    "code": "duplicate_only",
                    "message": "The refresh found jobs, but every visible result matched an existing record.",
                }
            if total_expired > 0:
                return {
                    "code": "all_results_expired",
                    "message": "The refresh found jobs, but they were already stale or expired.",
                }
            if errors > 0:
                return {
                    "code": "provider_error",
                    "message": "The refresh completed with provider errors and did not add visible jobs.",
                }
            return {
                "code": "no_new_jobs",
                "message": "The refresh completed, but no new or updated jobs were available for the feed.",
            }

        return {
            "code": "jobs_refreshed",
            "message": f"The refresh added {total_added} new job(s) and updated {total_updated} existing job(s).",
        }

    @trace_async("sync_jobs_from_sources")
    async def sync_jobs(
        self,
        admin_initiated: bool = False,
        resume_profile: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None,
        stage_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        from asyncio import sleep
        from src.db.redis import redis_client

        sources = ["remoteok", "arbeitnow", "adzuna", "usajobs", "greenhouse", "lever"]
        total_found = 0
        total_added = 0
        total_updated = 0
        total_duplicates = 0
        total_expired = 0
        errors = 0
        embed_result: Dict[str, int] = {"embedded": 0}
        provider_results: List[Dict[str, Any]] = []
        theirstack_result: Dict[str, Any] = {
            "configured": False, "found": 0, "added": 0, "updated": 0,
            "expired_removed": 0, "audit": {},
            "provider_health": {},
        }
        lease_id = str(uuid.uuid4())
        waited_seconds = 0

        while True:
            acquired = bool(await redis_client.set(
                JOB_SYNC_LOCK_KEY,
                lease_id,
                nx=True,
                ex=JOB_SYNC_LOCK_TTL_SECONDS,
            ))
            if acquired:
                break
            if not admin_initiated or waited_seconds >= JOB_SYNC_WAIT_SECONDS:
                logger.info(
                    "Skipping overlapping provider sync",
                    extra={
                        "admin_initiated": admin_initiated,
                        "waited_seconds": waited_seconds,
                    },
                )
                return {
                    "found": 0,
                    "added": 0,
                    "updated": 0,
                    "duplicates_removed": 0,
                    "expired_removed": 0,
                    "errors": 0,
                    "embedded": 0,
                    "provider_results": [],
                    "refresh_summary": {
                        "found": 0,
                        "added": 0,
                        "updated": 0,
                        "duplicates_removed": 0,
                        "expired_removed": 0,
                        "errors": 0,
                        "embedded": 0,
                    },
                    "visibility_reason": {
                        "code": "provider_sync_in_progress",
                        "message": "A provider refresh is already running.",
                    },
                    "skipped": True,
                    "skip_reason": "provider_sync_in_progress",
                    "theirstack": theirstack_result,
                }
            await sleep(JOB_SYNC_WAIT_INTERVAL_SECONDS)
            waited_seconds += JOB_SYNC_WAIT_INTERVAL_SECONDS

        if admin_initiated:
            try:
                from src.db.session import async_session
                from src.integrations.theirstack.sync_service import TheirStackSyncService
                service = TheirStackSyncService()
                async with async_session() as db:
                    repo = JobRepository(db)
                    last_fetched_at = await repo.get_last_fetched_at_for_source("theirstack")
                    recent_source_job_ids = await repo.find_recent_source_job_ids("theirstack", limit=250)

                    provider_preferences = dict(preferences or {})
                    if last_fetched_at:
                        provider_preferences["discovered_at_gte"] = last_fetched_at
                    elif recent_source_job_ids:
                        provider_preferences["exclude_job_ids"] = recent_source_job_ids

                    logger.info(
                        "TheirStack incremental hints discovered_at_gte=%s exclude_job_ids_count=%s",
                        last_fetched_at.isoformat() if last_fetched_at else None,
                        len(provider_preferences.get("exclude_job_ids", []) or []),
                    )

                    if stage_callback:
                        await stage_callback("fetch_jobs")
                    discovered = await service.search_from_resume(resume_profile or {}, provider_preferences)
                    if stage_callback:
                        await stage_callback("normalize")
                    added, updated, expired = await service.upsert_jobs(db, discovered.get("jobs", []))
                    if stage_callback:
                        await stage_callback("deduplicate")
                        await stage_callback("enrich")
                theirstack_result = {
                    "configured": discovered.get("configured", False),
                    "found": discovered.get("found", 0),
                    "normalized": discovered.get("normalized", 0),
                    "india_likely": discovered.get("india_likely", 0),
                    "non_india_rejected": discovered.get("non_india_rejected", 0),
                    "added": added,
                    "updated": updated,
                    "expired_removed": expired,
                    "queries": discovered.get("queries", []),
                    "errors": discovered.get("errors", []),
                    "audit": discovered.get("audit", {}),
                    "provider_blocked": discovered.get("provider_blocked", False),
                    "billing_required": discovered.get("billing_required", False),
                    "provider_status_code": discovered.get("provider_status_code", 0),
                    "provider_health": discovered.get("provider_health", {}),
                }
                provider_results.append(
                    provider_result_payload(
                        provider="theirstack",
                        display_name=self._provider_display_name("theirstack"),
                        status="blocked" if discovered.get("provider_blocked") else "completed",
                        configured=discovered.get("configured", False),
                        provider_blocked=discovered.get("provider_blocked", False),
                        billing_required=discovered.get("billing_required", False),
                        provider_status_code=discovered.get("provider_status_code", 0),
                        found=discovered.get("found", 0),
                        normalized=discovered.get("normalized", 0),
                        added=added,
                        updated=updated,
                        duplicates_removed=0,
                        expired_removed=expired,
                        error_count=len(discovered.get("errors", [])),
                        message=(
                            "Billing required"
                            if discovered.get("billing_required")
                            else "Provider blocked"
                            if discovered.get("provider_blocked")
                            else provider_refresh_message(
                                "theirstack",
                                found=discovered.get("found", 0),
                                added=added,
                                updated=updated,
                                duplicates=0,
                                expired=expired,
                            )
                        ),
                        query_context=getattr(service, "last_query_context", None),
                        sample_updated_jobs=list(getattr(service, "last_updated_jobs", []) or []),
                    ),
                )
                total_found += int(discovered.get("found", 0))
                total_added += added
                total_updated += updated
                total_expired += expired
                logger.info(
                    "TheirStack sync complete: found=%s, india=%s, added=%s, "
                    "slot=%s, rate_limited=%s",
                    discovered.get("found", 0),
                    discovered.get("india_likely", 0),
                    added,
                    discovered.get("audit", {}).get("selected_key_slot", ""),
                    discovered.get("audit", {}).get("rate_limited_slots", []),
                )
            except Exception as e:
                errors += 1
                theirstack_result = {
                    "configured": bool(getattr(settings, "THEIRSTACK_API_KEY", None)),
                    "found": 0,
                    "errors": [str(e)[:256]],
                    "audit": {},
                    "provider_health": {
                        "provider": "theirstack",
                        "status": "error",
                        "configured": bool(getattr(settings, "THEIRSTACK_API_KEY", None)),
                        "billing_required": False,
                        "provider_blocked": False,
                    },
                }
                logger.error("TheirStack sync failed: %s", e)
        else:
            theirstack_result = {
                "configured": False,
                "found": 0,
                "added": 0,
                "updated": 0,
                "expired_removed": 0,
                "errors": [],
                "audit": {},
                "provider_health": {
                    "provider": "theirstack",
                    "status": "skipped",
                    "configured": True,
                    "billing_required": False,
                    "provider_blocked": False,
                    "provider_http_call_count": 0,
                    "reason": "automatic_refresh_skips_paid_provider",
                },
            }
            logger.info(
                "Skipping TheirStack during automatic job refresh; paid provider is reserved for manual refresh clicks",
                extra={"provider": "theirstack", "admin_initiated": admin_initiated},
            )

        for source in sources:
            try:
                found, added, updated, duplicates, expired, query_context, sample_updated_jobs = await self._sync_source(
                    source,
                    stage_callback=stage_callback,
                )
                total_found += found
                total_added += added
                total_updated += updated
                total_duplicates += duplicates
                total_expired += expired
                provider_results.append(
                    provider_result_payload(
                        provider=source,
                        display_name=self._provider_display_name(source),
                        status="completed",
                        configured=True,
                        provider_blocked=False,
                        billing_required=False,
                        provider_status_code=200,
                        found=found,
                        normalized=found,
                        added=added,
                        updated=updated,
                        duplicates_removed=duplicates,
                        expired_removed=expired,
                        error_count=0,
                        message=provider_refresh_message(
                            source,
                            found=found,
                            added=added,
                            updated=updated,
                            duplicates=duplicates,
                            expired=expired,
                        ),
                        query_context=query_context,
                        sample_updated_jobs=sample_updated_jobs,
                    )
                )
                logger.info(
                    "provider=%s found=%s added=%s updated=%s duplicates=%s expired=%s",
                    source,
                    found,
                    added,
                    updated,
                    duplicates,
                    expired,
                )
            except Exception as e:
                errors += 1
                logger.error(f"Sync failed for {source}: {e}")
                provider_results.append(
                    {
                        "provider": source,
                        "display_name": self._provider_display_name(source),
                        "status": "error",
                        "configured": False,
                        "provider_blocked": False,
                        "billing_required": False,
                        "provider_status_code": 0,
                        "found": 0,
                        "normalized": 0,
                        "added": 0,
                        "updated": 0,
                        "duplicates_removed": 0,
                        "expired_removed": 0,
                        "error_count": 1,
                        "message": str(e)[:256],
                    }
                )

        # Embed newly added jobs into Qdrant
        try:
            embed_result = await self.embed_jobs_batch(limit=50)
            logger.info(f"Embedded {embed_result['embedded']} jobs into Qdrant")
        except Exception as e:
            logger.error(f"Failed to embed jobs: {e}")
            errors += 1
        finally:
            current_lease = await redis_client.get(JOB_SYNC_LOCK_KEY)
            if current_lease == lease_id:
                await redis_client.delete(JOB_SYNC_LOCK_KEY)

        refresh_summary = {
            "found": total_found,
            "added": total_added,
            "updated": total_updated,
            "duplicates_removed": total_duplicates,
            "expired_removed": total_expired,
            "errors": errors,
            "embedded": embed_result.get("embedded", 0),
        }
        visibility_reason = self._build_refresh_reason(
            resume_profile=resume_profile,
            provider_results=provider_results,
            total_found=total_found,
            total_added=total_added,
            total_updated=total_updated,
            total_duplicates=total_duplicates,
            total_expired=total_expired,
            errors=errors,
        )

        return {
            "found": total_found,
            "added": total_added,
            "updated": total_updated,
            "duplicates_removed": total_duplicates,
            "expired_removed": total_expired,
            "errors": errors,
            "embedded": embed_result.get("embedded", 0),
            "theirstack": theirstack_result,
            "provider_results": provider_results,
            "refresh_summary": refresh_summary,
            "visibility_reason": visibility_reason,
        }

    async def _sync_source(
        self,
        source: str,
        stage_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Tuple[int, int, int, int, int, Dict[str, Any], List[Dict[str, Any]]]:
        from src.db.session import async_session
        from src.db.repositories.domain_repositories import JobRepository
        from src.models.jobs import Job

        jobs = await self._fetch_source(source)
        if stage_callback:
            await stage_callback("normalize")
        direct_jobs = [job for job in jobs if self._is_direct_posting_url(job.get("source_url", ""))]
        if stage_callback:
            await stage_callback("deduplicate")
        found = len(direct_jobs)
        added = 0
        updated = 0
        duplicates = max(0, len(jobs) - len(direct_jobs))
        expired = 0
        fetched_at = datetime.utcnow()
        seen_source_ids: set[str] = set()
        updated_samples: List[Dict[str, Any]] = []

        query_context = build_provider_query_context(
            source,
            found=found,
            limit=len(jobs) or found,
            query=f"direct {self._provider_display_name(source)} feed",
            configured=True,
        )

        if stage_callback:
            await stage_callback("enrich")

        async with async_session() as db:
            repo = JobRepository(db)
            for job_data in direct_jobs:
                source_job_id = self._source_job_id(source, job_data)
                if source_job_id in seen_source_ids:
                    duplicates += 1
                    continue
                seen_source_ids.add(source_job_id)
                job_uid = self._make_job_uid(
                    source,
                    source_job_id,
                    job_data.get("source_url", ""),
                    job_data.get("title", ""),
                )
                legacy_source_job_id = source_job_id
                legacy_job_uid = job_uid
                if source == "greenhouse" and ":" in source_job_id:
                    legacy_source_job_id = source_job_id.split(":", 1)[1]
                    legacy_job_uid = self._make_job_uid(
                        source,
                        "",
                        job_data.get("source_url", ""),
                        job_data.get("title", ""),
                    )
                freshness_score, freshness_bucket = self._freshness(job_data.get("posted_date"))
                is_stale = freshness_bucket == "stale"
                lookup_clause = or_(
                    Job.source_job_id == source_job_id,
                    Job.job_uid == job_uid,
                )
                if source == "greenhouse" and legacy_source_job_id != source_job_id:
                    lookup_clause = or_(
                        Job.source_job_id == source_job_id,
                        Job.source_job_id == legacy_source_job_id,
                        Job.job_uid == job_uid,
                        Job.job_uid == legacy_job_uid,
                    )
                existing_result = await db.execute(select(Job).where(
                    Job.source == source,
                    lookup_clause,
                ).limit(1))
                existing = existing_result.scalar_one_or_none()
                loc_decision = classify_job_location(
                    location_raw=job_data.get("location", ""),
                    title=job_data.get("title", ""),
                    description=job_data.get("description", ""),
                )
                from src.services.job_role_filter import classify_tech_role, extract_job_experience_requirement
                tech_decision = classify_tech_role(
                    title=job_data.get("title", ""),
                    description=job_data.get("description", ""),
                    skills=job_data.get("skills_required"),
                    category=job_data.get("category"),
                )
                exp_decision = extract_job_experience_requirement(
                    title=job_data.get("title", ""),
                    description=job_data.get("description", ""),
                )
                is_non_tech = not tech_decision["is_tech_role"] and tech_decision["confidence"] >= 0.7
                values = {
                    "job_uid": job_uid,
                    "title": job_data["title"][:500],
                    "company": job_data.get("company", "")[:256],
                    "location": job_data.get("location", "")[:256],
                    "description": job_data.get("description", "")[:50000],
                    "source": source,
                    "source_provider": source,
                    "source_job_id": source_job_id,
                    "source_url": job_data.get("source_url", "")[:1024],
                    "apply_url": job_data.get("source_url", "")[:1024],
                    "posted_date": job_data.get("posted_date"),
                    "fetched_at": fetched_at,
                    "salary_range": str(job_data.get("salary_range", ""))[:128],
                    "skills_required": job_data.get("skills_required", []),
                    "freshness_score": freshness_score,
                    "freshness_bucket": freshness_bucket,
                    "provider_quality_score": self._provider_quality(source),
                    "salary_quality_score": 90.0 if job_data.get("salary_range") else 30.0,
                    "apply_url_valid": True,
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
                    "exclusion_reason": (
                        f"non_tech_role: {tech_decision['reason']}"
                        if is_non_tech
                        else loc_decision.exclusion_reason
                    ),
                }
                if is_non_tech:
                    status_val = "excluded"
                elif not loc_decision.is_india_eligible:
                    status_val = "excluded"
                elif is_stale:
                    status_val = "expired"
                else:
                    status_val = "active"
                values["status"] = status_val
                values["lifecycle_state"] = (
                    "EXCLUDED" if (is_non_tech or not loc_decision.is_india_eligible)
                    else "EXPIRED" if is_stale
                    else "NEW"
                )
                create_values = dict(values)
                update_values = {k: v for k, v in values.items() if k != "job_uid"}
                if is_stale or is_non_tech:
                    if existing:
                        changed_fields = updated_fields(existing, update_values)
                        await repo.update(existing.id, **update_values, updated_by="system")
                        updated += 1
                        if len(updated_samples) < 3:
                            updated_samples.append(
                                updated_job_sample(
                                    source=source,
                                    source_job_id=source_job_id,
                                    job_data=job_data,
                                    fetched_at=fetched_at,
                                    updated_fields=changed_fields or ["last_seen_at"],
                                )
                            )
                    else:
                        try:
                            await repo.create(
                                **create_values,
                                ingested_at=fetched_at,
                                created_by="system",
                            )
                            added += 1
                        except IntegrityError:
                            await db.rollback()
                            dup_result = await db.execute(select(Job).where(
                                Job.source == source,
                                lookup_clause,
                            ).limit(1))
                            dup = dup_result.scalar_one_or_none()
                            if dup:
                                changed_fields = updated_fields(dup, update_values)
                                await repo.update(dup.id, **update_values, updated_by="system")
                                updated += 1
                                if len(updated_samples) < 3:
                                    updated_samples.append(
                                        updated_job_sample(
                                            source=source,
                                            source_job_id=source_job_id,
                                            job_data=job_data,
                                            fetched_at=fetched_at,
                                            updated_fields=changed_fields or ["last_seen_at"],
                                        )
                                    )
                            else:
                                raise
                else:
                    if existing:
                        changed_fields = updated_fields(existing, update_values)
                        await repo.update(existing.id, **update_values, updated_by="system")
                        updated += 1
                        if len(updated_samples) < 3:
                            updated_samples.append(
                                updated_job_sample(
                                    source=source,
                                    source_job_id=source_job_id,
                                    job_data=job_data,
                                    fetched_at=fetched_at,
                                    updated_fields=changed_fields or ["last_seen_at"],
                                )
                            )
                    else:
                        try:
                            await repo.create(
                                **create_values,
                                ingested_at=fetched_at,
                                created_by="system",
                            )
                            added += 1
                        except IntegrityError:
                            await db.rollback()
                            dup_result = await db.execute(select(Job).where(
                                Job.source == source,
                                lookup_clause,
                            ).limit(1))
                            dup = dup_result.scalar_one_or_none()
                            if dup:
                                changed_fields = updated_fields(dup, update_values)
                                await repo.update(dup.id, **update_values, updated_by="system")
                                updated += 1
                                if len(updated_samples) < 3:
                                    updated_samples.append(
                                        updated_job_sample(
                                            source=source,
                                            source_job_id=source_job_id,
                                            job_data=job_data,
                                            fetched_at=fetched_at,
                                            updated_fields=changed_fields or ["last_seen_at"],
                                        )
                                    )
                            else:
                                raise

            if seen_source_ids:
                current = await db.execute(select(Job).where(
                    Job.source == source,
                    Job.status == "active",
                    Job.deleted_at.is_(None),
                ))
                for job in current.scalars().all():
                    if job.source_job_id not in seen_source_ids:
                        job.status = "expired"
                        job.deleted_at = fetched_at
                        job.updated_at = fetched_at
                        expired += 1
                if expired:
                    await db.commit()

        return found, added, updated, duplicates, expired, query_context, updated_samples

    async def _fetch_source(self, source: str) -> List[Dict[str, Any]]:
        fetchers = {
            "remoteok": self._fetch_remoteok,
            "arbeitnow": self._fetch_arbeitnow,
            "adzuna": self._fetch_adzuna,
            "usajobs": self._fetch_usajobs,
            "greenhouse": self._fetch_greenhouse,
            "lever": self._fetch_lever,
        }
        fetcher = fetchers.get(source)
        if not fetcher:
            return []
        return await fetcher()

    async def _fetch_remoteok(self) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self._client_timeout) as client:
                resp = await client.get("https://remoteok.com/api", headers={
                    "User-Agent": "CareerOS/1.0 (careeros@example.com)",
                    "Accept": "application/json",
                }, follow_redirects=True)
                if resp.status_code != 200:
                    logger.warning(f"RemoteOK API returned {resp.status_code}")
                    return []
                data = resp.json()
                jobs = []
                # Improved parsing: fetch up to 150 items, handle dict format if API changed
                items = data[1:] if isinstance(data, list) and len(data) > 1 else (data if isinstance(data, list) else [])
                for item in items[:150]:
                    try:
                        if isinstance(item, dict):
                            title = item.get("position", "") or item.get("title", "")
                            company = item.get("company", "")
                            desc = item.get("description", "") or item.get("description_html", "")
                            url = item.get("url", "")
                            source_job_id = str(item.get("id") or item.get("slug") or url)
                            posted_date = self._parse_datetime(item.get("date") or item.get("epoch"))
                        elif isinstance(item, list) and len(item) >= 8:
                            title = str(item[2]) if item[2] else ""
                            company = str(item[3]) if len(item) > 3 and item[3] else ""
                            desc = str(item[7]) if len(item) > 7 and item[7] else ""
                            url = str(item[5]) if len(item) > 5 and item[5] else ""
                            source_job_id = url
                            posted_date = None
                        else:
                            continue
                        
                        if not title:
                            continue
                        jobs.append({
                            "title": title[:500],
                            "company": company[:256],
                            "location": "Remote",
                            "description": self._strip_html(desc)[:5000],
                            "source_job_id": source_job_id,
                            "source_url": url[:1024],
                            "posted_date": posted_date,
                            "skills_required": self._extract_skills(desc),
                            "salary_range": str(item.get("salary", "")) if isinstance(item, dict) else "",
                        })
                    except (IndexError, TypeError, ValueError, AttributeError):
                        continue
                return jobs
        except Exception as e:
            logger.warning(f"RemoteOK fetch failed (non-critical): {e}")
            return []

    async def _fetch_arbeitnow(self) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self._client_timeout, follow_redirects=True) as client:
                resp = await client.get("https://arbeitnow.com/api/job-board-api", headers={"User-Agent": "CareerOS/1.0"})
                if resp.status_code != 200:
                    return []
                data = resp.json()
                jobs = []
                for item in data.get("data", [])[:40]:
                    jobs.append({
                        "title": item.get("title", ""),
                        "company": item.get("company_name", ""),
                        "location": item.get("location", ""),
                        "description": self._strip_html(item.get("description", ""))[:5000],
                        "source_job_id": str(item.get("slug") or item.get("url") or item.get("title", "")),
                        "source_url": item.get("url", ""),
                        "posted_date": self._parse_datetime(item.get("created_at") or item.get("published_at")),
                        "skills_required": self._extract_skills(item.get("description", "")),
                        "salary_range": "",
                    })
                return jobs
        except Exception as e:
            logger.warning(f"Arbeitnow fetch failed (non-critical): {e}")
            return []

    async def _fetch_adzuna(self) -> List[Dict[str, Any]]:
        adzuna_id = getattr(settings, "ADZUNA_APP_ID", None) or "demo"
        adzuna_key = getattr(settings, "ADZUNA_API_KEY", None) or "demo"
        try:
            async with httpx.AsyncClient(timeout=self._client_timeout) as client:
                url = "https://api.adzuna.com/v1/api/jobs/us/search/1"
                resp = await client.get(url, params={
                    "app_id": adzuna_id,
                    "app_key": adzuna_key,
                    "results_per_page": 40,
                    "what": "software engineer",
                }, headers={"User-Agent": "CareerOS/1.0"})
                if resp.status_code != 200:
                    # Adzuna requires real API keys; return empty for demo mode
                    logger.info(f"Adzuna API returned {resp.status_code} (expected without real key)")
                    return []
                data = resp.json()
                jobs = []
                for item in data.get("results", [])[:40]:
                    jobs.append({
                        "title": item.get("title", ""),
                        "company": item.get("company", {}).get("display_name", ""),
                        "location": ", ".join(item.get("location", {}).get("area", [])),
                        "description": item.get("description", "")[:5000],
                        "source_job_id": str(item.get("id") or item.get("redirect_url") or item.get("title", "")),
                        "source_url": item.get("redirect_url", ""),
                        "posted_date": self._parse_datetime(item.get("created") or item.get("created_at")),
                        "skills_required": self._extract_skills(item.get("description", "")),
                        "salary_range": str(item.get("salary_min", "")),
                    })
                return jobs
        except Exception as e:
            logger.warning(f"Adzuna fetch failed (non-critical): {e}")
            return []

    async def _fetch_usajobs(self) -> List[Dict[str, Any]]:
        usajobs_key = getattr(settings, "USAJOBS_API_KEY", None) or "demo"
        keywords = ["software engineer", "computer scientist", "data scientist", "ai specialist"]
        jobs = []
        try:
            async with httpx.AsyncClient(timeout=self._client_timeout) as client:
                for keyword in keywords:
                    try:
                        resp = await client.get(
                            "https://data.usajobs.gov/api/search",
                            params={"Keyword": keyword, "ResultsPerPage": 50},
                            headers={
                                "User-Agent": "CareerOS/1.0 (careeros@example.com)",
                                "Authorization-Key": usajobs_key,
                            }
                        )
                        if resp.status_code != 200:
                            logger.debug(f"USAJobs keyword '{keyword}' returned {resp.status_code}")
                            continue
                        
                        data = resp.json()
                        for item in data.get("SearchResult", {}).get("SearchResultItems", [])[:50]:
                            desc = item.get("MatchedObjectDescriptor", {})
                            jobs.append({
                                "title": desc.get("PositionTitle", ""),
                                "company": desc.get("OrganizationName", "US Government"),
                                "location": desc.get("PositionLocationDisplay", ""),
                                "description": str(desc.get("UserArea", {}).get("Details", {}).get("JobSummary", ""))[:5000],
                                "source_job_id": desc.get("PositionID") or desc.get("PositionURI", ""),
                                "source_url": desc.get("PositionURI", ""),
                                "posted_date": self._parse_datetime(desc.get("PublicationStartDate")),
                                "skills_required": self._extract_skills(str(desc.get("UserArea", {}).get("Details", {}).get("JobSummary", ""))),
                                "salary_range": desc.get("PositionRemuneration", [{}])[0].get("Description", "") if desc.get("PositionRemuneration") else "",
                            })
                    except Exception as e:
                        logger.debug(f"USAJobs keyword '{keyword}' fetch failed: {e}")
                        continue
                        
                return jobs
        except Exception as e:
            logger.warning(f"USAJobs fetch failed (non-critical): {e}")
            return []

    async def _fetch_greenhouse(self) -> List[Dict[str, Any]]:
        jobs = []
        try:
            async with httpx.AsyncClient(timeout=self._client_timeout) as client:
                for company in GREENHOUSE_TARGET_COMPANIES:
                    try:
                        resp = await client.get(
                            f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs",
                            params={"content": "true"},
                        )
                        if resp.status_code != 200:
                            logger.debug(f"Greenhouse {company} returned {resp.status_code}")
                            continue
                        
                        data = resp.json()
                        for item in data.get("jobs", [])[:30]:  # Up to 30 per company = 210 max
                            jobs.append({
                                "title": item.get("title", ""),
                                "company": item.get("company_name", company.capitalize()),
                                "location": item.get("location", {}).get("name", "") if isinstance(item.get("location"), dict) else str(item.get("location", "")),
                                "description": self._strip_html(item.get("content", ""))[:5000],
                                "source_job_id": str(
                                    f"{company}:{item.get('id') or item.get('absolute_url') or item.get('title', '')}"
                                ),
                                "board_slug": company,
                                "source_url": item.get("absolute_url", ""),
                                "posted_date": self._parse_datetime(item.get("updated_at") or item.get("first_published")),
                                "skills_required": self._extract_skills(item.get("content", "")),
                                "salary_range": "",
                            })
                    except Exception as e:
                        logger.debug(f"Greenhouse {company} fetch failed: {e}")
                        continue
                        
                return jobs
        except Exception as e:
            logger.warning(f"Greenhouse fetch failed (non-critical): {e}")
            return []

    async def _fetch_lever(self) -> List[Dict[str, Any]]:
        all_jobs = []
        
        try:
            async with httpx.AsyncClient(timeout=self._client_timeout, follow_redirects=True) as client:
                for company in LEVER_TARGET_COMPANIES:
                    try:
                        url = f"https://api.lever.co/v0/postings/{company}"
                        resp = await client.get(url, params={"mode": "json"})
                        if resp.status_code == 200:
                            data = resp.json()
                            items = data if isinstance(data, list) else []
                            for item in items[:20]:  # Limit per company to avoid overload
                                all_jobs.append({
                                    "title": item.get("text", ""),
                                    "company": item.get("categories", {}).get("team", company.title()) if isinstance(item.get("categories"), dict) else company.title(),
                                    "location": item.get("categories", {}).get("location", "") if isinstance(item.get("categories"), dict) else "",
                                    "description": self._strip_html(item.get("descriptionPlain", ""))[:5000],
                                    "source_job_id": str(item.get("id") or item.get("hostedUrl") or item.get("text", "")),
                                    "source_url": item.get("hostedUrl", ""),
                                    "posted_date": self._parse_datetime(item.get("createdAt")),
                                    "skills_required": self._extract_skills(item.get("descriptionPlain", "")),
                                    "salary_range": "",
                                })
                    except Exception as e:
                        logger.warning(f"Lever fetch failed for {company}: {e}")
                        continue
                        
                return all_jobs
        except Exception as e:
            logger.warning(f"Lever fetch failed (non-critical): {e}")
            return []

    # ── Utilities ───────────────────────────────────────────────────

    def _strip_html(self, text: str) -> str:
        import re
        return re.sub(r"<[^>]+>", " ", text)[:5000]

    def _extract_skills(self, text: str) -> List[str]:
        skill_keywords = [
            "python", "javascript", "typescript", "react", "node", "sql", "aws",
            "docker", "kubernetes", "java", "golang", "rust", "c++", "ruby",
            "postgresql", "mongodb", "redis", "graphql", "rest", "api", "linux",
            "git", "ci/cd", "terraform", "ansible", "machine learning", "data",
        ]
        text_lower = text.lower()
        return sorted(set(kw for kw in skill_keywords if kw in text_lower))

    async def enrich_job(self, job_id: int) -> Dict[str, Any]:
        from src.db.session import async_session
        from src.db.repositories.domain_repositories import JobRepository
        from src.services.intelligence.claude_service import get_claude_service

        async with async_session() as db:
            repo = JobRepository(db)
            job = await repo.get_by_id(job_id)
            if not job:
                return {"status": "not_found"}

            try:
                claude = get_claude_service()
                result = await claude.reason_text(
                    system_prompt="Extract a JSON list of technical skills and a one-sentence summary from this job posting.",
                    human_message=f"Title: {job.title}\nCompany: {job.company}\nDescription: {(job.description or '')[:2000]}\n\nReturn JSON: {{\"skills\": [\"skill1\"], \"summary\": \"one sentence\"}}",
                    category="evaluation",
                )
                import json
                if isinstance(result, dict):
                    text_content = result.get("result", "")
                    if hasattr(text_content, "content"):
                        text_content = text_content.content
                    try:
                        if isinstance(text_content, str):
                            text_content = text_content.strip()
                            if text_content.startswith("```"):
                                text_content = text_content.split("\n", 1)[-1].split("```")[0]
                            parsed = json.loads(text_content)
                            await repo.update(job.id,
                                skills_required=parsed.get("skills", job.skills_required),
                                description=f"{parsed.get('summary', '')}\n\n{job.description}" if parsed.get("summary") else job.description,
                            )
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                logger.warning(f"Job enrichment failed for {job_id}: {e}")

        return {"status": "enriched", "job_id": job_id}

    async def embed_jobs_batch(self, limit: int = 100) -> Dict[str, int]:
        """Embed jobs without embeddings into Qdrant for vector search."""
        from src.db.session import async_session
        from src.db.repositories.domain_repositories import JobRepository
        from src.services.vector_store.qdrant_service import QdrantService
        from qdrant_client.models import PointStruct

        async with async_session() as db:
            repo = JobRepository(db)
            jobs = await repo.find_active(limit=limit)
            qdrant = QdrantService()

            embedded = 0
            points = []
            for job in jobs:
                text = f"{job.title} at {job.company}. {job.description or ''}".strip()[:2000]
                if not text:
                    continue

                try:
                    from src.services.embedding.nvembed_service import NVEmbedV1Service
                    embedder = NVEmbedV1Service()
                    vec = await embedder.embed_query(text)
                    if vec:
                        points.append(PointStruct(
                            id=hash(f"job_{job.id}") & 0x7FFFFFFFFFFFFFFF,
                            vector=vec,
                            payload={
                                "job_id": str(job.id),
                                "job_uid": job.job_uid,
                                "title": job.title,
                                "company": job.company or "",
                                "source": job.source or "",
                                "source_provider": job.source_provider or job.source or "",
                                "source_job_id": job.source_job_id or job.job_uid,
                                "source_url": job.source_url or "",
                                "apply_url": job.apply_url or job.source_url or "",
                                "freshness_bucket": job.freshness_bucket or "unknown",
                                "freshness_score": job.freshness_score or 0,
                                "ingested_at": job.ingested_at.isoformat() if job.ingested_at else "",
                                "skills": job.skills_required or [],
                                "text": text,
                                "version_num": 1,
                            },
                        ))
                        embedded += 1
                except Exception as e:
                    logger.debug(f"Failed to embed job {job.id}: {e}")

            if points:
                try:
                    await qdrant.upsert_points("job_opportunities", points, validate=False)
                    logger.info(f"Embedded {embedded} jobs into Qdrant job_opportunities")
                except Exception as e:
                    logger.error(f"Failed to upsert job vectors: {e}")

            return {"embedded": embedded, "total_jobs": len(jobs)}

    async def compute_matches_for_user(self, user_id: str) -> int:
        from src.db.session import async_session
        from src.db.repositories.domain_repositories import JobRepository
        from src.services.opportunity.opportunity_match_engine import get_opportunity_match_engine

        async with async_session() as db:
            repo = JobRepository(db)
            active_jobs = await repo.find_active(limit=100)
            engine = get_opportunity_match_engine()
            matched = 0

            for job in active_jobs:
                result = engine.score(
                    opportunity={"id": str(job.id), "title": job.title, "skills": job.skills_required or []},
                    candidate={"skills": []},
                )
                if result["overall_score"] >= 50:
                    matched += 1

            return matched


_engine: Optional[JobIngestionEngine] = None


def get_job_ingestion_engine() -> JobIngestionEngine:
    global _engine
    if _engine is None:
        _engine = JobIngestionEngine()
    return _engine
