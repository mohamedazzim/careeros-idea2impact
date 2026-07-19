"""Regression tests for package ownership enforcement."""

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


def test_package_detail_requires_auth():
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = _override_db
    try:
        response = client.get("/api/v1/packages/pkg-1")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def test_package_download_requires_auth():
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = _override_db
    try:
        response = client.get("/api/v1/packages/pkg-1/download")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def test_package_detail_uses_owner_scoped_lookup(monkeypatch):
    from src.api.v1.endpoints import packages

    calls = []

    class FakePackageRepository:
        def __init__(self, db):
            pass

        async def get_by_uid_for_user(self, package_uid, user_id):
            calls.append((package_uid, user_id))
            return None

    monkeypatch.setattr(packages, "PackageRepository", FakePackageRepository)
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    try:
        response = client.get("/api/v1/packages/pkg-1")
        assert response.status_code == 404
        assert calls == [("pkg-1", "user-1")]
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def test_package_download_uses_owner_scoped_lookup(monkeypatch):
    from src.api.v1.endpoints import packages

    calls = []

    class FakePackageRepository:
        def __init__(self, db):
            pass

        async def get_by_uid_for_user(self, package_uid, user_id):
            calls.append((package_uid, user_id))
            return _package()

    monkeypatch.setattr(packages, "PackageRepository", FakePackageRepository)
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    try:
        response = client.get("/api/v1/packages/pkg-1/download")
        assert response.status_code == 200
        assert calls == [("pkg-1", "user-1")]
        assert response.json()["content"]
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
