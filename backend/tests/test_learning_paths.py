from datetime import datetime, timezone
from inspect import signature
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_current_user
from src.api.v1.endpoints import learning as learning_endpoint
from src.db.session import get_db
from src.integrations.learning.discovery import DiscoveryCandidate
from src.main import app
from src.services.learning.learning_path_service import LearningPathService, SkillGapAggregate
from src.services.learning.skill_normalizer import normalize_skill, normalize_skill_list


if "app" not in signature(httpx.Client.__init__).parameters:
    _httpx_client_init = httpx.Client.__init__

    def _patched_httpx_client_init(self, *args, app=None, **kwargs):
        return _httpx_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = _patched_httpx_client_init


client = TestClient(app)


async def _override_db():
    yield SimpleNamespace()


class _FakeLearningResourceService:
    def __init__(self, resources: list[SimpleNamespace] | None = None) -> None:
        self._resources = resources or []

    def provider_health(self) -> dict[str, object]:
        return {
            "enabled": True,
            "provider": "seeded",
            "youtube_configured": False,
            "seed_file_present": True,
        }

    async def ensure_skill_resources(
        self,
        db,
        skill_slug: str,
        skill_name: str | None = None,
        limit: int = 6,
        force_refresh: bool = False,
    ):
        return list(self._resources)[:limit]


class _FakePersistResult:
    def __init__(self, value: int = 1) -> None:
        self._value = value

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value

    def all(self):
        return []


class _FakePersistingDB:
    async def execute(self, statement):
        return _FakePersistResult()

    async def commit(self):
        return None


class _FakeDiscoveryProvider:
    def __init__(self, name: str, candidates: list[DiscoveryCandidate] | None = None, status: str = "ready") -> None:
        self.name = name
        self._candidates = candidates or []
        self._status = status

    def health(self) -> dict[str, object]:
        return {
            "name": self.name,
            "display_name": self.name.title(),
            "status": self._status,
            "configured": True,
            "enabled": True,
            "last_result_count": len(self._candidates),
        }

    async def discover(self, skill_name: str, skill_slug: str, limit: int = 5):
        return list(self._candidates)[:limit]


class _FakeLearningPathService:
    def __init__(self, path_payload: dict[str, object]) -> None:
        self._path_payload = path_payload
        self.last_list_paths_args = None
        self.last_get_path_args = None

    async def get_skill_gap_summary(self, db, user_id: str, limit: int = 10):
        return {
            "status": "ok",
            "user_id": user_id,
            "total_gaps": 1,
            "unique_skills": 1,
            "gaps": [
                {
                    "skill_slug": "tensorflow",
                    "skill_name": "TensorFlow",
                    "count": 2,
                    "priority": "medium",
                    "estimated_hours": 10.0,
                    "reason": "TensorFlow appears in 2 matched jobs across 1 roles; highest match score 81.0.",
                    "source_job_ids": [11],
                    "source_job_titles": ["ML Engineer"],
                    "job_match_ids": [21],
                    "max_match_score": 81.0,
                    "resource_status": "available",
                }
            ],
            "provider_health": {
                "enabled": True,
                "provider": "seeded",
                "youtube_configured": False,
                "status": "seeded_fallback",
            },
        }

    async def list_paths(self, db, user_id: str, limit: int = 10, skill_slugs=None, force_refresh: bool = False):
        self.last_list_paths_args = {
            "limit": limit,
            "skill_slugs": skill_slugs,
            "force_refresh": force_refresh,
        }
        return {
            "status": "ok",
            "user_id": user_id,
            "paths": [self._path_payload],
            "skill_gaps": [
                {
                    "skill_slug": "tensorflow",
                    "skill_name": "TensorFlow",
                    "count": 2,
                    "priority": "medium",
                    "estimated_hours": 10.0,
                    "reason": "TensorFlow appears in 2 matched jobs across 1 roles; highest match score 81.0.",
                    "source_job_ids": [11],
                    "source_job_titles": ["ML Engineer"],
                    "job_match_ids": [21],
                    "max_match_score": 81.0,
                    "resource_status": "available",
                }
            ],
            "provider_health": {
                "enabled": True,
                "provider": "seeded",
                "youtube_configured": False,
                "status": "seeded_fallback",
            },
        }

    async def get_path(self, db, user_id: str, skill_slug: str, force_refresh: bool = False):
        self.last_get_path_args = {
            "skill_slug": skill_slug,
            "force_refresh": force_refresh,
        }
        return {
            "status": "ok",
            "user_id": user_id,
            "path": self._path_payload,
            "provider_health": {
                "enabled": True,
                "provider": "seeded",
                "youtube_configured": False,
                "status": "seeded_fallback",
            },
        }

    async def refresh_paths(self, db, user_id: str, limit: int = 10):
        return {
            "status": "ok",
            "user_id": user_id,
            "refreshed_count": 1,
            "paths": [self._path_payload],
            "provider_health": {
                "enabled": True,
                "provider": "seeded",
                "youtube_configured": False,
                "status": "seeded_fallback",
            },
        }


