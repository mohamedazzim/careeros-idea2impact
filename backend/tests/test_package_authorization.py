"""Regression tests for package ownership enforcement."""

import asyncio
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.api.deps import get_current_user
from src.db.session import get_db
from src.main import app


client = TestClient(app)


async def _override_db():
    yield SimpleNamespace()


async def _override_user():
    return {"sub": "user-1", "role": "User"}


def _package(user_id: str = "user-1"):
    return SimpleNamespace(
        id=42,
        package_uid="pkg-1",
        user_id=user_id,
        job_id=1,
        title="Fictional AI Engineer",
        status="ready",
        resume_tailored=json.dumps({"summary": ["Safe demo resume"], "skills": {}}),
        cover_letter=json.dumps({"subject": "Demo", "body": "Safe demo cover letter"}),
        outreach_message=json.dumps({"linkedin_message": "Demo", "email_message": "Demo"}),
        interview_guide=json.dumps({"likely_questions": ["Demo question"]}),
        readiness_summary="Ready",
        metadata_={},
        created_at=None,
        updated_at=None,
    )


class _FakeJobRepository:
    def __init__(self, db):
        pass

    async def get_by_id(self, job_id):
        return SimpleNamespace(id=job_id, title="Fictional AI Engineer")


def _with_overrides(user_override=_override_user):
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = _override_db
    if user_override is not None:
        app.dependency_overrides[get_current_user] = user_override
    return original_overrides


def _restore_overrides(original_overrides):
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


def _install_repo(monkeypatch, *, package=None, calls=None, updates=None, deletes=None):
    from src.api.v1.endpoints import packages

    calls = calls if calls is not None else []
    updates = updates if updates is not None else []
    deletes = deletes if deletes is not None else []

    class FakePackageRepository:
        def __init__(self, db):
            pass

        async def get_by_uid_for_user(self, package_uid, user_id):
            calls.append((package_uid, user_id))
            return package

        async def get_by_uid(self, package_uid):
            raise AssertionError("package lookup must be scoped to the current user")

        async def update(self, package_id, **kwargs):
            updates.append((package_id, kwargs))
            return package

        async def soft_delete(self, package_id):
            deletes.append(package_id)
            return True

    monkeypatch.setattr(packages, "PackageRepository", FakePackageRepository)
    monkeypatch.setattr(packages, "JobRepository", _FakeJobRepository)
    return calls, updates, deletes


def _stub_generation_task(monkeypatch):
    from src.api.v1.endpoints import packages

    scheduled = []

    async def fake_run(*args):
        return None

    def fake_create_task(coro):
        scheduled.append(coro)
        if hasattr(coro, "close"):
            coro.close()
        return SimpleNamespace(done=lambda: False)

    monkeypatch.setattr(packages, "_run_structured_generation", fake_run)
    monkeypatch.setattr(packages.asyncio, "create_task", fake_create_task)
    return scheduled


def test_package_item_routes_require_auth():
    original_overrides = _with_overrides(user_override=None)
    try:
        checks = [
            client.get("/api/v1/packages/pkg-1"),
            client.get("/api/v1/packages/pkg-1/download"),
            client.post("/api/v1/packages/pkg-1/regenerate"),
            client.delete("/api/v1/packages/pkg-1"),
        ]
        assert [response.status_code for response in checks] == [401, 401, 401, 401]
    finally:
        _restore_overrides(original_overrides)


def test_package_item_routes_hide_wrong_owner(monkeypatch):
    calls, _, _ = _install_repo(monkeypatch, package=None)
    original_overrides = _with_overrides()
    try:
        checks = [
            client.get("/api/v1/packages/pkg-1"),
            client.get("/api/v1/packages/pkg-1/download"),
            client.post("/api/v1/packages/pkg-1/regenerate"),
            client.delete("/api/v1/packages/pkg-1"),
        ]
        assert [response.status_code for response in checks] == [404, 404, 404, 404]
        assert calls == [("pkg-1", "user-1")] * 4
    finally:
        _restore_overrides(original_overrides)


def test_package_owner_detail_succeeds_and_uses_scoped_lookup(monkeypatch):
    calls, _, _ = _install_repo(monkeypatch, package=_package())
    original_overrides = _with_overrides()
    try:
        response = client.get("/api/v1/packages/pkg-1")
        assert response.status_code == 200
        assert response.json()["id"] == "pkg-1"
        assert calls == [("pkg-1", "user-1")]
    finally:
        _restore_overrides(original_overrides)


