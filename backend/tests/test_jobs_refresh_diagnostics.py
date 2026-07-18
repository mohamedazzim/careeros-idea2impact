from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient

from src.api.deps import get_current_user
from src.db.session import get_db
from src.main import app


if "app" not in httpx.Client.__init__.__code__.co_varnames:
    _httpx_client_init = httpx.Client.__init__

    def _patched_httpx_client_init(self, *args, app=None, **kwargs):
        return _httpx_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = _patched_httpx_client_init


client = TestClient(app)


class _FakeResult:
    def __init__(self, scalar_value=None, rows=None):
        self._scalar_value = scalar_value
        self._rows = rows or []

    def scalar(self):
        return self._scalar_value

    def scalar_one_or_none(self):
        return self._scalar_value

    def all(self):
        return self._rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


class _FakeJobsStatsDB:
    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _statement):
        if not self._results:
            raise AssertionError("Unexpected execute call in jobs stats test")
        return self._results.pop(0)


class _FakeJobsIntelligenceService:
    async def get_active_resume(self, _db, _user_id, _resume_id):
        return SimpleNamespace(
            doc_uid="resume-123",
            title="Backend Resume",
            raw_text="CareerOS resume",
            analysis_results={},
        )

    def resume_profile(self, resume):
        return {
            "doc_uid": resume.doc_uid,
            "title": resume.title,
            "content": resume.raw_text,
        }

    def summary(self, _resume_profile, _matches):
        return {"active_resume": {"doc_uid": "resume-123"}}


def _override_user():
    return {"sub": "user-123", "role": "User"}


def test_jobs_stats_exposes_latest_refresh_diagnostics(monkeypatch):
    from src.db.repositories.domain_repositories import JobRepository

    monkeypatch.setattr(
        JobRepository,
        "get_stats",
        AsyncMock(
            return_value={
                "total_jobs": 12,
                "raw_total_jobs": 15,
                "active_jobs": 12,
                "india_eligible_jobs": 12,
                "excluded_non_india": 0,
                "filtered_out_jobs": 3,
                "non_india_filtered_jobs": 0,
                "non_tech_filtered_jobs": 0,
                "stale_or_closed_jobs": 0,
                "avg_match_score": 71.4,
                "by_source": {"remoteok": 7, "theirstack": 5},
                "india_by_source": {"remoteok": 7, "theirstack": 5},
                "last_ingested": "2026-06-13T00:00:00Z",
            }
        ),
    )
    monkeypatch.setattr(
        "src.services.opportunity.job_intelligence_service.get_job_intelligence_service",
        lambda: _FakeJobsIntelligenceService(),
    )
    monkeypatch.setattr(
        "src.integrations.theirstack.credential_resolver.resolve_keys",
        lambda: SimpleNamespace(
            has_keys=True,
            total_slots=2,
            slots=[SimpleNamespace(slot_name="primary"), SimpleNamespace(slot_name="backup")],
        ),
    )

    latest_session = SimpleNamespace(
        metadata_={
            "provider_health": {
                "theirstack": {
                    "status": "completed",
                    "billing_required": False,
                    "provider_blocked": False,
                },
                "summary": {"found": 10, "added": 3, "updated": 2, "errors": []},
            },
            "provider_results": [
                {
                    "provider": "remoteok",
                    "display_name": "RemoteOK",
                    "status": "completed",
                    "found": 4,
                    "added": 2,
                    "updated": 0,
                    "duplicates_removed": 2,
                    "expired_removed": 0,
                    "error_count": 0,
                }
            ],
            "refresh_summary": {
                "found": 4,
                "added": 2,
                "updated": 0,
                "duplicates_removed": 2,
                "expired_removed": 0,
                "errors": 0,
                "embedded": 2,
            },
            "visibility_reason": {
                "code": "jobs_refreshed",
                "message": "The refresh added 2 new job(s) and updated 0 existing job(s).",
            },
        }
    )

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: _FakeJobsStatsDB([
        _FakeResult(rows=[]),
        _FakeResult(scalar_value=latest_session),
    ])

    response = client.get("/api/v1/jobs/stats")

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert data["provider_health"]["theirstack"]["latest_refresh_reason"]["code"] == "jobs_refreshed"
    assert data["provider_health"]["theirstack"]["latest_provider_results"][0]["provider"] == "remoteok"
    assert data["provider_health"]["theirstack"]["latest_refresh_summary"]["added"] == 2
    assert data["provider_health"]["theirstack"]["status"] == "completed"


