from __future__ import annotations

import asyncio
from datetime import datetime
from inspect import signature
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient

from src.api.deps import get_current_user
from src.api.v1.endpoints import events as events_endpoint
from src.db.session import get_db
from src.main import app
from src.services.events import career_event_service as career_event_service_mod
from src.services.events.career_event_service import CareerEventService


if "app" not in signature(httpx.Client.__init__).parameters:
    _httpx_client_init = httpx.Client.__init__

    def _patched_httpx_client_init(self, *args, app=None, **kwargs):
        return _httpx_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = _patched_httpx_client_init


client = TestClient(app)


class _FakeEventResult:
    def __init__(self, event=None):
        self._event = event

    def scalar_one_or_none(self):
        return self._event


class _FakeEventDB:
    def __init__(self, existing_event=None):
        self.existing_event = existing_event
        self.added = []
        self.executed = []
        self.committed = False
        self.refreshed = []

    async def execute(self, statement):
        self.executed.append(statement)
        return _FakeEventResult(self.existing_event)

    def add(self, event):
        self.added.append(event)

    async def flush(self):
        return None

    async def commit(self):
        self.committed = True

    async def refresh(self, event):
        self.refreshed.append(event)


class _FakeSessionContext:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _ForbiddenCallerDB:
    async def execute(self, *_args, **_kwargs):
        raise AssertionError("caller db should not be used by career event writes")

    def add(self, *_args, **_kwargs):
        raise AssertionError("caller db should not be used by career event writes")

    async def flush(self):
        raise AssertionError("caller db should not be used by career event writes")

    async def commit(self):
        raise AssertionError("caller db should not be used by career event writes")

    async def refresh(self, *_args, **_kwargs):
        raise AssertionError("caller db should not be used by career event writes")


def _override_user():
    return {"sub": "user-123", "role": "User"}


def _override_admin():
    return {"sub": "admin-123", "role": "Admin"}


def test_career_event_service_sanitizes_payload_and_uses_isolated_session(monkeypatch):
    service = CareerEventService()
    fake_db = _FakeEventDB()
    monkeypatch.setattr(
        career_event_service_mod,
        "async_session",
        lambda: _FakeSessionContext(fake_db),
    )

    event = asyncio.run(
        service.emit_event(
            _ForbiddenCallerDB(),
            event_type="CareerEventCreated",
            entity_type="career_event",
            source_service="tests",
            user_id="user-123",
            entity_id="entity-1",
            source_table="career_events",
            source_id=99,
            payload={
                "email": "candidate@example.com",
                "phone": "+1 (555) 123-4567",
                "token": "secret-token-value",
                "notes": "please call at candidate@example.com or +1 (555) 123-4567",
            },
            evidence=[
                {
                    "type": "db_record",
                    "table": "career_events",
                    "id": 99,
                    "extra": {"authorization": "Bearer secret-token-value"},
                }
            ],
            trace_id="trace-1",
            request_id="request-1",
            provider="tests",
        )
    )

    assert event is not None
    assert fake_db.added
    assert fake_db.committed is True
    assert fake_db.refreshed
    assert event.payload_json["email"] == "[REDACTED_EMAIL]"
    assert event.payload_json["phone"] == "[REDACTED_PHONE]"
    assert event.payload_json["token"] == "[REDACTED]"
    assert event.evidence_json[0]["extra"]["authorization"] == "[REDACTED]"


def test_career_event_service_reuses_existing_event_uid(monkeypatch):
    service = CareerEventService()
    existing = SimpleNamespace(event_uid="evt-123")
    fake_db = _FakeEventDB(existing_event=existing)
    monkeypatch.setattr(
        career_event_service_mod,
        "async_session",
        lambda: _FakeSessionContext(fake_db),
    )

    event = asyncio.run(
        service.emit_event(
            _ForbiddenCallerDB(),
            event_type="CareerEventCreated",
            entity_type="career_event",
            source_service="tests",
            event_uid="evt-123",
        )
    )

    assert event is existing
    assert fake_db.added == []


def test_events_routes_require_auth():
    response = client.get("/api/v1/events")
    assert response.status_code == 401


def test_events_routes_list_and_get(monkeypatch):
    event = SimpleNamespace(
        event_uid="evt-1",
        event_type="CareerEventCreated",
        user_id="user-123",
        entity_type="career_event",
        entity_id="entity-1",
        source_service="tests",
        source_table="career_events",
        source_id="99",
        event_time=datetime(2026, 6, 19, 12, 0, 0),
        payload_json={"message": "ok"},
        evidence_json=[{"type": "db_record"}],
        confidence="medium",
        trace_id="trace-1",
        request_id="request-1",
        provider="tests",
        status="success",
        schema_version="v1",
        created_at=datetime(2026, 6, 19, 12, 0, 0),
    )
    fake_service = SimpleNamespace(
        list_events=AsyncMock(return_value=([event], 1)),
        get_event_by_uid=AsyncMock(return_value=event),
    )
    monkeypatch.setattr(events_endpoint, "get_career_event_service", lambda: fake_service)

    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    try:
        response = client.get("/api/v1/events")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["total"] == 1
        assert body["events"][0]["event_uid"] == "evt-1"

        response = client.get("/api/v1/events/evt-1")
        assert response.status_code == 200
        assert response.json()["event_uid"] == "evt-1"

        response = client.get("/api/v1/events?user_id=other-user")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def test_events_routes_allow_admin_scoped_lookup(monkeypatch):
    event = SimpleNamespace(
        event_uid="evt-admin",
        event_type="CareerEventCreated",
        user_id="admin-lookup",
        entity_type="career_event",
        entity_id="entity-admin",
        source_service="tests",
        source_table="career_events",
        source_id="100",
        event_time=datetime(2026, 6, 19, 12, 0, 0),
        payload_json={"message": "ok"},
        evidence_json=[],
        confidence="medium",
        trace_id="trace-admin",
        request_id="request-admin",
        provider="tests",
        status="success",
        schema_version="v1",
        created_at=datetime(2026, 6, 19, 12, 0, 0),
    )
    fake_service = SimpleNamespace(
        list_events=AsyncMock(return_value=([event], 1)),
        get_event_by_uid=AsyncMock(return_value=event),
    )
    monkeypatch.setattr(events_endpoint, "get_career_event_service", lambda: fake_service)

    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = _override_admin
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    try:
        response = client.get("/api/v1/events?user_id=admin-lookup")
        assert response.status_code == 200
        assert response.json()["total"] == 1

        response = client.get("/api/v1/events/evt-admin?user_id=admin-lookup")
        assert response.status_code == 200
        assert response.json()["event_uid"] == "evt-admin"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
