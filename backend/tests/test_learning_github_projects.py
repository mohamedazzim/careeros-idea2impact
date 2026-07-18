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
from src.integrations.github.repo_discovery import (
    GitHubIssueCandidate,
    GitHubProjectDiscoveryProvider,
    GitHubRepositoryCandidate,
    GitHubSkillDiscoveryResult,
)
from src.services.learning.github_project_service import GitHubProjectService
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


def _repo_payload(full_name: str, *, is_template: bool = False) -> dict[str, object]:
    name = full_name.split("/")[-1]
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "name": name,
        "description": f"{name} starter template",
        "language": "Python",
        "stargazers_count": 125,
        "forks_count": 17,
        "watchers_count": 42,
        "is_template": is_template,
        "archived": False,
        "updated_at": "2026-06-18T00:00:00Z",
    }


def _issue_payload(title: str, url: str, repo_full_name: str, *, pr: bool = False) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": title,
        "html_url": url,
        "repository_url": f"https://api.github.com/repos/{repo_full_name}",
        "labels": [{"name": "good first issue"}],
        "state": "open",
        "score": 7.5,
        "created_at": "2026-06-18T00:00:00Z",
        "updated_at": "2026-06-18T00:00:00Z",
    }
    if pr:
        payload["pull_request"] = {"url": url}
    return payload


class _FakeAsyncClient:
    def __init__(self, responder):
        self.responder = responder
        self.requests: list[dict[str, object]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None, params=None):
        headers = headers or {}
        params = params or {}
        self.requests.append({"url": url, "headers": headers, "params": params})
        status_code, body = self.responder(len(self.requests), url, headers, params)
        request = httpx.Request("GET", url)
        if isinstance(body, dict):
            return httpx.Response(status_code, request=request, json=body)
        return httpx.Response(status_code, request=request, content=str(body).encode("utf-8"))


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
        "job_id": 7,
        "job_context": {
            "job_id": 7,
            "title": "Cloud Engineer",
            "company": "CareerOS",
            "location": "Remote",
            "apply_url": "https://example.com/jobs/7",
            "source_url": "https://example.com/jobs/7",
            "match_score": 91.5,
            "missing_skill_slugs": ["aws", "docker"],
            "missing_skill_names": ["AWS", "Docker"],
        },
        "cached": False,
        "generated_at": "2026-06-19T00:00:00Z",
        "provider_health": {
            "enabled": True,
            "provider": "github",
            "provider_mode": "github_search_api",
            "status": "success",
            "cache_ttl_hours": 168,
            "min_results_per_skill": 3,
            "max_results_per_skill": 6,
            "issue_discovery_enabled": True,
            "token_configured": True,
            "message": "Using authenticated GitHub search.",
            "providers": [
                {
                    "name": "github",
                    "display_name": "GitHub search",
                    "status": "success",
                    "configured": True,
                    "enabled": True,
                    "last_result_count": 2,
                    "message": "Using authenticated GitHub search.",
                }
            ],
        },
        "source_status": "available",
        "skills": [
            {
                "skill_slug": "aws",
                "skill_name": "AWS",
                "count": 3,
                "priority": "high",
                "estimated_hours": 13.0,
                "reason": "AWS appears in 3 matched jobs across 1 roles; highest match score 91.5.",
                "source_job_ids": [7],
                "source_job_titles": ["Cloud Engineer"],
                "job_match_ids": [17],
                "repository_status": "available",
                "issue_status": "available",
                "source_status": "available",
                "repository_count": 1,
                "template_count": 1,
                "issue_count": 1,
                "repositories": [
                    {
                        "skill_slug": "aws",
                        "skill_name": "AWS",
                        "full_name": "octo/aws-service-template",
                        "html_url": "https://github.com/octo/aws-service-template",
                        "description": "AWS starter template",
                        "language": "Python",
                        "stargazers_count": 125,
                        "forks_count": 17,
                        "watchers_count": 42,
                        "is_template": True,
                        "archived": False,
                        "updated_at": "2026-06-18T00:00:00Z",
                        "matched_query": "aws",
                        "matched_terms": ["aws", "AWS"],
                        "source_status": "available",
                    }
                ],
                "templates": [
                    {
                        "skill_slug": "aws",
                        "skill_name": "AWS",
                        "full_name": "octo/aws-service-template",
                        "html_url": "https://github.com/octo/aws-service-template",
                        "description": "AWS starter template",
                        "language": "Python",
                        "stargazers_count": 125,
                        "forks_count": 17,
                        "watchers_count": 42,
                        "is_template": True,
                        "archived": False,
                        "updated_at": "2026-06-18T00:00:00Z",
                        "matched_query": "aws",
                        "matched_terms": ["aws", "AWS"],
                        "source_status": "available",
                    }
                ],
                "good_first_issues": [
                    {
                        "skill_slug": "aws",
                        "skill_name": "AWS",
                        "title": "Add a getting started guide",
                        "html_url": "https://github.com/octo/aws-service-template/issues/12",
                        "repository_full_name": "octo/aws-service-template",
                        "repository_html_url": "https://github.com/octo/aws-service-template",
                        "label_names": ["good first issue"],
                        "state": "open",
                        "score": 9.2,
                        "is_pull_request": False,
                        "created_at": "2026-06-18T00:00:00Z",
                        "updated_at": "2026-06-18T00:00:00Z",
                        "matched_terms": ["aws", "AWS"],
                        "source_status": "available",
                    }
                ],
                "search_queries": ["aws template in:name,description,readme fork:false archived:false stars:>0"],
                "errors": [],
            }
        ],
    }

    class _FakeService:
        async def build_github_projects(self, db, user_id: str, skills: list[str], job_id=None, force_refresh: bool = False):
            assert user_id == "user-123"
            assert skills == ["aws", "docker"]
            assert job_id == 7
            return fake_payload

    monkeypatch.setattr(learning_endpoint, "get_github_project_service", lambda: _FakeService())

    yield fake_payload

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


