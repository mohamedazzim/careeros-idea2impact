"""Job refresh service — async background workflow layer.

Orchestrates the start/poll lifecycle for job matching runs using
the existing orchestration_sessions table.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.orchestration import OrchestrationSession


class JobRefreshService:
    """Thin service for async job refresh lifecycle."""

    @staticmethod
    def _utc_iso(value: datetime | None) -> str | None:
        """Serialize timestamps as explicit UTC so the browser does not misread naive datetimes."""
        if not value:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _default_refresh_summary() -> Dict[str, int]:
        return {
            "found": 0,
            "added": 0,
            "updated": 0,
            "duplicates_removed": 0,
            "expired_removed": 0,
            "errors": 0,
            "embedded": 0,
        }

    @staticmethod
    def _summarize_provider_results(provider_results: list[Dict[str, Any]]) -> Dict[str, int]:
        summary = JobRefreshService._default_refresh_summary()
        for item in provider_results:
            summary["found"] += int(item.get("found") or 0)
            summary["added"] += int(item.get("added") or 0)
            summary["updated"] += int(item.get("updated") or 0)
            summary["duplicates_removed"] += int(item.get("duplicates_removed") or 0)
            summary["expired_removed"] += int(item.get("expired_removed") or 0)
            summary["errors"] += int(item.get("error_count") or 0)
            summary["embedded"] += int(item.get("embedded") or 0)
        return summary

    @staticmethod
    def _build_visibility_reason(
        *,
        resume_doc_uid: str | None,
        provider_results: list[Dict[str, Any]],
        refresh_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        total_found = int(refresh_summary.get("found") or 0)
        total_added = int(refresh_summary.get("added") or 0)
        total_updated = int(refresh_summary.get("updated") or 0)
        total_duplicates = int(refresh_summary.get("duplicates_removed") or 0)
        total_expired = int(refresh_summary.get("expired_removed") or 0)
        total_errors = int(refresh_summary.get("errors") or 0)
        blocked_provider = next(
            (
                provider
                for provider in provider_results
                if provider.get("provider_blocked") or provider.get("status") == "blocked"
            ),
            None,
        )

        if not resume_doc_uid:
            return {
                "code": "resume_missing",
                "message": "Provider refresh ran, but no valid resume was selected for matching.",
            }
        if blocked_provider:
            provider_name = blocked_provider.get("display_name") or blocked_provider.get("provider") or "a provider"
            if blocked_provider.get("billing_required"):
                return {
                    "code": "provider_billing_required",
                    "message": f"{provider_name} is billing-blocked, so no new jobs were fetched from that source.",
                }
            return {
                "code": "provider_blocked",
                "message": f"{provider_name} was blocked, so refresh results from that source were not available.",
            }
        if total_found <= 0:
            if total_errors > 0:
                return {
                    "code": "provider_error",
                    "message": "The refresh completed with provider errors, but no jobs were discovered.",
                }
            return {
                "code": "no_provider_results",
                "message": "The refresh completed, but none of the configured providers returned direct job results.",
            }
        if total_added <= 0 and total_updated > 0:
            return {
                "code": "providers_returned_only_existing_jobs",
                "message": f"Providers returned {total_found} jobs, but all matched existing records, so no new job cards were added.",
            }
        if total_added <= 0 and total_updated <= 0:
            if total_duplicates > 0:
                return {
                    "code": "duplicate_only",
                    "message": "The refresh found jobs, but they were duplicates of existing records.",
                }
            if total_expired > 0:
                return {
                    "code": "all_results_expired",
                    "message": "The refresh found jobs, but they were already stale or expired.",
                }
            if total_errors > 0:
                return {
                    "code": "provider_error",
                    "message": "The refresh completed with provider errors and produced no visible job updates.",
                }
            return {
                "code": "no_new_jobs",
                "message": "The refresh completed successfully, but no new or updated jobs were available for the feed.",
            }
        return {
            "code": "jobs_refreshed",
            "message": f"The refresh added {total_added} new job(s) and updated {total_updated} existing job(s).",
        }

    def build_diagnostics_payload(
        self,
        session: OrchestrationSession,
    ) -> Dict[str, Any]:
        meta = session.metadata_ or {}
        provider_results = list(meta.get("provider_results") or [])
        provider_query_contexts = list(meta.get("provider_query_contexts") or [])
        sample_updated_jobs = list(meta.get("sample_updated_jobs") or [])
        refresh_summary = dict(meta.get("refresh_summary") or {})
        if not refresh_summary:
            refresh_summary = self._summarize_provider_results(provider_results)
        for key, value in self._default_refresh_summary().items():
            refresh_summary.setdefault(key, value)
        visibility_reason = dict(
            meta.get("visibility_reason")
            or self._build_visibility_reason(
                resume_doc_uid=meta.get("resume_doc_uid"),
                provider_results=provider_results,
                refresh_summary=refresh_summary,
            )
        )
        diagnostics = dict(meta.get("diagnostics") or {})
        diagnostics.setdefault("status", session.status)
        diagnostics.setdefault("reason_code", visibility_reason.get("code", "unknown"))
        diagnostics.setdefault("reason", visibility_reason.get("message", "Refresh diagnostics not available yet."))
        diagnostics.setdefault("summary", refresh_summary)
        diagnostics.setdefault("provider_results", provider_results)
        diagnostics.setdefault("visibility_reason", visibility_reason)
        diagnostics.setdefault(
            "totals",
            {
                "fetched": int(refresh_summary.get("found") or 0),
                "new_unique": int(refresh_summary.get("added") or 0),
                "updated_existing": int(refresh_summary.get("updated") or 0),
                "duplicate_results": int(refresh_summary.get("duplicates_removed") or 0),
                "visible_new_jobs": int(refresh_summary.get("added") or 0),
            },
        )
        diagnostics.setdefault(
            "dedupe",
            {
                "strategy": "provider_external_id_then_canonical_fingerprint",
                "new_insert_count": int(refresh_summary.get("added") or 0),
                "existing_match_count": int(refresh_summary.get("updated") or 0),
                "duplicate_result_count": int(refresh_summary.get("duplicates_removed") or 0),
                "possible_over_dedupe_count": max(
                    0,
                    int(refresh_summary.get("found") or 0)
                    - int(refresh_summary.get("added") or 0)
                    - int(refresh_summary.get("updated") or 0)
                    - int(refresh_summary.get("duplicates_removed") or 0),
                ),
            },
        )
        diagnostics.setdefault(
            "visibility",
            {
                "visible_list_changed": bool(int(refresh_summary.get("added") or 0) > 0),
                "reason_if_unchanged": (
                    visibility_reason.get("code")
                    if not int(refresh_summary.get("added") or 0)
                    else None
                ),
                "message": visibility_reason.get("message"),
            },
        )
        if not sample_updated_jobs:
            for provider in provider_results:
                sample_updated_jobs.extend(list(provider.get("sample_updated_jobs") or []))
        diagnostics.setdefault("sample_updated_jobs", sample_updated_jobs[:5])
        if not provider_query_contexts:
            provider_query_contexts = [
                provider.get("query_context")
                for provider in provider_results
                if provider.get("query_context")
            ]
        diagnostics.setdefault("provider_query_contexts", provider_query_contexts)
        return diagnostics

    async def start_refresh(
        self,
        db: AsyncSession,
        user_id: str,
        resume_doc_uid: str | None,
        resume_profile: Dict[str, Any],
        preferences: Optional[Dict[str, Any]] = None,
    ) -> OrchestrationSession:
        """Create a new queued session and return it. Does NOT run matching."""
        requested_preferences = preferences or {}
        cooldown_seconds = max(1, int(getattr(settings, "JOB_REFRESH_COOLDOWN_SECONDS", 120) or 120))
        results = await db.execute(
            select(OrchestrationSession).where(
                OrchestrationSession.user_id == user_id,
                OrchestrationSession.graph_name == "job_refresh",
                OrchestrationSession.status.in_(["queued", "running", "completed"]),
                OrchestrationSession.deleted_at.is_(None),
            ).order_by(OrchestrationSession.created_at.desc()).limit(1)
        )
        existing = results.scalar_one_or_none()
        if existing:
            metadata = existing.metadata_ or {}
            recently_updated = bool(
                existing.updated_at and existing.updated_at >= datetime.utcnow() - timedelta(seconds=cooldown_seconds)
            )
            if (
                recently_updated
                and
                metadata.get("resume_doc_uid") == resume_doc_uid
                and (metadata.get("preferences") or {}) == requested_preferences
            ):
                metadata = dict(metadata)
                metadata["reused_existing_refresh"] = True
                metadata["next_refresh_at"] = (
                    (existing.updated_at or datetime.utcnow()) + timedelta(seconds=cooldown_seconds)
                ).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                existing.metadata_ = metadata
                await db.commit()
                await db.refresh(existing)
                return existing

        session = OrchestrationSession(
            session_uid=str(uuid.uuid4()),
            user_id=user_id,
            graph_name="job_refresh",
            status="queued",
            current_node="queued",
            completion_pct=0.0,
            metadata_={
                "resume_doc_uid": resume_doc_uid,
                "resume": {k: v for k, v in resume_profile.items() if k != "content"},
                "preferences": requested_preferences,
                "reused_existing_refresh": False,
                "next_refresh_at": None,
                "progress": {"processed": 0, "total": 0, "failed": 0},
                "stage_history": [],
                "provider_results": [],
                "provider_query_contexts": [],
                "sample_updated_jobs": [],
                "refresh_summary": self._default_refresh_summary(),
                "visibility_reason": {
                    "code": "queued",
                    "message": "Job refresh is queued and provider diagnostics will appear once the worker runs.",
                },
                "diagnostics": {
                    "status": "queued",
                    "reason_code": "queued",
                    "reason": "Job refresh is queued and provider diagnostics will appear once the worker runs.",
                    "summary": self._default_refresh_summary(),
                    "provider_results": [],
                    "provider_query_contexts": [],
                    "sample_updated_jobs": [],
                    "visibility_reason": {
                        "code": "queued",
                        "message": "Job refresh is queued and provider diagnostics will appear once the worker runs.",
                    },
                },
            },
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def get_status(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Return the session status payload, or None if not found."""
        result = await db.execute(
            select(OrchestrationSession).where(OrchestrationSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return None

        meta = session.metadata_ or {}
        diagnostics = self.build_diagnostics_payload(session)
        return {
            "session_id": session.id,
            "session_uid": session.session_uid,
            "status": session.status,
            "current_node": session.current_node,
            "completion_pct": session.completion_pct,
            "progress": meta.get("progress", {"processed": 0, "total": 0, "failed": 0}),
            "stage_history": meta.get("stage_history", []),
            "provider_health": meta.get("provider_health"),
            "provider_results": meta.get("provider_results", []),
            "refresh_summary": meta.get("refresh_summary", self._default_refresh_summary()),
            "visibility_reason": meta.get("visibility_reason", diagnostics.get("visibility_reason")),
            "diagnostics": diagnostics,
            "resume": meta.get("resume"),
            "error": (session.errors or {}).get("message"),
            "created_at": self._utc_iso(session.created_at),
            "updated_at": self._utc_iso(session.updated_at),
        }


_job_refresh_service: Optional[JobRefreshService] = None


def get_job_refresh_service() -> JobRefreshService:
    global _job_refresh_service
    if _job_refresh_service is None:
        _job_refresh_service = JobRefreshService()
    return _job_refresh_service
