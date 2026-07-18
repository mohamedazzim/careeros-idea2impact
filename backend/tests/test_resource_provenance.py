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
from src.services.learning.learning_path_service import LearningPathService, SkillGapAggregate
from src.services.learning.resource_provenance_service import ResourceProvenanceService
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


@pytest.fixture
def authenticated_learning_routes():
    original_overrides = dict(app.dependency_overrides)

    async def _override_user():
        return {"sub": "user-123", "role": "User"}

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    yield

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


def test_resource_provenance_helpers_build_honest_scores():
    service = ResourceProvenanceService()
    breakdown = service.build_score_breakdown(
        trust_score=0.9,
        relevance_score=0.8,
        freshness_score=0.7,
        verification_status="verified",
        source_kind="live",
    )
    assert breakdown["composite_score"] > 0
    explanation = service.build_explanation(
        title="AWS Tutorials",
        provider="AWS",
        source_kind="live",
        verification_status="verified",
        score_breakdown=breakdown,
    )
    assert "AWS Tutorials" in explanation
    assert "AWS" in explanation


def test_learning_provenance_routes_require_auth():
    response = client.get("/api/v1/learning/provenance")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_resource_provenance_lookup_skips_db_stubs_without_execute():
    service = ResourceProvenanceService()
    assert await service.get_latest_resource_summary(SimpleNamespace(), resource_id=123) is None
    assert await service.get_provenance_by_uid(SimpleNamespace(), "prov-1", user_id="user-123") is None
    assert await service.get_discovery_run_by_uid(SimpleNamespace(), "run-1", user_id="user-123") is None
    records, total = await service.list_provenance(SimpleNamespace(), user_id="user-123")
    assert records == []
    assert total == 0
    runs, total_runs = await service.list_discovery_runs(SimpleNamespace(), user_id="user-123")
    assert runs == []
    assert total_runs == 0


