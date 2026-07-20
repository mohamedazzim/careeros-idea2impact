from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager, ExitStack
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError


def _patched_classifiers():
    return (
        patch(
            "src.services.job_location_filter.classify_job_location",
            return_value=SimpleNamespace(
                is_india_eligible=True,
                location_country="IN",
                location_region="Karnataka",
                location_city="Bengaluru",
                is_remote=False,
                remote_region=None,
                exclusion_reason=None,
            ),
        ),
        patch(
            "src.services.job_role_filter.classify_tech_role",
            return_value={
                "is_tech_role": True,
                "tech_role_category": "backend",
                "confidence": 0.95,
                "reason": "keyword match",
            },
        ),
        patch(
            "src.services.job_role_filter.extract_job_experience_requirement",
            return_value={
                "min_years": 2.0,
                "max_years": 5.0,
                "seniority_level": "mid",
            },
        ),
    )


def _make_session(db):
    @asynccontextmanager
    async def _session():
        yield db

    return _session


@contextmanager
def _patched_greenhouse_env(db, fake_repo):
    with ExitStack() as stack:
        stack.enter_context(patch("src.db.session.async_session", return_value=_make_session(db)()))
        stack.enter_context(patch("src.db.repositories.domain_repositories.JobRepository", return_value=fake_repo))
        for classifier_patch in _patched_classifiers():
            stack.enter_context(classifier_patch)
        yield


class _FakeResult:
    def __init__(self, existing=None, rows=None):
        self._existing = existing
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._existing

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


@pytest.mark.asyncio
async def test_greenhouse_duplicate_rows_deduped_before_insert(monkeypatch):
    from src.services.jobs import JobIngestionEngine

    engine = JobIngestionEngine()
    db = SimpleNamespace()
    db.execute = AsyncMock(side_effect=[
        _FakeResult(None),
        _FakeResult(rows=[]),
    ])
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    fake_repo = SimpleNamespace(create=AsyncMock(), update=AsyncMock())

    jobs = [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Bengaluru, India",
            "description": "Python FastAPI SQL",
            "source_job_id": "123",
            "board_slug": "acme",
            "source_url": "https://boards.greenhouse.io/acme/jobs/123",
            "posted_date": datetime(2026, 6, 10),
            "skills_required": ["python", "fastapi"],
            "salary_range": "",
        },
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Bengaluru, India",
            "description": "Python FastAPI SQL",
            "source_job_id": "123",
            "board_slug": "acme",
            "source_url": "https://boards.greenhouse.io/acme/jobs/123",
            "posted_date": datetime(2026, 6, 10),
            "skills_required": ["python", "fastapi"],
            "salary_range": "",
        },
    ]

    with _patched_greenhouse_env(db, fake_repo):
        with patch.object(engine, "_fetch_source", new=AsyncMock(return_value=jobs)):
            found, added, updated, duplicates, expired, *rest = await engine._sync_source("greenhouse")

    assert found == 2
    assert added == 1
    assert updated == 0
    assert duplicates == 1
    assert expired == 0
    assert fake_repo.create.await_count == 1


@pytest.mark.asyncio
async def test_greenhouse_resync_updates_existing_job(monkeypatch):
    from src.services.jobs import JobIngestionEngine

    engine = JobIngestionEngine()
    jobs = [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Bengaluru, India",
            "description": "Python FastAPI SQL",
            "source_job_id": "123",
            "board_slug": "acme",
            "source_url": "https://boards.greenhouse.io/acme/jobs/123",
            "posted_date": datetime(2026, 6, 10),
            "skills_required": ["python", "fastapi"],
            "salary_range": "",
        }
    ]
    fake_repo = SimpleNamespace(create=AsyncMock(), update=AsyncMock())

    db_first = SimpleNamespace()
    db_first.execute = AsyncMock(side_effect=[_FakeResult(None), _FakeResult(rows=[])])
    db_first.commit = AsyncMock()
    db_first.rollback = AsyncMock()

    db_second = SimpleNamespace()
    db_second.execute = AsyncMock(side_effect=[_FakeResult(SimpleNamespace(id=42)), _FakeResult(rows=[])])
    db_second.commit = AsyncMock()
    db_second.rollback = AsyncMock()

    with _patched_greenhouse_env(db_first, fake_repo):
        with patch.object(engine, "_fetch_source", new=AsyncMock(return_value=jobs)):
            await engine._sync_source("greenhouse")

    with _patched_greenhouse_env(db_second, fake_repo):
        with patch.object(engine, "_fetch_source", new=AsyncMock(return_value=jobs)):
            found, added, updated, duplicates, expired, *rest = await engine._sync_source("greenhouse")

    assert found == 1
    assert added == 0
    assert updated == 1
    assert duplicates == 0
    assert expired == 0
    assert fake_repo.update.await_count >= 1