@pytest.fixture
def authenticated_learning_routes(monkeypatch):
    original_overrides = dict(app.dependency_overrides)

    async def _override_user():
        return {"sub": "user-123", "role": "User"}

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    resource = SimpleNamespace(
        id=1,
        skill_slug="tensorflow",
        skill_name="TensorFlow",
        title="TensorFlow Tutorials",
        provider="TensorFlow",
        source_type="official_docs",
        source_url="https://www.tensorflow.org/tutorials",
        channel_name=None,
        duration_minutes=90,
        difficulty="beginner",
        format="tutorial",
        is_free=True,
        language="en",
        trust_score=0.97,
        relevance_score=0.92,
        freshness_score=0.88,
        last_verified_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
        metadata_={"step_type": "foundation"},
    )
    path_payload = {
        "skill_slug": "tensorflow",
        "skill_name": "TensorFlow",
        "priority": "medium",
        "estimated_hours": 10.0,
        "reason": "TensorFlow appears in 2 matched jobs across 1 roles; highest match score 81.0.",
        "source_job_ids": [11],
        "source_job_titles": ["ML Engineer"],
        "job_match_ids": [21],
        "resource_status": "available",
        "discovery_status": "seeded_fallback",
        "resource_count": 1,
        "resource_titles": ["TensorFlow Tutorials"],
        "source_domains": ["www.tensorflow.org"],
        "message": None,
        "cached": True,
        "generated_at": "2026-06-18T00:00:00Z",
        "refreshed_at": "2026-06-18T00:00:00Z",
        "steps": [
            {
                "order_index": 1,
                "step_type": "foundation",
                "title": "Understand TensorFlow fundamentals",
                "reason": "Start with the official free material for TensorFlow.",
                "estimated_minutes": 90,
                "practice_project": None,
                "resources": [
                    {
                        "id": 1,
                        "skill_slug": "tensorflow",
                        "skill_name": "TensorFlow",
                        "title": "TensorFlow Tutorials",
                        "provider": "TensorFlow",
                        "source_type": "official_docs",
                        "source_url": "https://www.tensorflow.org/tutorials",
                        "channel_name": None,
                        "duration_minutes": 90,
                        "difficulty": "beginner",
                        "format": "tutorial",
                        "is_free": True,
                        "language": "en",
                        "trust_score": 0.97,
                        "relevance_score": 0.92,
                        "freshness_score": 0.88,
                        "last_verified_at": "2026-06-18T00:00:00Z",
                        "metadata": {
                            "step_type": "foundation",
                            "discovery_source": "seed",
                            "verification_status": "seeded_fallback",
                            "price_status": "free",
                            "source_domain": "www.tensorflow.org",
                            "cache_status": "seed_cache",
                        },
                        "source_domain": "www.tensorflow.org",
                        "discovery_source": "seed",
                        "verification_status": "seeded_fallback",
                        "price_status": "free",
                        "cache_status": "seed_cache",
                    }
                ],
            },
            {
                "order_index": 2,
                "step_type": "hands_on",
                "title": "Apply TensorFlow in a small project",
                "reason": "Turn reading into a runnable or demonstrable artifact.",
                "estimated_minutes": 180,
                "practice_project": "Train a small model on a public dataset and explain evaluation metrics clearly.",
                "resources": [
                    {
                        "id": 1,
                        "skill_slug": "tensorflow",
                        "skill_name": "TensorFlow",
                        "title": "TensorFlow Tutorials",
                        "provider": "TensorFlow",
                        "source_type": "official_docs",
                        "source_url": "https://www.tensorflow.org/tutorials",
                        "channel_name": None,
                        "duration_minutes": 90,
                        "difficulty": "beginner",
                        "format": "tutorial",
                        "is_free": True,
                        "language": "en",
                        "trust_score": 0.97,
                        "relevance_score": 0.92,
                        "freshness_score": 0.88,
                        "last_verified_at": "2026-06-18T00:00:00Z",
                        "metadata": {
                            "step_type": "foundation",
                            "discovery_source": "seed",
                            "verification_status": "seeded_fallback",
                            "price_status": "free",
                            "source_domain": "www.tensorflow.org",
                            "cache_status": "seed_cache",
                        },
                        "source_domain": "www.tensorflow.org",
                        "discovery_source": "seed",
                        "verification_status": "seeded_fallback",
                        "price_status": "free",
                        "cache_status": "seed_cache",
                    }
                ],
            },
            {
                "order_index": 3,
                "step_type": "proof",
                "title": "Add evidence to resume and portfolio",
                "reason": "Translate the new skill into interview-ready proof.",
                "estimated_minutes": 60,
                "practice_project": "Write one resume bullet and one portfolio note showing how you used TensorFlow.",
                "resources": [],
            },
        ],
    }

    fake_service = _FakeLearningPathService(path_payload)
    monkeypatch.setattr(learning_endpoint, "get_learning_path_service", lambda: fake_service)

    yield fake_service

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