def test_package_owner_download_resume_and_cover_letter(monkeypatch):
    calls, _, _ = _install_repo(monkeypatch, package=_package())
    original_overrides = _with_overrides()
    try:
        resume_response = client.get("/api/v1/packages/pkg-1/download?asset=resume")
        cover_response = client.get("/api/v1/packages/pkg-1/download?asset=cover_letter")

        assert resume_response.status_code == 200
        assert "Safe demo resume" in resume_response.json()["content"]
        assert cover_response.status_code == 200
        assert "Safe demo cover letter" in cover_response.json()["content"]
        assert calls == [("pkg-1", "user-1"), ("pkg-1", "user-1")]
    finally:
        _restore_overrides(original_overrides)


def test_package_download_rejects_invalid_asset_and_format(monkeypatch):
    _install_repo(monkeypatch, package=_package())
    original_overrides = _with_overrides()
    try:
        invalid_asset = client.get("/api/v1/packages/pkg-1/download?asset=../../etc/passwd")
        invalid_format = client.get("/api/v1/packages/pkg-1/download?format=zip")

        assert invalid_asset.status_code == 400
        assert invalid_format.status_code == 400
    finally:
        _restore_overrides(original_overrides)


def test_package_owner_regenerate_schedules_scoped_generation(monkeypatch):
    pkg = _package()
    calls, updates, _ = _install_repo(monkeypatch, package=pkg)
    scheduled = _stub_generation_task(monkeypatch)
    original_overrides = _with_overrides()
    try:
        response = client.post("/api/v1/packages/pkg-1/regenerate")
        assert response.status_code == 200
        assert response.json()["status"] == "regenerating"
        assert calls == [("pkg-1", "user-1")]
        assert updates == [(pkg.id, {"status": "regenerating", "updated_by": "user-1"})]
        assert len(scheduled) == 1
    finally:
        _restore_overrides(original_overrides)


def test_package_owner_delete_reaches_soft_delete(monkeypatch):
    pkg = _package()
    calls, _, deletes = _install_repo(monkeypatch, package=pkg)
    original_overrides = _with_overrides()
    try:
        response = client.delete("/api/v1/packages/pkg-1")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        assert calls == [("pkg-1", "user-1")]
        assert deletes == [pkg.id]
    finally:
        _restore_overrides(original_overrides)


def test_background_generation_refuses_unowned_package(monkeypatch):
    from src.api.v1.endpoints import packages
    import src.db.repositories.package_repository as package_repository_module
    import src.db.session as session_module

    calls = []

    class FakeSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return SimpleNamespace()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePackageRepository:
        def __init__(self, db):
            pass

        async def get_by_uid_for_user(self, package_uid, user_id):
            calls.append((package_uid, user_id))
            return None

        async def get_by_uid(self, package_uid):
            raise AssertionError("background generation must use owner-scoped lookup")

        async def update(self, package_id, **kwargs):
            raise AssertionError("unowned package must not be modified")

    async def fail_generation(**kwargs):
        raise AssertionError("generation should not start for unowned package")

    monkeypatch.setattr(session_module, "async_session", FakeSessionFactory())
    monkeypatch.setattr(packages, "PackageRepository", FakePackageRepository)
    monkeypatch.setattr(package_repository_module, "PackageRepository", FakePackageRepository)
    monkeypatch.setattr(packages, "_generate_with_llm_or_fallback", fail_generation)

    asyncio.run(packages._run_structured_generation("pkg-1", "user-1", "job-1", 1))
    assert calls == [("pkg-1", "user-1")]


def test_background_generation_exception_handler_uses_scoped_lookup(monkeypatch):
    from src.api.v1.endpoints import packages
    import src.db.repositories.package_repository as package_repository_module
    import src.db.session as session_module

    pkg = _package()
    calls = []
    updates = []

    class FakeSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return SimpleNamespace()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePackageRepository:
        def __init__(self, db):
            pass

        async def get_by_uid_for_user(self, package_uid, user_id):
            calls.append((package_uid, user_id))
            return pkg if len(calls) == 1 else None

        async def get_by_uid(self, package_uid):
            raise AssertionError("exception handler must use owner-scoped lookup")

        async def update(self, package_id, **kwargs):
            updates.append((package_id, kwargs))

    class FailingJobRepository:
        def __init__(self, db):
            pass

        async def get_by_id(self, job_id):
            raise RuntimeError("synthetic job failure")

    monkeypatch.setattr(session_module, "async_session", FakeSessionFactory())
    monkeypatch.setattr(packages, "PackageRepository", FakePackageRepository)
    monkeypatch.setattr(package_repository_module, "PackageRepository", FakePackageRepository)
    monkeypatch.setattr(packages, "JobRepository", FailingJobRepository)

    asyncio.run(packages._run_structured_generation("pkg-1", "user-1", "job-1", 1))
    assert calls == [("pkg-1", "user-1"), ("pkg-1", "user-1")]
    assert updates == []