@pytest.mark.asyncio
async def test_greenhouse_duplicate_key_conflict_recovers_as_update():
    from src.services.jobs import JobIngestionEngine

    engine = JobIngestionEngine()
    jobs = [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Bengaluru, India",
            "description": "Python FastAPI SQL",
            "source_job_id": "123",
            "board_slug": "acme",
            "source_url": "https://boards.greenhouse.io/acme/jobs/123",
            "posted_date": datetime(2026, 6, 10),
            "skills_required": ["python", "fastapi"],
            "salary_range": "",
        }
    ]
    fake_repo = SimpleNamespace(
        create=AsyncMock(side_effect=IntegrityError("insert jobs", {}, Exception("duplicate key value violates unique constraint"))),
        update=AsyncMock(),
    )
    db = SimpleNamespace()
    db.execute = AsyncMock(side_effect=[
        _FakeResult(None),
        _FakeResult(SimpleNamespace(id=77)),
        _FakeResult(rows=[]),
    ])
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    with _patched_greenhouse_env(db, fake_repo):
        with patch.object(engine, "_fetch_source", new=AsyncMock(return_value=jobs)):
            found, added, updated, duplicates, expired, *rest = await engine._sync_source("greenhouse")

    assert found == 1
    assert added == 0
    assert updated == 1
    assert duplicates == 0
    assert expired == 0
    assert fake_repo.create.await_count == 1
    assert fake_repo.update.await_count == 1


@pytest.mark.asyncio
async def test_greenhouse_duplicate_count_reported():
    from src.services.jobs import JobIngestionEngine

    engine = JobIngestionEngine()
    jobs = [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Bengaluru, India",
            "description": "Python FastAPI SQL",
            "source_job_id": "123",
            "board_slug": "acme",
            "source_url": "https://boards.greenhouse.io/acme/jobs/123",
            "posted_date": datetime(2026, 6, 10),
            "skills_required": ["python", "fastapi"],
            "salary_range": "",
        },
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Bengaluru, India",
            "description": "Python FastAPI SQL",
            "source_job_id": "123",
            "board_slug": "acme",
            "source_url": "https://boards.greenhouse.io/acme/jobs/123",
            "posted_date": datetime(2026, 6, 10),
            "skills_required": ["python", "fastapi"],
            "salary_range": "",
        },
        {
            "title": "Platform Engineer",
            "company": "Acme",
            "location": "Bengaluru, India",
            "description": "Python FastAPI SQL",
            "source_job_id": "456",
            "board_slug": "acme",
            "source_url": "https://boards.greenhouse.io/acme/jobs/456",
            "posted_date": datetime(2026, 6, 10),
            "skills_required": ["python", "fastapi"],
            "salary_range": "",
        },
    ]
    db = SimpleNamespace()
    db.execute = AsyncMock(side_effect=[_FakeResult(None), _FakeResult(None), _FakeResult(rows=[])])
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    fake_repo = SimpleNamespace(create=AsyncMock(), update=AsyncMock())

    with _patched_greenhouse_env(db, fake_repo):
        with patch.object(engine, "_fetch_source", new=AsyncMock(return_value=jobs)):
            found, added, updated, duplicates, expired, *rest = await engine._sync_source("greenhouse")

    assert found == 3
    assert duplicates == 1
    assert added == 2
    assert updated == 0
    assert expired == 0


@pytest.mark.asyncio
async def test_greenhouse_duplicate_does_not_fail_provider_sync():
    from src.services.jobs import JobIngestionEngine

    engine = JobIngestionEngine()
    jobs = [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Bengaluru, India",
            "description": "Python FastAPI SQL",
            "source_job_id": "123",
            "board_slug": "acme",
            "source_url": "https://boards.greenhouse.io/acme/jobs/123",
            "posted_date": datetime(2026, 6, 10),
            "skills_required": ["python", "fastapi"],
            "salary_range": "",
        }
    ]
    db = SimpleNamespace()
    db.execute = AsyncMock(side_effect=[_FakeResult(None), _FakeResult(SimpleNamespace(id=77)), _FakeResult(rows=[])])
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    fake_repo = SimpleNamespace(create=AsyncMock(), update=AsyncMock())

    with _patched_greenhouse_env(db, fake_repo):
        with patch.object(engine, "_fetch_source", new=AsyncMock(return_value=jobs)):
            found, added, updated, duplicates, expired, *rest = await engine._sync_source("greenhouse")

    assert found == 1
    assert added == 1
    assert updated == 0
    assert duplicates == 0
    assert expired == 0