def test_skill_normalizer_aliases_and_dedupes():
    normalized = normalize_skill_list(["AWS", "Amazon Web Services", "TensorFlow", "tensorflow"])
    assert [item.slug for item in normalized] == ["aws", "tensorflow"]
    assert normalized[0].display_name == "AWS"
    assert normalized[1].display_name == "TensorFlow"


def test_skill_normalizer_keeps_java_and_javascript_distinct():
    normalized = normalize_skill_list(["Java", "JDK", "JavaScript", "Java Script", "core java"])
    assert [item.slug for item in normalized] == ["java", "javascript"]
    assert normalized[0].display_name == "Java"
    assert normalized[1].display_name == "JavaScript"


def test_skill_normalizer_handles_java_programming_and_js_aliases():
    normalized = normalize_skill_list(["Java Programming", "JS"])
    assert [item.slug for item in normalized] == ["java", "javascript"]
    assert normalized[0].display_name == "Java"
    assert normalized[1].display_name == "JavaScript"


def test_skill_normalizer_maps_cpp_to_cpp():
    normalized = normalize_skill("c++")
    assert normalized.slug == "cpp"
    assert normalized.display_name == "C++"


def test_skill_normalizer_maps_ci_cd_to_ci_cd():
    normalized = normalize_skill("ci/cd")
    assert normalized.slug == "ci-cd"
    assert normalized.display_name == "CI/CD"


def test_skill_normalizer_keeps_java_and_javascript_separate():
    normalized = normalize_skill_list(["Java", "JavaScript", "JS", "JDK"])
    assert [item.slug for item in normalized] == ["java", "javascript"]
    assert normalized[0].display_name == "Java"
    assert normalized[1].display_name == "JavaScript"


def test_skill_normalizer_handles_azure_and_react_without_error():
    normalized = normalize_skill_list(["azure", "React", "react"])
    assert [item.slug for item in normalized] == ["azure", "react"]
    assert normalized[0].display_name == "azure"
    assert normalized[1].display_name == "React"


def test_java_seed_resource_is_real_and_normalizes():
    import json
    from pathlib import Path

    seed_path = Path(__file__).resolve().parents[1] / "seeds" / "learning_resources.json"
    rows = json.loads(seed_path.read_text(encoding="utf-8"))
    java_rows = [row for row in rows if row.get("skill_slug") == "java"]
    assert len(java_rows) >= 4

    from src.services.learning.learning_resource_service import LearningResourceService

    service = LearningResourceService(discovery_providers=[])
    record = service._normalize_seed_record(java_rows[0])
    assert record is not None
    assert record.skill_slug == "java"
    assert record.skill_name == "Java"
    assert record.source_url.startswith("https://")
    assert "java" in record.source_url.lower()


