from datetime import datetime, timezone
from inspect import signature
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import MultipleResultsFound

from src.api.deps import get_current_user
from src.api.v1.endpoints import learning as learning_endpoint
from src.db.session import get_db
from src.main import app
from src.schemas.security import Role
from src.services.security.auth import auth_service
from src.services.learning.gap_action_service import LearningGapActionService
from src.services.learning.learning_path_service import LearningPathService, SkillGapAggregate


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


class _FakeLearningResourceService:
    def __init__(self, resources_by_skill: dict[str, list[SimpleNamespace]] | None = None) -> None:
        self._resources_by_skill = resources_by_skill or {}

    def provider_health(self) -> dict[str, object]:
        return {
            "enabled": True,
            "provider": "seeded",
            "youtube_configured": False,
            "seed_file_present": True,
            "status": "seeded_fallback",
        }

    async def ensure_skill_resources(
        self,
        db,
        skill_slug: str,
        skill_name: str | None = None,
        limit: int = 6,
        force_refresh: bool = False,
    ):
        return list(self._resources_by_skill.get(skill_slug, []))[:limit]


class _FakeJobContextResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeJobContextDB:
    def __init__(self, job, match, *, duplicate_match_rows: bool = False) -> None:
        self.job = job
        self.match = match
        self.duplicate_match_rows = duplicate_match_rows
        self.calls = 0

    async def execute(self, statement):
        self.calls += 1
        sql = str(statement).lower()
        if self.calls == 1:
            return _FakeJobContextResult(self.job)
        if self.duplicate_match_rows and "limit" not in sql:
            raise MultipleResultsFound("multiple matches")
        return _FakeJobContextResult(self.match)


def _make_resource(resource_id: int, skill_slug: str, title: str, source_url: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=resource_id,
        skill_slug=skill_slug,
        skill_name=skill_slug.upper(),
        title=title,
        provider="Verified Provider",
        source_type="official_docs",
        source_url=source_url,
        channel_name=None,
        duration_minutes=60,
        difficulty="beginner",
        format="tutorial",
        is_free=True,
        language="en",
        trust_score=0.98,
        relevance_score=0.96,
        freshness_score=0.93,
        last_verified_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
        metadata_={
            "step_type": "foundation",
            "discovery_source": "seed",
            "verification_status": "seeded_fallback",
            "price_status": "free",
            "source_domain": source_url.split("/")[2],
            "cache_status": "seed_cache",
        },
    )


@pytest.mark.asyncio
async def test_gap_action_service_links_verified_sources_and_generated_fallbacks():
    aws_resource = _make_resource(1, "aws", "AWS Cloud Practitioner Essentials", "https://aws.amazon.com/training/digital/")
    fake_resource_service = _FakeLearningResourceService(
        resources_by_skill={
            "aws": [aws_resource],
            "docker": [],
        }
    )
    path_service = LearningPathService(resource_service=fake_resource_service)  # type: ignore[arg-type]

    async def _aggregate_skill_gaps(db, user_id: str, limit: int = 10):
        return [
            SkillGapAggregate(
                skill_slug="aws",
                skill_name="AWS",
                count=3,
                source_job_ids=[101],
                source_job_titles=["Cloud Engineer"],
                job_match_ids=[201],
                max_match_score=82.0,
                latest_match_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
            ),
            SkillGapAggregate(
                skill_slug="docker",
                skill_name="Docker",
                count=2,
                source_job_ids=[102],
                source_job_titles=["Platform Engineer"],
                job_match_ids=[202],
                max_match_score=74.0,
                latest_match_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
            ),
        ][:limit]

    path_service.aggregate_skill_gaps = _aggregate_skill_gaps  # type: ignore[assignment]
    service = LearningGapActionService(
        learning_path_service=path_service,
        learning_resource_service=fake_resource_service,  # type: ignore[arg-type]
    )

    payload = await service.build_gap_actions(SimpleNamespace(), "user-123", ["aws", "docker"], job_id=None, force_refresh=True)

    assert payload["status"] == "ok"
    assert payload["cached"] is False
    assert [action["skill_slug"] for action in payload["actions"]] == ["aws", "docker"]

    aws_action = payload["actions"][0]
    docker_action = payload["actions"][1]

    assert aws_action["resource_status"] == "available"
    assert aws_action["source_resources"][0]["source_url"] == "https://aws.amazon.com/training/digital/"
    assert aws_action["project_ideas"][0]["source_status"] == "ai_generated_with_verified_learning_resources"
    assert aws_action["project_ideas"][0]["source_resources"][0]["source_url"].startswith("https://")

    assert docker_action["resource_status"] == "not_available"
    assert docker_action["source_resources"] == []
    assert docker_action["project_ideas"][0]["source_status"] == "generated_from_skill_context_no_external_source"
    assert docker_action["resume_proof"]["suggested_bullets"][0].startswith("Suggested resume bullet:")
    assert docker_action["interview_proof"]["sample_answer"].startswith("Suggested interview answer:")