def test_learning_github_projects_routes_require_auth():
    response = client.get("/api/v1/learning/github-projects?skills=aws,docker")
    assert response.status_code == 401


def test_learning_github_projects_endpoint_returns_cards(authenticated_learning_routes):
    response = client.get("/api/v1/learning/github-projects?skills=aws,docker&job_id=7")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["job_context"]["title"] == "Cloud Engineer"
    assert payload["skills"][0]["repositories"][0]["html_url"].startswith("https://github.com/")
    assert payload["skills"][0]["good_first_issues"][0]["html_url"].startswith("https://github.com/")

    response = client.post("/api/v1/learning/github-projects/refresh", json={"skills": ["aws", "docker"], "job_id": 7})
    assert response.status_code == 200
    payload = response.json()
    assert payload["cached"] is False
    assert payload["source_status"] == "available"


@pytest.mark.asyncio
async def test_github_provider_uses_token_when_configured(monkeypatch):
    requests_seen: list[dict[str, object]] = []

    def responder(call_index: int, url: str, headers: dict[str, str], params: dict[str, object]):
        requests_seen.append({"url": url, "headers": headers, "params": params})
        if "/search/repositories" in url and call_index == 1:
            return 200, {"items": [_repo_payload("octo/aws-service-template", is_template=True)]}
        if "/search/repositories" in url and call_index == 2:
            return 200, {"items": [_repo_payload("octo/aws-example-app", is_template=False)]}
        if "/search/issues" in url:
            return 200, {
                "items": [
                    _issue_payload("Add a getting started guide", "https://github.com/octo/aws-service-template/issues/12", "octo/aws-service-template"),
                    _issue_payload(
                        "PR: update docs",
                        "https://github.com/octo/aws-service-template/pull/13",
                        "octo/aws-service-template",
                        pr=True,
                    ),
                ]
            }
        return 500, {"message": "unexpected call"}

    fake_client = _FakeAsyncClient(responder)
    monkeypatch.setattr("src.integrations.github.repo_discovery.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    provider = GitHubProjectDiscoveryProvider(token="github-token")
    result = await provider.discover_skill("aws", "AWS", limit=3)

    assert result.source_status == "available"
    assert result.repositories[0].full_name == "octo/aws-service-template"
    assert result.templates[0].is_template is True
    assert len(result.good_first_issues) == 1
    assert result.good_first_issues[0].html_url == "https://github.com/octo/aws-service-template/issues/12"
    assert any(str(request["headers"].get("Authorization", "")).startswith("Bearer github-token") for request in requests_seen)


@pytest.mark.asyncio
async def test_github_provider_anonymous_when_token_missing(monkeypatch):
    headers_seen: list[dict[str, str]] = []

    def responder(call_index: int, url: str, headers: dict[str, str], params: dict[str, object]):
        headers_seen.append(headers)
        if "/search/repositories" in url:
            return 200, {"items": [_repo_payload("octo/docker-starter", is_template=True)]}
        if "/search/issues" in url:
            return 200, {"items": []}
        return 500, {"message": "unexpected call"}

    fake_client = _FakeAsyncClient(responder)
    monkeypatch.setattr("src.integrations.github.repo_discovery.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    provider = GitHubProjectDiscoveryProvider(token=None)
    result = await provider.discover_skill("docker", "Docker", limit=3)

    assert result.source_status in {"available", "partial"}
    assert headers_seen and "Authorization" not in headers_seen[0]


@pytest.mark.asyncio
async def test_github_rate_limit_returns_source_status_not_500(monkeypatch):
    def responder(call_index: int, url: str, headers: dict[str, str], params: dict[str, object]):
        if "/search/repositories" in url:
            return 403, {"message": "API rate limit exceeded"}
        return 200, {"items": []}

    fake_client = _FakeAsyncClient(responder)
    monkeypatch.setattr("src.integrations.github.repo_discovery.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    provider = GitHubProjectDiscoveryProvider(token="github-token")
    result = await provider.discover_skill("aws", "AWS", limit=3)

    assert result.source_status == "rate_limited"
    assert result.repositories == []
    assert result.good_first_issues == []


@pytest.mark.asyncio
async def test_github_service_keeps_available_skills_when_one_skill_fails(monkeypatch):
    class _FakeProvider:
        def provider_health(self) -> dict[str, object]:
            return {
                "enabled": True,
                "provider": "github",
                "provider_mode": "github_search_api",
                "status": "success",
                "cache_ttl_hours": 168,
                "min_results_per_skill": 3,
                "max_results_per_skill": 6,
                "issue_discovery_enabled": True,
                "token_configured": False,
            }

        async def discover_skill(self, skill_slug: str, skill_name: str, limit: int = 6):
            if skill_slug == "docker":
                return GitHubSkillDiscoveryResult(
                    skill_slug=skill_slug,
                    skill_name=skill_name,
                    source_status="not_available",
                    repositories=[],
                    templates=[],
                    good_first_issues=[],
                    search_queries=[],
                    errors=["rate limit"],
                )
            repo = GitHubRepositoryCandidate(
                skill_slug=skill_slug,
                skill_name=skill_name,
                full_name=f"octo/{skill_slug}-starter",
                html_url=f"https://github.com/octo/{skill_slug}-starter",
                description=f"{skill_name} starter",
                language="Python",
                stargazers_count=100,
                forks_count=5,
                watchers_count=10,
                is_template=True,
                archived=False,
                updated_at="2026-06-18T00:00:00Z",
                matched_query=skill_slug,
                matched_terms=[skill_slug],
            )
            issue = GitHubIssueCandidate(
                skill_slug=skill_slug,
                skill_name=skill_name,
                title=f"Improve {skill_name} onboarding",
                html_url=f"https://github.com/octo/{skill_slug}-starter/issues/1",
                repository_full_name=f"octo/{skill_slug}-starter",
                repository_html_url=f"https://github.com/octo/{skill_slug}-starter",
                label_names=["good first issue"],
                state="open",
                score=5.0,
                is_pull_request=False,
                created_at="2026-06-18T00:00:00Z",
                updated_at="2026-06-18T00:00:00Z",
                matched_terms=[skill_slug],
            )
            return GitHubSkillDiscoveryResult(
                skill_slug=skill_slug,
                skill_name=skill_name,
                source_status="available",
                repositories=[repo],
                templates=[repo],
                good_first_issues=[issue],
                search_queries=[skill_slug],
                errors=[],
            )

    class _SkillAwarePathService(LearningPathService):
        async def aggregate_skill_gaps(self, db, user_id: str, limit: int = 10):
            return [
                SkillGapAggregate(
                    skill_slug="aws",
                    skill_name="AWS",
                    count=2,
                    source_job_ids=[1],
                    source_job_titles=["Cloud Engineer"],
                    job_match_ids=[2],
                    max_match_score=90.0,
                    latest_match_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
                ),
                SkillGapAggregate(
                    skill_slug="docker",
                    skill_name="Docker",
                    count=1,
                    source_job_ids=[3],
                    source_job_titles=["Platform Engineer"],
                    job_match_ids=[4],
                    max_match_score=78.0,
                    latest_match_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
                ),
            ][:limit]

    service = GitHubProjectService(
        learning_path_service=_SkillAwarePathService(),
        github_provider=_FakeProvider(),
    )

    payload = await service.build_github_projects(SimpleNamespace(), "user-123", ["aws", "docker"], job_id=None)

    assert payload["status"] == "ok"
    assert [skill["skill_slug"] for skill in payload["skills"]] == ["aws", "docker"]
    assert payload["skills"][0]["source_status"] == "available"
    assert payload["skills"][1]["source_status"] == "not_available"
    assert payload["skills"][0]["repositories"][0]["html_url"].startswith("https://github.com/")


@pytest.mark.asyncio
async def test_github_project_service_loads_single_job_match_even_when_duplicates_exist():
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
        overall_score=88.0,
        gaps=[{"skill": "AWS"}],
        match_details={"missing_skills": ["docker"], "job_extraction": {"skills": ["react"]}},
    )

    class _FakeProvider:
        def provider_health(self) -> dict[str, object]:
            return {
                "enabled": True,
                "provider": "github",
                "provider_mode": "github_search_api",
                "status": "success",
                "cache_ttl_hours": 168,
                "min_results_per_skill": 3,
                "max_results_per_skill": 6,
                "issue_discovery_enabled": True,
                "token_configured": False,
            }

        async def discover_skill(self, skill_slug: str, skill_name: str, limit: int = 6):
            return GitHubSkillDiscoveryResult(
                skill_slug=skill_slug,
                skill_name=skill_name,
                source_status="not_available",
                repositories=[],
                templates=[],
                good_first_issues=[],
                search_queries=[],
                errors=[],
            )

    class _SkillAwarePathService(LearningPathService):
        async def aggregate_skill_gaps(self, db, user_id: str, limit: int = 10):
            return []

    service = GitHubProjectService(
        learning_path_service=_SkillAwarePathService(),
        github_provider=_FakeProvider(),
    )

    payload = await service._load_job_context(_FakeJobContextDB(job, match, duplicate_match_rows=True), "user-123", 17589)

    assert payload["job_id"] == 17589
    assert payload["missing_skill_slugs"] == ["aws", "docker", "react"]


def test_github_projects_refresh_rejects_missing_body_with_400():
    response = client.post("/api/v1/learning/github-projects/refresh", headers=_user_auth_headers())
    assert response.status_code == 400


def test_github_projects_invalid_job_id_returns_404_not_500(monkeypatch):
    class _MissingJobService:
        async def build_github_projects(self, db, user_id: str, skills: list[str], job_id=None, force_refresh: bool = False):
            raise ValueError("Job not found")

    original_overrides = dict(app.dependency_overrides)

    async def _override_user():
        return {"sub": "user-123", "role": "User"}

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    monkeypatch.setattr(learning_endpoint, "get_github_project_service", lambda: _MissingJobService())

    response = client.get("/api/v1/learning/github-projects?skills=aws,azure,javascript,react&job_id=17589")

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)

    assert response.status_code == 404