def test_learning_resource_service_reports_honest_provider_messages():
    from src.services.learning.learning_resource_service import LearningResourceService

    class _MessageProvider:
        name = "web"

        def health(self) -> dict[str, object]:
            return {
                "name": "web",
                "display_name": "Web search",
                "status": "success",
                "configured": True,
                "enabled": True,
                "last_result_count": 0,
                "message": "No verified results returned for this query yet.",
            }

    resource_service = LearningResourceService(discovery_providers=[_MessageProvider()])
    health = resource_service.provider_health()
    assert health["status"] in {"success", "seeded_fallback"}
    assert "fallback" in health["message"].lower() or "verified" in health["message"].lower()
    assert health["providers"][0]["message"] == "No verified results returned for this query yet."


@pytest.mark.asyncio
async def test_learning_path_service_builds_verified_three_step_path():
    resource = SimpleNamespace(
        id=1,
        skill_slug="tensorflow",
        skill_name="TensorFlow",
        title="TensorFlow Tutorials",
        provider="TensorFlow",
        source_type="official_docs",
        source_url="https://www.tensorflow.org/tutorials",
        channel_name=None,
        duration_minutes=90,
        difficulty="beginner",
        format="tutorial",
        is_free=True,
        language="en",
        trust_score=0.97,
        relevance_score=0.92,
        freshness_score=0.88,
        last_verified_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
        metadata_={"step_type": "foundation"},
    )
    service = LearningPathService(resource_service=_FakeLearningResourceService([resource]))
    aggregate = SkillGapAggregate(
        skill_slug="tensorflow",
        skill_name="TensorFlow",
        count=2,
        source_job_ids=[11],
        source_job_titles=["ML Engineer"],
        job_match_ids=[21],
        max_match_score=81.0,
        latest_match_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
    )

    payload = await service._build_path_payload(SimpleNamespace(), "user-123", aggregate)

    assert payload["resource_status"] == "available"
    assert len(payload["steps"]) == 3
    assert payload["steps"][0]["resources"][0]["title"] == "TensorFlow Tutorials"
    assert payload["steps"][1]["practice_project"]
    assert payload["steps"][2]["resources"] == []


@pytest.mark.asyncio
async def test_learning_path_service_marks_missing_resources_not_available():
    service = LearningPathService(resource_service=_FakeLearningResourceService([]))
    aggregate = SkillGapAggregate(
        skill_slug="tensorflow",
        skill_name="TensorFlow",
        count=1,
        source_job_ids=[11],
        source_job_titles=["ML Engineer"],
        job_match_ids=[21],
        max_match_score=55.0,
        latest_match_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
    )

    payload = await service._build_path_payload(SimpleNamespace(), "user-123", aggregate)

    assert payload["resource_status"] == "not_available"
    assert payload["steps"] == []
    assert "TensorFlow" in payload["message"] or "tensorflow" in payload["message"].lower()


