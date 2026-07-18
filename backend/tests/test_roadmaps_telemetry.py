"""Regression tests for roadmap progress telemetry labeling."""

from datetime import datetime, timedelta
from inspect import signature
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_current_user_id
from src.db.session import get_db
from src.db.repositories import domain_repositories
from src.main import app


if "app" not in signature(httpx.Client.__init__).parameters:
    _httpx_client_init = httpx.Client.__init__

    def _patched_httpx_client_init(self, *args, app=None, **kwargs):
        return _httpx_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = _patched_httpx_client_init


client = TestClient(app)


async def _override_db():
    yield SimpleNamespace()


class _QueuedResult:
    def __init__(self, scalar_value=None, rows=None):
        self._scalar_value = scalar_value
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar_value

    def all(self):
        return self._rows


class _FakeRoadmapDB:
    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _statement):
        if not self._results:
            raise AssertionError("Unexpected execute call in test fixture")
        return self._results.pop(0)

    def add(self, _instance):
        return None

    async def commit(self):
        return None

    async def refresh(self, _instance):
        return None


@pytest.fixture(autouse=True)
def _roadmap_dependency_overrides():
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user_id] = lambda: "user-123"
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user_id, None)


def _fake_progress_repos(monkeypatch, roadmap, goal, tasks):
    monkeypatch.setattr(
        domain_repositories.RoadmapRepository,
        "find_by_user",
        AsyncMock(return_value=[roadmap]),
    )
    monkeypatch.setattr(
        domain_repositories.RoadmapGoalRepository,
        "find_by_roadmap",
        AsyncMock(return_value=[goal]),
    )
    monkeypatch.setattr(
        domain_repositories.RoadmapTaskRepository,
        "find_by_goal",
        AsyncMock(return_value=tasks),
    )


def _fake_generate_dependencies(monkeypatch, db_results, provider):
    app.dependency_overrides[get_db] = lambda: _FakeRoadmapDB(db_results)
    monkeypatch.setattr(
        "src.services.llm.factory.get_reasoning_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        domain_repositories.PreferencesRepository,
        "get_by_user",
        AsyncMock(
            return_value=SimpleNamespace(
                extra={
                    "target_role": "AI Engineer",
                    "target_salary": "$180,000/yr",
                    "target_location": "San Francisco, CA",
                    "timeline_months": 12,
                }
            )
        ),
    )


class _FailingProvider:
    async def structured_generate(self, **_kwargs):
        raise RuntimeError("provider unavailable")


class _PlanProvider:
    def __init__(self, payload):
        self.payload = payload

    async def structured_generate(self, **_kwargs):
        return self.payload


def test_progress_endpoint_marks_telemetry_as_not_tracked(monkeypatch):
    fake_roadmap = SimpleNamespace(
        id=1,
        roadmap_uid="roadmap-1",
        updated_at=datetime.utcnow(),
        recommendations=[{"type": "strategy", "text": "Focus on core milestones"}],
        velocity_history=[{"week": 1, "progress": 10}],
        trace_id="trace-1",
    )
    fake_goal = SimpleNamespace(id=10)
    fake_tasks = [
        SimpleNamespace(id=1, completed=True),
        SimpleNamespace(id=2, completed=False),
    ]

    _fake_progress_repos(monkeypatch, fake_roadmap, fake_goal, fake_tasks)

    response = client.get("/api/v1/roadmaps/progress")

    assert response.status_code == 200
    data = response.json()
    assert data["progress_source"] == "stored_task_completion"
    assert data["telemetry_status"] == "not_tracked"
    assert data["analytics_confidence"] is None
    assert data["metrics_available"] is False
    assert data["completion_percentage"] == 50.0
    assert data["recommendation_acceptance"] == 1.0
    assert data["observability"]["status"] == "not_tracked"
    assert data["observability"]["averageGenerationTimeMs"] is None
    assert data["observability"]["averageRefreshTimeMs"] is None
    assert data["observability"]["totalGenerations"] is None
    assert data["observability"]["totalRefreshes"] is None
    assert data["diagnostics"]["status"] == "partial"
    assert data["diagnostics"]["roadmaps"][0]["status"] == "fresh"
    assert data["diagnostics"]["roadmaps"][0]["evidence_status"] == "partial"


def test_missing_timing_telemetry_is_null_not_zero(monkeypatch):
    fake_roadmap = SimpleNamespace(
        id=1,
        roadmap_uid="roadmap-1",
        updated_at=datetime.utcnow(),
        recommendations=[],
        velocity_history=[],
        trace_id="trace-1",
    )
    fake_goal = SimpleNamespace(id=10)
    fake_tasks = [SimpleNamespace(id=1, completed=False)]

    _fake_progress_repos(monkeypatch, fake_roadmap, fake_goal, fake_tasks)

    data = client.get("/api/v1/roadmaps/progress").json()

    assert data["telemetry_status"] == "not_tracked"
    assert data["analytics_confidence"] is None
    assert data["metrics_available"] is False
    assert data["observability"]["averageGenerationTimeMs"] is None
    assert data["observability"]["averageRefreshTimeMs"] is None
    assert data["observability"]["totalGenerations"] is None
    assert data["observability"]["totalRefreshes"] is None