@pytest.mark.asyncio
async def test_greenhouse_real_db_errors_still_raise_or_report_error():
    from src.services.jobs import JobIngestionEngine

    engine = JobIngestionEngine()
    jobs = [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Bengaluru, India",
            "description": "Python FastAPI SQL",
            "source_job_id": "123",
            "board_slug": "acme",
            "source_url": "https://boards.greenhouse.io/acme/jobs/123",
            "posted_date": datetime(2026, 6, 10),
            "skills_required": ["python", "fastapi"],
            "salary_range": "",
        }
    ]
    db = SimpleNamespace()
    db.execute = AsyncMock(side_effect=[_FakeResult(None), _FakeResult(SimpleNamespace(id=77)), _FakeResult(rows=[])])
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    fake_repo = SimpleNamespace(
        create=AsyncMock(side_effect=IntegrityError("insert jobs", {}, Exception("duplicate key value violates unique constraint"))),
        update=AsyncMock(side_effect=RuntimeError("db unavailable")),
    )

    with _patched_greenhouse_env(db, fake_repo):
        with patch.object(engine, "_fetch_source", new=AsyncMock(return_value=jobs)):
            with pytest.raises(RuntimeError):
                await engine._sync_source("greenhouse")


@pytest.mark.asyncio
async def test_other_providers_continue_after_greenhouse_duplicates():
    from src.services.jobs import JobIngestionEngine

    engine = JobIngestionEngine()
    call_order: list[str] = []

    async def fake_sync_source(source: str, stage_callback=None):
        call_order.append(source)
        if source == "greenhouse":
            return 10, 0, 0, 1, 0, {}, []
        return 5, 1, 0, 0, 0, {}, []

    fake_theirstack = SimpleNamespace(
        search_from_resume=AsyncMock(return_value={"configured": False, "found": 0, "jobs": []}),
        upsert_jobs=AsyncMock(return_value=(0, 0, 0)),
    )
    fake_redis = SimpleNamespace(
        set=AsyncMock(return_value=True),
        get=AsyncMock(return_value="lease-1"),
        delete=AsyncMock(return_value=1),
    )

    with patch.object(engine, "_sync_source", side_effect=fake_sync_source), \
         patch("src.db.redis.redis_client", fake_redis), \
         patch("src.integrations.theirstack.sync_service.TheirStackSyncService", return_value=fake_theirstack):
        result = await engine.sync_jobs()

    assert call_order == ["remoteok", "arbeitnow", "adzuna", "usajobs", "greenhouse", "lever"]
    assert result["duplicates_removed"] == 1
    assert result["added"] == 5


@pytest.mark.asyncio
async def test_automatic_job_refresh_skips_theirstack_paid_provider():
    from src.services.jobs import JobIngestionEngine

    engine = JobIngestionEngine()
    call_order: list[str] = []

    async def fake_sync_source(source: str, stage_callback=None):
        call_order.append(source)
        return 2, 1, 0, 0, 0, {}, []

    fake_redis = SimpleNamespace(
        set=AsyncMock(return_value=True),
        get=AsyncMock(return_value="lease-1"),
        delete=AsyncMock(return_value=1),
    )

    with patch.object(engine, "_sync_source", side_effect=fake_sync_source), \
         patch.object(engine, "embed_jobs_batch", new=AsyncMock(return_value={"embedded": 0})), \
         patch("src.db.redis.redis_client", fake_redis), \
         patch("src.integrations.theirstack.sync_service.TheirStackSyncService", side_effect=AssertionError("TheirStack must not run automatically")):
        result = await engine.sync_jobs(admin_initiated=False)

    assert call_order == ["remoteok", "arbeitnow", "adzuna", "usajobs", "greenhouse", "lever"]
    assert result["theirstack"]["provider_health"]["status"] == "skipped"
    assert result["theirstack"]["provider_health"]["provider_http_call_count"] == 0
    assert result["found"] == 12
    assert result["added"] == 6


@pytest.mark.asyncio
async def test_legacy_ingestion_pipeline_does_not_use_paid_theirstack_mode():
    from src.workers.tasks.job_ingestion import jobs_ingestion_pipeline

    fake_engine = SimpleNamespace(
        sync_jobs=AsyncMock(return_value={"found": 0, "added": 0, "errors": 0})
    )

    with patch("src.services.jobs.get_job_ingestion_engine", return_value=fake_engine):
        result = await jobs_ingestion_pipeline({"job_id": "unit-test"})

    fake_engine.sync_jobs.assert_awaited_once_with(admin_initiated=False)
    assert result["added"] == 0


@pytest.mark.asyncio
async def test_opportunity_discovery_does_not_use_paid_theirstack_mode():
    from fastapi import HTTPException
    from src.api.v1.endpoints.opportunities_api import DiscoverRequest, discover_opportunities

    fake_engine = SimpleNamespace(sync_jobs=AsyncMock(return_value={"found": 0, "added": 0}))
    fake_intelligence = SimpleNamespace(get_active_resume=AsyncMock(return_value=None))

    with patch("src.services.jobs.get_job_ingestion_engine", return_value=fake_engine), \
         patch("src.services.opportunity.job_intelligence_service.get_job_intelligence_service", return_value=fake_intelligence):
        with pytest.raises(HTTPException):
            await discover_opportunities(
                DiscoverRequest(),
                user={"sub": "user-1"},
                db=MagicMock(),
            )

    fake_engine.sync_jobs.assert_awaited_once_with(admin_initiated=False)