def test_job_refresh_service_builds_diagnostics_payload():
    from src.services.job_refresh import JobRefreshService

    service = JobRefreshService()
    session = SimpleNamespace(
        status="completed",
        metadata_={
            "resume_doc_uid": "resume-123",
            "provider_results": [
                {
                    "provider": "theirstack",
                    "display_name": "TheirStack",
                    "status": "blocked",
                    "provider_blocked": True,
                    "billing_required": True,
                    "found": 0,
                    "added": 0,
                    "updated": 0,
                    "duplicates_removed": 0,
                    "expired_removed": 0,
                    "error_count": 0,
                    "message": "Billing required",
                },
                {
                    "provider": "remoteok",
                    "display_name": "RemoteOK",
                    "status": "completed",
                    "found": 4,
                    "added": 0,
                    "updated": 0,
                    "duplicates_removed": 4,
                    "expired_removed": 0,
                    "error_count": 0,
                    "message": "Completed",
                },
            ],
            "refresh_summary": {
                "found": 4,
                "added": 0,
                "updated": 0,
                "duplicates_removed": 4,
                "expired_removed": 0,
                "errors": 0,
                "embedded": 0,
            },
            "visibility_reason": {
                "code": "provider_billing_required",
                "message": "TheirStack returned a billing-required response, so no new jobs could be fetched from that source.",
            },
        },
    )

    payload = service.build_diagnostics_payload(session)

    assert payload["status"] == "completed"
    assert payload["reason_code"] == "provider_billing_required"
    assert payload["reason"].startswith("TheirStack returned a billing-required response")
    assert payload["summary"]["found"] == 4
    assert payload["summary"]["duplicates_removed"] == 4
    assert payload["provider_results"][0]["provider"] == "theirstack"
    assert payload["provider_results"][1]["provider"] == "remoteok"


def test_job_refresh_service_builds_existing_only_visibility_reason_and_enriched_diagnostics():
    from src.services.job_refresh import JobRefreshService

    service = JobRefreshService()
    session = SimpleNamespace(
        status="completed",
        metadata_={
            "resume_doc_uid": "resume-123",
            "provider_results": [
                {
                    "provider": "remoteok",
                    "display_name": "RemoteOK",
                    "status": "completed",
                    "found": 100,
                    "added": 0,
                    "updated": 100,
                    "duplicates_removed": 0,
                    "expired_removed": 0,
                    "error_count": 0,
                    "query_context": {
                        "provider": "remoteok",
                        "query": "direct RemoteOK feed",
                        "location": "India/Remote filters",
                        "limit": 100,
                        "since": "not used",
                        "configured": True,
                    },
                    "sample_updated_jobs": [
                        {
                            "title": "Backend Developer",
                            "company": "Okta",
                            "provider": "remoteok",
                            "external_job_id": "rk-123",
                            "last_seen_at": "2026-06-13T00:00:00Z",
                            "updated_fields": ["freshness_score", "last_seen_at"],
                        }
                    ],
                    "message": "All 100 provider jobs already existed in CareerOS.",
                },
                {
                    "provider": "greenhouse",
                    "display_name": "Greenhouse",
                    "status": "completed",
                    "found": 270,
                    "added": 0,
                    "updated": 270,
                    "duplicates_removed": 30,
                    "expired_removed": 0,
                    "error_count": 0,
                    "query_context": {
                        "provider": "greenhouse",
                        "query": "direct Greenhouse feed",
                        "location": "India/Remote filters",
                        "limit": 270,
                        "since": "not used",
                        "configured": True,
                    },
                    "sample_updated_jobs": [],
                    "message": "All 270 provider jobs already existed in CareerOS.",
                },
            ],
            "refresh_summary": {
                "found": 370,
                "added": 0,
                "updated": 370,
                "duplicates_removed": 30,
                "expired_removed": 0,
                "errors": 0,
                "embedded": 50,
            },
            "provider_query_contexts": [
                {
                    "provider": "remoteok",
                    "query": "direct RemoteOK feed",
                    "location": "India/Remote filters",
                    "limit": 100,
                    "since": "not used",
                    "configured": True,
                }
            ],
            "sample_updated_jobs": [
                {
                    "title": "Backend Developer",
                    "company": "Okta",
                    "provider": "remoteok",
                    "external_job_id": "rk-123",
                    "last_seen_at": "2026-06-13T00:00:00Z",
                    "updated_fields": ["freshness_score", "last_seen_at"],
                }
            ],
        },
    )

    payload = service.build_diagnostics_payload(session)

    assert payload["reason_code"] == "providers_returned_only_existing_jobs"
    assert payload["reason"].startswith("Providers returned 370 jobs")
    assert payload["totals"]["fetched"] == 370
    assert payload["totals"]["new_unique"] == 0
    assert payload["totals"]["updated_existing"] == 370
    assert payload["dedupe"]["strategy"] == "provider_external_id_then_canonical_fingerprint"
    assert payload["visibility"]["visible_list_changed"] is False
    assert payload["visibility"]["reason_if_unchanged"] == "providers_returned_only_existing_jobs"
    assert payload["sample_updated_jobs"][0]["provider"] == "remoteok"
    assert payload["provider_query_contexts"][0]["query"] == "direct RemoteOK feed"
    assert "api_key" not in json.dumps(payload).lower()


