from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

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

    def all(self):
        return self._rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


class _CaptureDB:
    def __init__(self, results):
        self.results = list(results)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        if self.results:
            return self.results.pop(0)
        return _FakeResult()


class _FakeJobsIntelligenceService:
    def __init__(self):
        self.resume_calls: list[str | None] = []

    async def get_active_resume(self, _db, _user_id, _resume_id):
        self.resume_calls.append(_resume_id)
        if not _resume_id:
            return None
        return SimpleNamespace(
            doc_uid=_resume_id,
            title="Backend Resume",
            raw_text="CareerOS resume",
            analysis_results={},
        )

    def resume_profile(self, resume):
        if not resume:
            return {}
        return {
            "doc_uid": resume.doc_uid,
            "title": resume.title,
            "content": resume.raw_text,
        }

    def summary(self, _resume_profile, _matches):
        return {"active_resume": {"doc_uid": "resume-123"}}


def _override_user():
    return {"sub": "user-123", "role": "User"}


def test_job_response_uses_real_posted_date_and_keeps_nulls():
    from src.api.v1.endpoints.jobs import _response_from_job

    posted_at = datetime(2026, 6, 13, 10, 30, 0)
    job = SimpleNamespace(
        id=7,
        job_uid="job-7",
        title="Backend Engineer",
        company="CareerOS",
        location="Remote",
        description="Build CareerOS",
        source="greenhouse",
        source_provider="greenhouse",
        source_job_id="gh-7",
        source_url="https://example.com/jobs/7",
        apply_url="https://example.com/apply/7",
        posted_date=posted_at,
        fetched_at=datetime(2026, 6, 14, 9, 15, 0),
        salary_range="$120k-$150k",
        skills_required=["python", "fastapi"],
        freshness_score=91.2,
        freshness_bucket="fresh",
        provider_quality_score=88.0,
        salary_quality_score=77.0,
        opportunity_priority_score=93.0,
        lifecycle_state="NEW",
        apply_url_valid=True,
        is_india_eligible=True,
        is_tech_role=True,
        tech_role_category="backend",
        tech_role_confidence=0.98,
        seniority_level="mid",
        experience_min_years=3.0,
        experience_max_years=6.0,
        experience_filter_status="compatible",
        match_score=82.0,
        match_details={},
        status="active",
        ingested_at=datetime(2026, 6, 14, 10, 0, 0),
    )

    response = _response_from_job(job, None)

    assert response.posted_date == "2026-06-13T10:30:00Z"
    assert response.posted_at == "2026-06-13T10:30:00Z"
    assert response.fetched_at == "2026-06-14T09:15:00Z"

    missing_posted = SimpleNamespace(**{**job.__dict__, "posted_date": None, "posted_at": None})
    missing_response = _response_from_job(missing_posted, None)

    assert missing_response.posted_date is None
    assert missing_response.posted_at is None


def test_jobs_sort_posted_at_desc_preserves_resume_and_orders_nulls_last(monkeypatch):
    from src.services.opportunity import job_intelligence_service as job_intel_module

    fake_service = _FakeJobsIntelligenceService()
    fake_db = _CaptureDB([
        _FakeResult(rows=[]),
        _FakeResult(scalar_value=0),
        _FakeResult(scalar_value=0),
        _FakeResult(rows=[]),
    ])

    monkeypatch.setattr(job_intel_module, "get_job_intelligence_service", lambda: fake_service)
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: fake_db

    response = client.get(
        "/api/v1/jobs",
        params={
            "resume_id": "resume-123",
            "include_unmatched": "true",
            "source": "greenhouse",
            "sort": "posted_at_desc",
            "limit": 5,
            "offset": 0,
        },
    )

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert fake_service.resume_calls == ["resume-123"]
    assert fake_db.statements, "expected the jobs query to be captured"

    compiled_sql = str(
        fake_db.statements[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "jobs.source = 'greenhouse'" in compiled_sql
    assert "jobs.posted_date DESC NULLS LAST" in compiled_sql
    assert "jobs.fetched_at DESC NULLS LAST" in compiled_sql
    assert "jobs.id DESC" in compiled_sql
    assert "NULLS LAST" in compiled_sql


def test_jobs_sort_rejects_invalid_value(monkeypatch):
    from src.services.opportunity import job_intelligence_service as job_intel_module

    fake_service = _FakeJobsIntelligenceService()
    fake_db = _CaptureDB([
        _FakeResult(rows=[]),
        _FakeResult(scalar_value=0),
        _FakeResult(scalar_value=0),
        _FakeResult(rows=[]),
    ])

    monkeypatch.setattr(job_intel_module, "get_job_intelligence_service", lambda: fake_service)
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: fake_db

    response = client.get(
        "/api/v1/jobs",
        params={
            "resume_id": "resume-123",
            "sort": "not_a_sort",
        },
    )

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400
    assert "Invalid sort option" in response.text
