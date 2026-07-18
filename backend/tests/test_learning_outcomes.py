from datetime import datetime, timezone
from inspect import signature
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_current_user
from src.api.v1.endpoints import learning as learning_endpoint
from src.db.session import get_db
from src.main import app
from src.schemas.security import Role
from src.services.learning.learning_outcome_service import LearningOutcomeService
from src.services.security.auth import auth_service


if "app" not in signature(httpx.Client.__init__).parameters:
    _httpx_client_init = httpx.Client.__init__

    def _patched_httpx_client_init(self, *args, app=None, **kwargs):
        return _httpx_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = _patched_httpx_client_init


client = TestClient(app)


async def _override_db():
    yield SimpleNamespace()


def _user_auth_headers(user_id: str = "user-123") -> dict[str, str]:
    token = auth_service.generate_token_pair(user_id, Role.USER).access_token
    return {"Authorization": f"Bearer {token}"}


def _session_payload(session_uid: str, status: str = "in_progress", completion_percentage: float = 25.0) -> dict[str, object]:
    return {
        "session_uid": session_uid,
        "user_id": "user-123",
        "resource_id": 42,
        "provenance_uid": "prov-42",
        "path_id": 9,
        "path_item_id": 3,
        "skill_slug": "aws",
        "job_id": 7,
        "status": status,
        "source_ui": "learning_panel",
        "external_resource_url": "https://aws.amazon.com/training/",
        "started_at": "2026-06-19T00:00:00Z",
        "last_activity_at": "2026-06-19T00:10:00Z",
        "ended_at": None if status not in {"completed", "abandoned"} else "2026-06-19T00:20:00Z",
        "duration_seconds": 1200 if status in {"completed", "abandoned"} else None,
        "completion_percentage": completion_percentage,
        "metadata_json": {"source_ui": "learning_panel"},
        "created_at": "2026-06-19T00:00:00Z",
        "updated_at": "2026-06-19T00:10:00Z",
    }


def _outcome_payload(status: str = "sufficient_data") -> dict[str, object]:
    return {
        "resource_id": 42,
        "provenance_uid": "prov-42",
        "skill_slug": "aws",
        "source_type": "official_docs",
        "provider": "AWS",
        "completion_count": 2,
        "started_count": 3,
        "feedback_count": 1,
        "average_rating": 4.5,
        "completion_rate": 0.6667,
        "drop_off_rate": 0.0,
        "recommendation_rate": 1.0,
        "average_completion_percentage": 82.0,
        "average_duration_seconds": 900.0,
        "last_calculated_at": "2026-06-19T00:15:00Z",
        "status": status,
        "calculation_metadata_json": {
            "session_count": 3,
            "completed_session_count": 2,
            "abandoned_session_count": 0,
            "recommend_count": 1,
            "resource_title": "AWS Tutorials",
        },
        "explanation": "AWS Tutorials has 3 started session(s), 2 completion(s), 1 feedback entry(ies), and Average rating 4.5/5.",
        "created_at": "2026-06-19T00:15:00Z",
        "updated_at": "2026-06-19T00:15:00Z",
    }


def _activity_payload(event_type: str = "ResourceOpened") -> dict[str, object]:
    return {
        "activity_uid": "activity-42",
        "user_id": "user-123",
        "event_type": event_type,
        "resource_id": 42,
        "provenance_uid": "prov-42",
        "session_uid": "session-42",
        "path_id": 9,
        "path_item_id": 3,
        "skill_slug": "aws",
        "job_id": 7,
        "payload_json": {"source_ui": "learning_panel"},
        "event_time": "2026-06-19T00:10:00Z",
        "created_at": "2026-06-19T00:10:00Z",
    }