@pytest.mark.asyncio
async def test_learning_path_service_returns_one_path_per_requested_skill():
    class _SkillAwareResourceService(_FakeLearningResourceService):
        async def ensure_skill_resources(
            self,
            db,
            skill_slug: str,
            skill_name: str | None = None,
            limit: int = 6,
            force_refresh: bool = False,
        ):
            if skill_slug in {"aws", "java"}:
                return list(self._resources)[:limit]
            return []

    aws_resource = SimpleNamespace(
        id=1,
        skill_slug="aws",
        skill_name="AWS",
        title="AWS Digital Training",
        provider="AWS",
        source_type="official_docs",
        source_url="https://aws.amazon.com/training/",
        channel_name=None,
        duration_minutes=60,
        difficulty="beginner",
        format="tutorial",
        is_free=True,
        language="en",
        trust_score=0.99,
        relevance_score=0.96,
        freshness_score=0.9,
        last_verified_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
        metadata_={"step_type": "foundation"},
    )
    java_resource = SimpleNamespace(
        id=2,
        skill_slug="java",
        skill_name="Java",
        title="Getting started with Java",
        provider="dev.java",
        source_type="official_docs",
        source_url="https://dev.java/learn/getting-started/",
        channel_name=None,
        duration_minutes=60,
        difficulty="beginner",
        format="tutorial",
        is_free=True,
        language="en",
        trust_score=0.99,
        relevance_score=0.96,
        freshness_score=0.9,
        last_verified_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
        metadata_={"step_type": "foundation"},
    )
    service = LearningPathService(resource_service=_SkillAwareResourceService([aws_resource, java_resource]))

    aggregates = [
        SkillGapAggregate(
            skill_slug="aws",
            skill_name="AWS",
            count=1,
            source_job_ids=[1],
            source_job_titles=["Job 1"],
            job_match_ids=[11],
            max_match_score=90.0,
            latest_match_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
        )
    ]

    async def _aggregate_skill_gaps(db, user_id: str, limit: int = 10):
        assert limit >= 5
        return aggregates

    service.aggregate_skill_gaps = _aggregate_skill_gaps  # type: ignore[assignment]

    payload = await service.list_paths(
        _FakePersistingDB(),
        "user-123",
        limit=5,
        skill_slugs=["aws", "c++", "ci/cd", "data", "java"],
        force_refresh=False,
    )

    assert [path["skill_slug"] for path in payload["paths"]] == ["aws", "cpp", "ci-cd", "data", "java"]
    assert payload["paths"][0]["resource_status"] == "available"
    assert payload["paths"][1]["resource_status"] == "not_available"
    assert payload["paths"][4]["resource_status"] == "available"
    assert payload["paths"][1]["steps"] == []
    assert payload["paths"][4]["steps"][0]["resources"][0]["source_url"].startswith("https://")


@pytest.mark.asyncio
async def test_learning_path_service_does_not_limit_requested_skills_globally():
    class _AlwaysEmptyResourceService(_FakeLearningResourceService):
        async def ensure_skill_resources(
            self,
            db,
            skill_slug: str,
            skill_name: str | None = None,
            limit: int = 6,
            force_refresh: bool = False,
        ):
            return []

    service = LearningPathService(resource_service=_AlwaysEmptyResourceService())

    async def _aggregate_skill_gaps(db, user_id: str, limit: int = 10):
        assert limit >= 8
        return []

    service.aggregate_skill_gaps = _aggregate_skill_gaps  # type: ignore[assignment]

    payload = await service.list_paths(
        _FakePersistingDB(),
        "user-123",
        limit=3,
        skill_slugs=["aws", "c++", "ci/cd", "data", "docker", "java", "javascript", "kubernetes"],
        force_refresh=False,
    )

    assert [path["skill_slug"] for path in payload["paths"]] == [
        "aws",
        "cpp",
        "ci-cd",
        "data",
        "docker",
        "java",
        "javascript",
        "kubernetes",
    ]
    assert all(path["resource_status"] == "not_available" for path in payload["paths"])


@pytest.mark.asyncio
async def test_learning_resource_service_reports_multi_provider_health():
    web_candidate = DiscoveryCandidate(
        skill_slug="tensorflow",
        skill_name="TensorFlow",
        title="TensorFlow Official Docs",
        provider="Web search",
        source_type="web_search_result",
        source_url="https://www.tensorflow.org/tutorials",
        channel_name="Web search",
        duration_minutes=None,
        difficulty="beginner",
        format="guide",
        is_free=True,
        language="en",
        trust_score=0.9,
        relevance_score=0.9,
        freshness_score=0.8,
        last_verified_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
        metadata={"step_type": "foundation"},
    )
    from src.services.learning.learning_resource_service import LearningResourceService

    resource_service = LearningResourceService(
        discovery_providers=[_FakeDiscoveryProvider("web", [web_candidate])],
    )
    health = resource_service.provider_health()
    assert health["provider_mode"]
    assert isinstance(health["providers"], list)
    assert health["providers"][0]["name"] == "web"
    assert health["status"] in {"seeded_fallback", "success", "skipped"}