@pytest.mark.asyncio
async def test_gap_action_service_generates_every_requested_skill_card():
    fake_resource_service = _FakeLearningResourceService(
        resources_by_skill={
            "aws": [_make_resource(1, "aws", "AWS Digital Training", "https://aws.amazon.com/training/digital/")],
            "java": [_make_resource(2, "java", "Getting started with Java", "https://dev.java/learn/getting-started/")],
        }
    )
    path_service = LearningPathService(resource_service=fake_resource_service)  # type: ignore[arg-type]

    async def _aggregate_skill_gaps(db, user_id: str, limit: int = 10):
        return [
            SkillGapAggregate(
                skill_slug="aws",
                skill_name="AWS",
                count=4,
                source_job_ids=[11],
                source_job_titles=["Cloud Engineer"],
                job_match_ids=[21],
                max_match_score=91.0,
                latest_match_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
            )
        ]

    path_service.aggregate_skill_gaps = _aggregate_skill_gaps  # type: ignore[assignment]
    service = LearningGapActionService(
        learning_path_service=path_service,
        learning_resource_service=fake_resource_service,  # type: ignore[arg-type]
    )

    payload = await service.build_gap_actions(SimpleNamespace(), "user-123", ["aws", "docker", "java"], job_id=None)

    assert [action["skill_slug"] for action in payload["actions"]] == ["aws", "docker", "java"]
    assert payload["actions"][1]["resource_status"] == "not_available"
    assert payload["actions"][2]["resource_status"] == "available"
    assert payload["actions"][2]["source_resources"][0]["source_url"].startswith("https://")


@pytest.fixture
def authenticated_learning_routes(monkeypatch):
    original_overrides = dict(app.dependency_overrides)

    async def _override_user():
        return {"sub": "user-123", "role": "User"}

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    fake_payload = {
        "status": "ok",
        "user_id": "user-123",
        "job_id": 9,
        "job_context": {
            "job_id": 9,
            "title": "Cloud Engineer",
            "company": "CareerOS",
            "location": "Remote",
            "apply_url": "https://example.com/jobs/9",
            "source_url": "https://example.com/jobs/9",
            "match_score": 87.5,
            "missing_skill_slugs": ["aws", "docker"],
            "missing_skill_names": ["AWS", "Docker"],
        },
        "cached": False,
        "generated_at": "2026-06-19T00:00:00Z",
        "provider_health": {
            "enabled": True,
            "provider": "seeded",
            "youtube_configured": False,
            "seed_file_present": True,
            "status": "seeded_fallback",
        },
        "source_status": "verified_resource_supported",
        "actions": [
            {
                "skill_slug": "aws",
                "skill_name": "AWS",
                "count": 3,
                "priority": "high",
                "estimated_hours": 14.0,
                "reason": "AWS appears in 3 matched jobs across 1 roles; highest match score 87.5.",
                "source_job_ids": [9],
                "source_job_titles": ["Cloud Engineer"],
                "job_match_ids": [3],
                "resource_status": "available",
                "resource_count": 1,
                "source_status": "ai_generated_with_verified_learning_resources",
                "source_resources": [
                    {
                        "id": 1,
                        "skill_slug": "aws",
                        "skill_name": "AWS",
                        "title": "AWS Digital Training",
                        "provider": "AWS",
                        "source_type": "official_docs",
                        "source_url": "https://aws.amazon.com/training/digital/",
                        "channel_name": None,
                        "duration_minutes": 60,
                        "difficulty": "beginner",
                        "format": "tutorial",
                        "is_free": True,
                        "language": "en",
                        "trust_score": 0.98,
                        "relevance_score": 0.96,
                        "freshness_score": 0.93,
                        "last_verified_at": "2026-06-18T00:00:00Z",
                        "metadata": {
                            "step_type": "foundation",
                            "discovery_source": "seed",
                            "verification_status": "seeded_fallback",
                            "price_status": "free",
                            "source_domain": "aws.amazon.com",
                            "cache_status": "seed_cache",
                        },
                        "source_domain": "aws.amazon.com",
                        "discovery_source": "seed",
                        "verification_status": "seeded_fallback",
                        "price_status": "free",
                        "cache_status": "seed_cache",
                    }
                ],
                "project_ideas": [
                    {
                        "title": "Deploy a FastAPI service on AWS",
                        "difficulty": "beginner",
                        "estimated_hours": 6,
                        "proof_type": "portfolio_project",
                        "steps": ["Review AWS Digital Training", "Build the app", "Document the tradeoffs"],
                        "source_resources": [],
                        "resume_bullets": ["Suggested resume bullet: Built a sample AWS project."],
                        "github_readme_outline": ["Problem statement", "Architecture"],
                        "source_status": "ai_generated_with_verified_learning_resources",
                    }
                ],
                "resume_proof": {
                    "before_gap": "No verified AWS proof is linked yet.",
                    "suggested_bullets": ["Suggested resume bullet: Built a sample AWS project."],
                    "linkedin_bullets": ["Suggested LinkedIn bullet: Shared an AWS proof project."],
                    "portfolio_description": "Suggested portfolio blurb: AWS project.",
                    "source_status": "ai_generated_with_verified_learning_resources",
                },
                "interview_proof": {
                    "talking_points": ["Why AWS?", "How did you verify it?"],
                    "sample_answer": "Suggested interview answer: I used the AWS project to close a real gap.",
                    "source_status": "ai_generated_with_verified_learning_resources",
                },
            }
        ],
    }

    class _FakeService:
        async def build_gap_actions(self, db, user_id: str, skills: list[str], job_id=None, force_refresh: bool = False):
            assert skills == ["aws", "docker"]
            assert job_id == 9
            return fake_payload

    monkeypatch.setattr(learning_endpoint, "get_learning_gap_action_service", lambda: _FakeService())

    yield fake_payload

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