class _FakeLearningOutcomeService:
    def __init__(self) -> None:
        self.last_feedback_session_uid: str | None = None
        self.last_progress_request: dict[str, object] | None = None

    async def open_resource(self, db, **kwargs):
        assert kwargs["resource_id"] == 42
        return {
            "status": "ok",
            "session": _session_payload("session-opened", status="opened", completion_percentage=0.0),
            "outcome": _outcome_payload(status="insufficient_data"),
            "event": _activity_payload("ResourceOpened"),
            "message": "Resource opened.",
            "insufficient_data": True,
        }

    async def start_session(self, db, **kwargs):
        assert kwargs["resource_id"] == 42
        return {
            "status": "ok",
            "session": _session_payload("session-started", status="in_progress", completion_percentage=10.0),
            "outcome": _outcome_payload(status="insufficient_data"),
            "event": _activity_payload("ResourceStarted"),
            "message": "Session started.",
            "insufficient_data": True,
        }

    async def update_progress(self, db, **kwargs):
        self.last_progress_request = kwargs
        return {
            "status": "ok",
            "session": _session_payload(kwargs["session_uid"], status="in_progress", completion_percentage=float(kwargs["completion_percentage"])),
            "outcome": _outcome_payload(status="sufficient_data"),
            "event": _activity_payload("ResourceProgressUpdated"),
            "message": "Progress recorded.",
            "insufficient_data": False,
        }

    async def complete_resource(self, db, **kwargs):
        return {
            "status": "ok",
            "session": _session_payload(kwargs["session_uid"], status="completed", completion_percentage=100.0),
            "outcome": _outcome_payload(status="sufficient_data"),
            "event": _activity_payload("ResourceCompleted"),
            "message": "Resource completed.",
            "insufficient_data": False,
        }

    async def abandon_resource(self, db, **kwargs):
        return {
            "status": "ok",
            "session": _session_payload(kwargs["session_uid"], status="abandoned", completion_percentage=45.0),
            "outcome": _outcome_payload(status="insufficient_data"),
            "event": _activity_payload("ResourceAbandoned"),
            "message": "Resource abandoned.",
            "insufficient_data": True,
        }

    async def submit_feedback(self, db, **kwargs):
        self.last_feedback_session_uid = kwargs.get("session_uid")
        return {
            "status": "ok",
            "feedback": {
                "feedback_uid": "feedback-42",
                "user_id": "user-123",
                "resource_id": 42,
                "provenance_uid": "prov-42",
                "session_uid": kwargs.get("session_uid"),
                "skill_slug": "aws",
                "rating": 5.0,
                "difficulty": "beginner",
                "would_recommend": True,
                "comment": "Great resource.",
                "helpfulness_score": 4.0,
                "outcome_tag": "helpful",
                "metadata_json": {"source_ui": "learning_panel"},
                "created_at": "2026-06-19T00:20:00Z",
                "updated_at": "2026-06-19T00:20:00Z",
            },
            "outcome": _outcome_payload(status="sufficient_data"),
            "event": _activity_payload("ResourceFeedbackSubmitted"),
            "message": "Feedback recorded.",
            "insufficient_data": False,
        }

    async def get_resource_outcome(self, db, **kwargs):
        return {
            "status": "ok",
            "outcome": _outcome_payload(status="sufficient_data"),
            "insufficient_data": False,
            "message": "Learning outcome loaded.",
        }

    async def list_resource_outcomes(self, db, **kwargs):
        return [_outcome_payload(status="sufficient_data")], 1

    async def list_user_learning_activity(self, db, **kwargs):
        return [_activity_payload("ResourceOpened")], 1


@pytest.fixture
def authenticated_learning_outcomes(monkeypatch):
    original_overrides = dict(app.dependency_overrides)

    async def _override_user():
        return {"sub": "user-123", "role": "User"}

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    fake_service = _FakeLearningOutcomeService()
    monkeypatch.setattr(learning_endpoint, "get_learning_outcome_service", lambda: fake_service)

    yield fake_service

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


def test_learning_outcome_routes_require_auth():
    response = client.post("/api/v1/learning/resources/42/open")
    assert response.status_code == 401
    assert client.get("/api/v1/learning/activity").status_code == 401