def test_stale_roadmap_is_marked_stale(monkeypatch):
    fake_roadmap = SimpleNamespace(
        id=1,
        roadmap_uid="roadmap-stale",
        updated_at=datetime.utcnow() - timedelta(days=45),
        recommendations=[],
        velocity_history=[],
        trace_id="trace-stale",
    )
    fake_goal = SimpleNamespace(id=10)
    fake_tasks = [SimpleNamespace(id=1, completed=False)]

    _fake_progress_repos(monkeypatch, fake_roadmap, fake_goal, fake_tasks)

    data = client.get("/api/v1/roadmaps/progress").json()

    assert data["diagnostics"]["status"] == "stale"
    assert data["diagnostics"]["roadmaps"][0]["status"] == "stale"


def test_partial_roadmap_evidence_marked_partial(monkeypatch):
    fake_roadmap = SimpleNamespace(
        id=1,
        roadmap_uid="roadmap-partial",
        updated_at=datetime.utcnow(),
        recommendations=[],
        velocity_history=[],
        trace_id="trace-partial",
    )
    fake_goal = SimpleNamespace(id=10)
    fake_tasks = [
        SimpleNamespace(id=1, completed=True),
        SimpleNamespace(id=2, completed=False),
        SimpleNamespace(id=3, completed=False),
    ]

    _fake_progress_repos(monkeypatch, fake_roadmap, fake_goal, fake_tasks)

    data = client.get("/api/v1/roadmaps/progress").json()

    assert data["diagnostics"]["status"] == "partial"
    assert data["diagnostics"]["roadmaps"][0]["evidence_status"] == "partial"


def test_roadmap_diagnostics_payload_is_stable(monkeypatch):
    fake_roadmap = SimpleNamespace(
        id=1,
        roadmap_uid="roadmap-stable",
        updated_at=datetime.utcnow(),
        recommendations=[{"type": "strategy", "text": "Keep going"}],
        velocity_history=[{"week": 1, "progress": 10}],
        trace_id="trace-stable",
    )
    fake_goal = SimpleNamespace(id=10)
    fake_tasks = [SimpleNamespace(id=1, completed=True)]

    _fake_progress_repos(monkeypatch, fake_roadmap, fake_goal, fake_tasks)

    data = client.get("/api/v1/roadmaps/progress").json()

    assert data["progress_source"] == "stored_task_completion"
    assert data["telemetry_status"] == "not_tracked"
    assert data["analytics_confidence"] is None
    assert data["metrics_available"] is False
    assert data["diagnostics"]["status"] == "healthy"
    assert set(data["diagnostics"]) == {
        "status",
        "summary",
        "roadmap_count",
        "stale_roadmap_count",
        "partial_roadmap_count",
        "roadmaps",
    }
    assert set(data["diagnostics"]["roadmaps"][0]) == {
        "roadmap_uid",
        "status",
        "evidence_status",
        "tasks_completed",
        "total_tasks",
        "updated_at",
        "trace_id",
    }


def test_learning_paths_do_not_change_roadmap_progress_source(monkeypatch):
    from src.services.learning.learning_path_service import LearningPathService

    monkeypatch.setattr(
        LearningPathService,
        "list_paths",
        AsyncMock(side_effect=AssertionError("roadmap progress should not depend on learning paths")),
    )

    fake_roadmap = SimpleNamespace(
        id=1,
        roadmap_uid="roadmap-1",
        updated_at=datetime.utcnow(),
        recommendations=[],
        velocity_history=[],
        trace_id="trace-1",
    )
    fake_goal = SimpleNamespace(id=10)
    fake_tasks = [SimpleNamespace(id=1, completed=False)]

    _fake_progress_repos(monkeypatch, fake_roadmap, fake_goal, fake_tasks)

    data = client.get("/api/v1/roadmaps/progress").json()

    assert data["progress_source"] == "stored_task_completion"
    assert data["diagnostics"]["status"] in {"healthy", "partial"}


def test_fallback_roadmap_is_marked_fallback(monkeypatch):
    db_results = [
        _QueuedResult(
            scalar_value=SimpleNamespace(
                gaps=[{"category": "python"}, {"title": "Testing"}]
            )
        ),
        _QueuedResult(
            rows=[
                (
                    SimpleNamespace(
                        match_details={"job_extraction": {"skills": ["Python", "FastAPI"]}},
                    ),
                    SimpleNamespace(skills_required=["Python", "FastAPI"]),
                )
            ]
        ),
    ]
    _fake_generate_dependencies(monkeypatch, db_results, _FailingProvider())

    response = client.post(
        "/api/v1/roadmaps/generate",
        json={
            "blueprint_type": "AI_ENGINEER",
            "target_role": "AI Engineer",
            "target_location": "San Francisco, CA",
            "target_timeline": "12 months",
            "target_salary": "$180,000/yr",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["generation_mode"] == "deterministic_fallback"
    assert body["generation_confidence"] == "low"
    assert body["fallback_reason"] == "provider_unavailable"
    assert body["goals_created"] > 0


def test_fallback_roadmap_has_low_confidence(monkeypatch):
    db_results = [
        _QueuedResult(
            scalar_value=SimpleNamespace(
                gaps=[{"category": "python"}]
            )
        ),
        _QueuedResult(rows=[]),
    ]
    _fake_generate_dependencies(monkeypatch, db_results, _PlanProvider({"unexpected": "shape"}))

    response = client.post(
        "/api/v1/roadmaps/generate",
        json={
            "blueprint_type": "AI_ENGINEER",
            "target_role": "AI Engineer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["generation_mode"] == "deterministic_fallback"
    assert body["generation_confidence"] == "low"
    assert body["fallback_reason"] in {
        "non_dict_provider_output",
        "invalid_json_output",
        "unstructured_provider_output",
        "generic_provider_output",
    }