def test_learning_gap_actions_routes_require_auth():
    response = client.get("/api/v1/learning/gap-actions?skills=aws,docker")
    assert response.status_code == 401


def test_learning_gap_actions_endpoint_returns_cards(authenticated_learning_routes):
    response = client.get("/api/v1/learning/gap-actions?skills=aws,docker&job_id=9")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["job_context"]["title"] == "Cloud Engineer"
    assert len(payload["actions"]) == 1
    assert payload["actions"][0]["skill_slug"] == "aws"
    assert payload["actions"][0]["source_resources"][0]["source_url"].startswith("https://")

    response = client.post("/api/v1/learning/gap-actions/refresh", json={"skills": ["aws", "docker"], "job_id": 9})
    assert response.status_code == 200
    payload = response.json()
    assert payload["cached"] is False
    assert payload["source_status"] == "verified_resource_supported"


@pytest.mark.asyncio
async def test_gap_action_service_loads_single_job_match_even_when_duplicates_exist():
    job = SimpleNamespace(
        id=17589,
        title="Cloud Engineer",
        company="CareerOS",
        location="Remote",
        apply_url="https://example.com/jobs/17589",
        source_url="https://example.com/jobs/17589",
        skills_required=["aws", "docker"],
    )
    match = SimpleNamespace(
        overall_score=87.5,
        gaps=[{"skill": "AWS"}],
        match_details={"missing_skills": ["docker"], "job_extraction": {"skills": ["react"]}},
    )

    class _FakeDB:
        async def execute(self, statement):
            sql = str(statement).lower()
            if "from jobs" in sql:
                return _FakeJobContextResult(job)
            if "from job_matches" in sql:
                assert "limit" in sql
                return _FakeJobContextResult(match)
            raise AssertionError(f"Unexpected statement: {statement}")

    fake_resource_service = _FakeLearningResourceService()
    path_service = LearningPathService(resource_service=fake_resource_service)  # type: ignore[arg-type]

    async def _aggregate_skill_gaps(*args, **kwargs):
        return []

    path_service.aggregate_skill_gaps = _aggregate_skill_gaps  # type: ignore[assignment]
    service = LearningGapActionService(
        learning_path_service=path_service,
        learning_resource_service=fake_resource_service,  # type: ignore[arg-type]
    )

    payload = await service.build_gap_actions(_FakeDB(), "user-123", ["aws", "azure"], job_id=17589, force_refresh=False)

    assert payload["status"] == "ok"
    assert payload["job_context"]["job_id"] == 17589
    assert [item["skill_slug"] for item in payload["actions"]] == ["aws", "azure"]


def test_gap_actions_refresh_rejects_missing_body_with_400():
    response = client.post("/api/v1/learning/gap-actions/refresh", headers=_user_auth_headers())
    assert response.status_code == 400


def test_gap_actions_invalid_job_id_returns_404_not_500(monkeypatch):
    class _MissingJobService:
        async def build_gap_actions(self, db, user_id: str, skills: list[str], job_id=None, force_refresh: bool = False):
            raise ValueError("Job not found")

    original_overrides = dict(app.dependency_overrides)
    async def _override_user():
        return {"sub": "user-123", "role": "User"}

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    monkeypatch.setattr(learning_endpoint, "get_learning_gap_action_service", lambda: _MissingJobService())

    response = client.get("/api/v1/learning/gap-actions?skills=aws,azure,javascript,react&job_id=17589")

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)

    assert response.status_code == 404