def test_learning_provenance_routes_return_records(authenticated_learning_routes, monkeypatch):
    fake_records = [
        {
            "provenance_uid": "prov-1",
            "provenance_type": "learning_resource",
            "source_entity_type": "learning_resource",
            "source_entity_id": "12",
            "source_table": "learning_resources",
            "source_pk": "12",
            "recorded_at": "2026-06-19T00:00:00Z",
            "status": "success",
            "confidence": "high",
            "score_total": 95.0,
            "score_formula": "trust*0.45 + relevance*0.35 + freshness*0.20",
            "score_breakdown": {"composite_score": 95.0},
            "explanation": "Verified official docs.",
            "evidence_count": 1,
            "provider": "AWS",
            "skill_slug": "aws",
            "skill_name": "AWS",
            "title": "AWS Tutorials",
            "source_url": "https://aws.amazon.com/training/",
            "resource_id": 12,
            "discovery_run_uid": "run-1",
        }
    ]

    fake_runs = [
        {
            "run_uid": "run-1",
            "status": "completed",
            "provider": "seeded",
            "source_type": "learning_resource",
            "skill_slug": "aws",
            "skill_name": "AWS",
            "candidate_count": 1,
            "stored_count": 1,
            "started_at": "2026-06-19T00:00:00Z",
            "completed_at": "2026-06-19T00:01:00Z",
            "error_message": None,
        }
    ]
    captured_list_kwargs: list[dict[str, object]] = []
    captured_run_kwargs: list[dict[str, object]] = []
    captured_detail_kwargs: list[dict[str, object]] = []
    captured_run_detail_kwargs: list[dict[str, object]] = []

    class _FakeService:
        async def list_provenance(self, db, **kwargs):
            captured_list_kwargs.append(kwargs)
            return fake_records, len(fake_records)

        async def get_provenance_by_uid(self, db, provenance_uid: str, **kwargs):
            captured_detail_kwargs.append(kwargs)
            assert provenance_uid == "prov-1"
            return fake_records[0] if provenance_uid == "prov-1" else None

        async def list_discovery_runs(self, db, **kwargs):
            captured_run_kwargs.append(kwargs)
            return fake_runs, len(fake_runs)

        async def get_discovery_run_by_uid(self, db, run_uid: str, **kwargs):
            captured_run_detail_kwargs.append(kwargs)
            assert run_uid == "run-1"
            return fake_runs[0] if run_uid == "run-1" else None

    monkeypatch.setattr(learning_endpoint, "get_resource_provenance_service", lambda: _FakeService())

    response = client.get("/api/v1/learning/provenance", headers=_user_auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["records"][0]["provenance_uid"] == "prov-1"
    assert captured_list_kwargs[-1]["user_id"] == "user-123"

    response = client.get(
        "/api/v1/learning/provenance?skill_slug=aws&provider=AWS&source_type=learning_resource&resource_type=learning_resource&job_id=9&status=success",
        headers=_user_auth_headers(),
    )
    assert response.status_code == 200
    assert captured_list_kwargs[-1]["skill_slug"] == "aws"
    assert captured_list_kwargs[-1]["provider"] == "AWS"
    assert captured_list_kwargs[-1]["source_type"] == "learning_resource"
    assert captured_list_kwargs[-1]["resource_type"] == "learning_resource"
    assert captured_list_kwargs[-1]["job_id"] == 9
    assert captured_list_kwargs[-1]["status"] == "success"

    response = client.get("/api/v1/learning/provenance/prov-1", headers=_user_auth_headers())
    assert response.status_code == 200
    assert response.json()["source_entity_type"] == "learning_resource"
    assert captured_detail_kwargs[-1]["user_id"] == "user-123"

    response = client.get("/api/v1/learning/resources/12/provenance", headers=_user_auth_headers())
    assert response.status_code == 200
    assert response.json()["records"][0]["resource_id"] == 12

    response = client.get("/api/v1/learning/discovery-runs", headers=_user_auth_headers())
    assert response.status_code == 200
    assert response.json()["runs"][0]["run_uid"] == "run-1"
    assert captured_run_kwargs[-1]["user_id"] == "user-123"

    response = client.get("/api/v1/learning/discovery-runs/run-1", headers=_user_auth_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert captured_run_detail_kwargs[-1]["user_id"] == "user-123"


@pytest.mark.asyncio
async def test_learning_path_payload_includes_provenance_summary():
    resource = SimpleNamespace(
        id=42,
        skill_slug="aws",
        skill_name="AWS",
        title="AWS Tutorials",
        provider="AWS",
        source_type="official_docs",
        source_url="https://aws.amazon.com/training/",
        channel_name=None,
        duration_minutes=90,
        difficulty="beginner",
        format="tutorial",
        is_free=True,
        language="en",
        trust_score=0.95,
        relevance_score=0.9,
        freshness_score=0.85,
        last_verified_at=datetime(2026, 6, 19, tzinfo=timezone.utc),
        metadata_={"step_type": "foundation", "seeded": True, "verification_status": "seeded_fallback"},
    )

    class _FakeResourceService:
        async def ensure_skill_resources(self, db, skill_slug: str, skill_name: str | None = None, limit: int = 6, force_refresh: bool = False):
            return [resource]

        def provider_health(self):
            return {"provider": "seeded", "status": "seeded_fallback"}

    class _FakeProvenanceService:
        async def get_latest_resource_summary(self, db, resource_id: int):
            return {
                "provenance_uid": "prov-42",
                "provenance_type": "seeded_fallback",
                "source_entity_type": "learning_resource",
                "source_entity_id": str(resource_id),
                "recorded_at": "2026-06-19T00:00:00Z",
                "status": "success",
                "confidence": "high",
                "score_total": 95.0,
                "score_formula": "trust*0.45 + relevance*0.35 + freshness*0.20",
                "score_breakdown": {"composite_score": 95.0},
                "explanation": "Verified official docs.",
                "evidence_count": 1,
                "provider": "AWS",
                "skill_slug": "aws",
                "skill_name": "AWS",
                "title": "AWS Tutorials",
                "source_url": "https://aws.amazon.com/training/",
                "resource_id": resource_id,
                "discovery_run_uid": None,
            }

    service = LearningPathService(resource_service=_FakeResourceService())  # type: ignore[arg-type]
    service.provenance_service = _FakeProvenanceService()  # type: ignore[assignment]
    aggregate = SkillGapAggregate(
        skill_slug="aws",
        skill_name="AWS",
        count=2,
        source_job_ids=[7],
        source_job_titles=["Cloud Engineer"],
        job_match_ids=[9],
        max_match_score=91.5,
        latest_match_at=datetime(2026, 6, 19, tzinfo=timezone.utc),
    )

    payload = await service._build_path_payload(SimpleNamespace(), "user-123", aggregate)

    assert payload["provenance_summary"]["source_entity_type"] == "learning_path"
    assert payload["steps"][0]["resources"][0]["provenance_summary"]["provenance_uid"] == "prov-42"