def test_job_ingestion_engine_builds_duplicate_only_visibility_reason():
    from src.services.jobs import JobIngestionEngine

    engine = JobIngestionEngine()
    reason = engine._build_refresh_reason(
        resume_profile={"status": "indexed"},
        provider_results=[
            {
                "provider": "remoteok",
                "display_name": "RemoteOK",
                "status": "completed",
                "found": 5,
                "added": 0,
                "updated": 0,
                "duplicates_removed": 5,
                "expired_removed": 0,
                "error_count": 0,
            }
        ],
        total_found=5,
        total_added=0,
        total_updated=0,
        total_duplicates=5,
        total_expired=0,
        errors=0,
    )

    assert reason["code"] == "duplicate_only"
    assert "matched an existing record" in reason["message"]


def test_job_ingestion_engine_builds_existing_only_visibility_reason():
    from src.services.jobs import JobIngestionEngine

    engine = JobIngestionEngine()
    reason = engine._build_refresh_reason(
        resume_profile={"status": "indexed"},
        provider_results=[
            {
                "provider": "remoteok",
                "display_name": "RemoteOK",
                "status": "completed",
                "found": 100,
                "added": 0,
                "updated": 100,
                "duplicates_removed": 0,
                "expired_removed": 0,
                "error_count": 0,
            }
        ],
        total_found=100,
        total_added=0,
        total_updated=100,
        total_duplicates=0,
        total_expired=0,
        errors=0,
    )

    assert reason["code"] == "providers_returned_only_existing_jobs"
    assert "no new job cards were added" in reason["message"]


def test_job_card_response_includes_provider_source_and_last_seen():
    from src.api.v1.endpoints.jobs import _response_from_job

    job = SimpleNamespace(
        id=17589,
        job_uid="job-uid-17589",
        title="Backend Engineer",
        company="Okta",
        location="Remote India",
        description="Build APIs",
        source="remoteok",
        source_provider="remoteok",
        source_job_id="rk-17589",
        source_url="https://remoteok.com/jobs/17589",
        apply_url="https://remoteok.com/jobs/17589",
        posted_date=None,
        fetched_at=None,
        ingested_at=None,
        salary_range=None,
        skills_required=["python", "fastapi"],
        freshness_score=92.0,
        freshness_bucket="fresh",
        provider_quality_score=85.0,
        salary_quality_score=30.0,
        opportunity_priority_score=88.0,
        match_score=None,
        match_details={},
        lifecycle_state="NEW",
        apply_url_valid=True,
        is_india_eligible=True,
        is_tech_role=True,
        tech_role_category="backend",
        tech_role_confidence=0.9,
        seniority_level="mid",
        experience_min_years=3,
        experience_max_years=5,
        experience_filter_status="active",
        status="active",
    )

    response = _response_from_job(job)

    assert response.source_provider == "remoteok"
    assert response.fetched_at is None
    assert response.source_url == "https://remoteok.com/jobs/17589"
    assert response.title == "Backend Engineer"