def test_learning_resource_service_uses_configured_web_backend(monkeypatch):
    from src.integrations.learning import discovery as learning_discovery
    from src.services.learning.learning_resource_service import LearningResourceService

    monkeypatch.setattr(learning_discovery.settings, "LEARNING_RESOURCE_PROVIDER", "seeded+dynamic", raising=False)
    monkeypatch.setattr(learning_discovery.settings, "LEARNING_RESOURCES_ENABLED", True, raising=False)
    monkeypatch.setattr(learning_discovery.settings, "LEARNING_RESOURCE_DISCOVERY_ENABLED", True, raising=False)
    monkeypatch.setattr(learning_discovery.settings, "LEARNING_WEB_SEARCH_ENABLED", True, raising=False)
    monkeypatch.setattr(learning_discovery.settings, "LEARNING_WEB_SEARCH_PROVIDER", "tavily", raising=False)
    monkeypatch.setattr(learning_discovery.settings, "TAVILY_API_KEY", "tvly-test", raising=False)

    class _FakeYouTubeClient:
        configured = False

    youtube_client = _FakeYouTubeClient()
    resource_service = LearningResourceService(
        youtube_client=youtube_client,
        discovery_providers=learning_discovery.build_default_discovery_providers(youtube_client, enabled=True),
    )
    health = resource_service.provider_health()
    assert health["web_search_backend"] == "tavily"
    assert health["search_backend"] == "tavily"
    web_provider = next(provider for provider in health["providers"] if provider["name"] == "web")
    assert web_provider["search_backend"] == "tavily"


@pytest.mark.asyncio
async def test_learning_resource_service_discovers_resources_from_live_provider_fallback():
    web_candidate = DiscoveryCandidate(
        skill_slug="tensorflow",
        skill_name="TensorFlow",
        title="TensorFlow Official Docs",
        provider="Web search",
        source_type="web_search_result",
        source_url="https://www.tensorflow.org/tutorials",
        channel_name="Web search",
        duration_minutes=None,
        difficulty="beginner",
        format="guide",
        is_free=True,
        language="en",
        trust_score=0.9,
        relevance_score=0.9,
        freshness_score=0.8,
        last_verified_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
        metadata={"step_type": "foundation"},
    )
    from src.services.learning.learning_resource_service import LearningResourceService

    resource_service = LearningResourceService(
        discovery_providers=[_FakeDiscoveryProvider("web", [web_candidate])],
    )
    discovered = await resource_service.discover_remote_resources("TensorFlow", "tensorflow", limit=3)
    assert len(discovered) == 1
    assert discovered[0].provider == "Web search"
    assert discovered[0].metadata["discovery_source"] == "web"
    assert discovered[0].metadata["verification_status"] in {"verified", "unverified"}


def test_learning_routes_require_auth():
    response = client.get("/api/v1/learning/paths")
    assert response.status_code == 401


def test_learning_routes_return_verified_payloads(authenticated_learning_routes):
    response = client.get("/api/v1/learning/skill-gaps")
    assert response.status_code == 200
    skill_gaps = response.json()
    assert skill_gaps["total_gaps"] == 1
    assert skill_gaps["gaps"][0]["skill_slug"] == "tensorflow"

    response = client.get("/api/v1/learning/paths")
    assert response.status_code == 200
    paths = response.json()
    assert paths["status"] == "ok"
    assert paths["paths"][0]["resource_status"] == "available"
    assert paths["paths"][0]["steps"][0]["resources"][0]["source_url"] == "https://www.tensorflow.org/tutorials"

    response = client.get("/api/v1/learning/paths/tensorflow")
    assert response.status_code == 200
    path = response.json()
    assert path["path"]["skill_name"] == "TensorFlow"
    assert path["path"]["resource_count"] == 1
    assert path["path"]["source_domains"] == ["www.tensorflow.org"]
    assert authenticated_learning_routes.last_get_path_args == {
        "skill_slug": "tensorflow",
        "force_refresh": False,
    }

    response = client.get("/api/v1/learning/paths/tensorflow?refresh=true")
    assert response.status_code == 200
    assert authenticated_learning_routes.last_get_path_args == {
        "skill_slug": "tensorflow",
        "force_refresh": True,
    }

    response = client.post("/api/v1/learning/paths/refresh", json={"limit": 5})
    assert response.status_code == 200
    refresh = response.json()
    assert refresh["refreshed_count"] == 1
    assert refresh["paths"][0]["skill_slug"] == "tensorflow"

    response = client.get("/api/v1/learning/paths?skills=aws,docker,sql&refresh=true")
    assert response.status_code == 200
    assert authenticated_learning_routes.last_list_paths_args == {
        "limit": 10,
        "skill_slugs": ["aws", "docker", "sql"],
        "force_refresh": True,
    }