def test_learning_outcome_routes_return_tracking_payloads(authenticated_learning_outcomes):
    response = client.post("/api/v1/learning/resources/42/open", json={"source_ui": "learning_panel"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["session"]["session_uid"] == "session-opened"
    assert payload["outcome"]["status"] == "insufficient_data"

    response = client.post("/api/v1/learning/resources/42/start", json={"source_ui": "learning_panel"})
    assert response.status_code == 200
    assert response.json()["session"]["status"] == "in_progress"

    response = client.patch("/api/v1/learning/sessions/session-started/progress", json={"completion_percentage": 55, "notes": "halfway"})
    assert response.status_code == 200
    assert authenticated_learning_outcomes.last_progress_request["completion_percentage"] == 55
    assert response.json()["session"]["completion_percentage"] == 55

    response = client.post("/api/v1/learning/sessions/session-started/complete", json={"notes": "done"})
    assert response.status_code == 200
    assert response.json()["session"]["status"] == "completed"

    response = client.post("/api/v1/learning/sessions/session-started/abandon", json={"reason": "time"})
    assert response.status_code == 200
    assert response.json()["session"]["status"] == "abandoned"

    response = client.post(
        "/api/v1/learning/resources/42/feedback",
        json={
            "session_uid": "session-started",
            "rating": 5,
            "helpfulness_score": 4,
            "would_recommend": True,
            "comment": "Great resource",
        },
    )
    assert response.status_code == 200
    assert response.json()["feedback"]["feedback_uid"] == "feedback-42"
    assert authenticated_learning_outcomes.last_feedback_session_uid == "session-started"

    response = client.get("/api/v1/learning/resources/42/outcome")
    assert response.status_code == 200
    assert response.json()["outcome"]["status"] == "sufficient_data"

    response = client.get("/api/v1/learning/provenance/prov-42/outcome")
    assert response.status_code == 200
    assert response.json()["outcome"]["skill_slug"] == "aws"

    response = client.get("/api/v1/learning/outcomes")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["outcomes"][0]["resource_id"] == 42

    response = client.get("/api/v1/learning/activity")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["events"][0]["event_type"] == "ResourceOpened"


@pytest.mark.asyncio
async def test_learning_outcome_service_builds_honest_explanations():
    service = LearningOutcomeService()
    summary = service.build_outcome_explanation(
        resource_title="AWS Tutorials",
        started_count=0,
        completion_count=0,
        feedback_count=0,
        average_rating=None,
        status="insufficient_data",
    )
    assert "Not enough learning activity" in summary

    class _FakeOutcomeResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    outcome = SimpleNamespace(
        resource_id=42,
        provenance_uid="prov-42",
        skill_slug="aws",
        source_type="official_docs",
        provider="AWS",
        completion_count=2,
        started_count=3,
        feedback_count=1,
        average_rating=4.5,
        completion_rate=0.6667,
        drop_off_rate=0.0,
        recommendation_rate=1.0,
        average_completion_percentage=82.0,
        average_duration_seconds=900.0,
        last_calculated_at=datetime(2026, 6, 19, tzinfo=timezone.utc),
        status="sufficient_data",
        calculation_metadata_json={"resource_title": "AWS Tutorials"},
        created_at=datetime(2026, 6, 19, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 19, tzinfo=timezone.utc),
        id=1,
    )

    class _FakeOutcomeDB:
        def __init__(self):
            self.calls = 0

        async def execute(self, statement):
            self.calls += 1
            return _FakeOutcomeResult(outcome if self.calls == 1 else "AWS Tutorials")

    payload = await service.get_latest_resource_outcome_summary(_FakeOutcomeDB(), resource_id=42)

    assert payload is not None
    assert payload["status"] == "sufficient_data"
    assert "AWS Tutorials" in payload["explanation"]
    assert payload["started_count"] == 3
