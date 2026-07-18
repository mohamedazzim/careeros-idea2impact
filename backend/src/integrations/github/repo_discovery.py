"""Real GitHub repository and issue discovery for learning skill gaps."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import logging
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
GITHUB_USER_AGENT = "CareerOS-GitHub-Discovery/1.0"


class GitHubDiscoveryError(RuntimeError):
    """Base class for GitHub search failures."""


class GitHubRateLimitError(GitHubDiscoveryError):
    """Raised when GitHub search has been rate limited."""


@dataclass(slots=True)
class GitHubRepositoryCandidate:
    skill_slug: str
    skill_name: str
    full_name: str
    html_url: str
    description: Optional[str]
    language: Optional[str]
    stargazers_count: int
    forks_count: int
    watchers_count: int
    is_template: bool
    archived: bool
    updated_at: Optional[str]
    matched_query: str
    matched_terms: list[str]
    source_status: str = "available"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GitHubIssueCandidate:
    skill_slug: str
    skill_name: str
    title: str
    html_url: str
    repository_full_name: str
    repository_html_url: str
    label_names: list[str]
    state: str
    score: float
    is_pull_request: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    matched_terms: list[str]
    source_status: str = "available"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GitHubSkillDiscoveryResult:
    skill_slug: str
    skill_name: str
    source_status: str
    repositories: list[GitHubRepositoryCandidate]
    templates: list[GitHubRepositoryCandidate]
    good_first_issues: list[GitHubIssueCandidate]
    search_queries: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_slug": self.skill_slug,
            "skill_name": self.skill_name,
            "source_status": self.source_status,
            "repositories": [item.to_dict() for item in self.repositories],
            "templates": [item.to_dict() for item in self.templates],
            "good_first_issues": [item.to_dict() for item in self.good_first_issues],
            "search_queries": list(self.search_queries),
            "errors": list(self.errors),
        }


_DEFAULT_TOKEN = object()


def _quote_term(term: str) -> str:
    cleaned = term.strip()
    if not cleaned:
        return cleaned
    if any(char in cleaned for char in [" ", "+", "/", "-"]):
        return f'"{cleaned}"'
    return cleaned


def _github_repo_name(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return url


class GitHubProjectDiscoveryProvider:
    def __init__(
        self,
        token: Optional[str] | object = _DEFAULT_TOKEN,
        enabled: Optional[bool] = None,
        issue_discovery_enabled: Optional[bool] = None,
        cache_ttl_hours: Optional[int] = None,
        min_results_per_skill: Optional[int] = None,
        max_results_per_skill: Optional[int] = None,
        base_url: str = GITHUB_API_BASE_URL,
        timeout_seconds: float = 20.0,
    ) -> None:
        if token is _DEFAULT_TOKEN:
            self.token = settings.GITHUB_TOKEN
        else:
            self.token = token
        self.enabled = settings.GITHUB_REPO_DISCOVERY_ENABLED if enabled is None else enabled
        self.issue_discovery_enabled = (
            settings.GITHUB_ISSUE_DISCOVERY_ENABLED if issue_discovery_enabled is None else issue_discovery_enabled
        )
        self.cache_ttl_hours = settings.GITHUB_REPO_CACHE_TTL_HOURS if cache_ttl_hours is None else cache_ttl_hours
        self.min_results_per_skill = (
            settings.GITHUB_REPO_MIN_RESULTS_PER_SKILL if min_results_per_skill is None else min_results_per_skill
        )
        self.max_results_per_skill = (
            settings.GITHUB_REPO_MAX_RESULTS_PER_SKILL if max_results_per_skill is None else max_results_per_skill
        )
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._fallback_to_anonymous = False

    def provider_health(self) -> dict[str, Any]:
        if not self.enabled:
            status = "skipped"
            message = "GitHub project discovery is disabled."
        elif self.token:
            status = "success" if not self._fallback_to_anonymous else "partial"
            message = (
                "Using authenticated GitHub search."
                if not self._fallback_to_anonymous
                else "GitHub token fallback to anonymous public search was used."
            )
        else:
            status = "success"
            message = "Using public GitHub search without a token; rate limits are lower."

        return {
            "enabled": self.enabled,
            "provider": "github",
            "provider_mode": "github_search_api",
            "status": status,
            "cache_ttl_hours": self.cache_ttl_hours,
            "min_results_per_skill": self.min_results_per_skill,
            "max_results_per_skill": self.max_results_per_skill,
            "issue_discovery_enabled": self.issue_discovery_enabled,
            "token_configured": bool(self.token),
            "message": message,
            "providers": [
                {
                    "name": "github",
                    "display_name": "GitHub search",
                    "status": status,
                    "configured": bool(self.token),
                    "enabled": self.enabled,
                    "last_result_count": None,
                    "message": message,
                }
            ],
        }

    def _headers(self, use_auth: bool = True) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": GITHUB_USER_AGENT,
        }
        if use_auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict[str, Any],
        use_auth: bool = True,
    ) -> dict[str, Any]:
        response = await client.get(
            f"{self.base_url}{path}",
            headers=self._headers(use_auth=use_auth),
            params=params,
        )
        body: dict[str, Any] = {}
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    body = payload
            except Exception:
                body = {}

        if response.status_code in {403, 429}:
            message = str(body.get("message") or response.text or "GitHub rate limit exceeded")
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining == "0" or "rate limit" in message.lower():
                raise GitHubRateLimitError(message)
            raise GitHubDiscoveryError(message)

        if response.status_code == 401:
            message = str(body.get("message") or response.text or "GitHub authorization failed")
            raise GitHubDiscoveryError(message)

        response.raise_for_status()
        return body

    def _skill_search_term(self, skill_slug: str, skill_name: str) -> str:
        lookup = skill_slug.strip().lower()
        if lookup in {"cpp", "c++"}:
            return 'cpp OR "c++"'
        if lookup in {"ci-cd", "ci cd", "ci/cd"}:
            return '"ci/cd" OR "ci-cd" OR "ci cd"'
        if lookup in {"javascript", "js", "java script"}:
            return '"javascript" OR js'
        if lookup in {"java", "core java", "java programming", "java se", "jdk", "openjdk"}:
            return "java"
        return _quote_term(skill_name or skill_slug)

    def _repo_query(self, term: str, variant: str) -> str:
        if variant == "template":
            return f"({term}) template in:name,description,readme fork:false archived:false stars:>0"
        return f"({term}) in:name,description,readme fork:false archived:false stars:>0"

    def _issue_query(self, term: str) -> str:
        return f"({term}) is:issue state:open label:\"good first issue\",\"help wanted\""

    def _repo_sort_key(self, item: dict[str, Any]) -> tuple[float, float, str]:
        name = str(item.get("name") or "").lower()
        description = str(item.get("description") or "").lower()
        stars = float(item.get("stargazers_count") or 0)
        score = stars
        if any(marker in name or marker in description for marker in ["template", "starter", "boilerplate", "example", "blueprint"]):
            score += 200.0
        if bool(item.get("is_template")):
            score += 300.0
        if bool(item.get("archived")):
            score -= 500.0
        updated_at = str(item.get("updated_at") or "")
        return (score, stars, updated_at)

    def _issue_score(self, item: dict[str, Any]) -> float:
        score = float(item.get("score") or 0.0)
        labels = [str(label.get("name") or "").lower() for label in item.get("labels", []) if isinstance(label, dict)]
        if "good first issue" in labels:
            score += 25.0
        if "help wanted" in labels:
            score += 10.0
        return score

    def _normalize_repository(self, skill_slug: str, skill_name: str, item: dict[str, Any], query: str) -> GitHubRepositoryCandidate:
        name = str(item.get("name") or "")
        description = item.get("description")
        matched_terms = [skill_slug]
        if skill_name and skill_name.lower() != skill_slug.lower():
            matched_terms.append(skill_name)
        return GitHubRepositoryCandidate(
            skill_slug=skill_slug,
            skill_name=skill_name,
            full_name=str(item.get("full_name") or name),
            html_url=str(item.get("html_url") or ""),
            description=str(description) if description is not None else None,
            language=str(item.get("language") or None),
            stargazers_count=int(item.get("stargazers_count") or 0),
            forks_count=int(item.get("forks_count") or 0),
            watchers_count=int(item.get("watchers_count") or item.get("subscribers_count") or 0),
            is_template=bool(item.get("is_template") or any(marker in name.lower() for marker in ["template", "starter", "boilerplate"])),
            archived=bool(item.get("archived") or False),
            updated_at=str(item.get("updated_at") or None),
            matched_query=query,
            matched_terms=matched_terms,
        )

    def _normalize_issue(self, skill_slug: str, skill_name: str, item: dict[str, Any], query: str) -> GitHubIssueCandidate:
        labels = [str(label.get("name") or "") for label in item.get("labels", []) if isinstance(label, dict)]
        repository_url = str(item.get("repository_url") or "")
        repository_html_url = repository_url.replace("https://api.github.com/repos/", "https://github.com/")
        repository_full_name = _github_repo_name(repository_url)
        matched_terms = [skill_slug]
        if skill_name and skill_name.lower() != skill_slug.lower():
            matched_terms.append(skill_name)
        return GitHubIssueCandidate(
            skill_slug=skill_slug,
            skill_name=skill_name,
            title=str(item.get("title") or ""),
            html_url=str(item.get("html_url") or ""),
            repository_full_name=repository_full_name,
            repository_html_url=repository_html_url,
            label_names=labels,
            state=str(item.get("state") or "open"),
            score=self._issue_score(item),
            is_pull_request=bool(item.get("pull_request")),
            created_at=str(item.get("created_at") or None),
            updated_at=str(item.get("updated_at") or None),
            matched_terms=matched_terms,
        )

    async def _search_repositories(
        self,
        client: httpx.AsyncClient,
        query: str,
        per_page: int,
        use_auth: bool = True,
    ) -> list[dict[str, Any]]:
        payload = await self._request_json(
            client,
            "/search/repositories",
            {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": per_page,
            },
            use_auth=use_auth,
        )
        return list(payload.get("items") or [])

    async def _search_issues(
        self,
        client: httpx.AsyncClient,
        query: str,
        per_page: int,
        use_auth: bool = True,
    ) -> list[dict[str, Any]]:
        payload = await self._request_json(
            client,
            "/search/issues",
            {
                "q": query,
                "sort": "updated",
                "order": "desc",
                "per_page": per_page,
            },
            use_auth=use_auth,
        )
        return list(payload.get("items") or [])

    async def discover_skill(self, skill_slug: str, skill_name: str, limit: Optional[int] = None) -> GitHubSkillDiscoveryResult:
        if not self.enabled:
            return GitHubSkillDiscoveryResult(
                skill_slug=skill_slug,
                skill_name=skill_name,
                source_status="not_available",
                repositories=[],
                templates=[],
                good_first_issues=[],
                search_queries=[],
                errors=["GitHub discovery is disabled."],
            )

        effective_limit = max(self.min_results_per_skill, min(limit or self.max_results_per_skill, self.max_results_per_skill))
        skill_term = self._skill_search_term(skill_slug, skill_name)
        repo_queries = [self._repo_query(skill_term, "template"), self._repo_query(skill_term, "project")]
        issue_queries = [self._issue_query(skill_term)] if self.issue_discovery_enabled else []

        repo_candidates: list[GitHubRepositoryCandidate] = []
        issue_candidates: list[GitHubIssueCandidate] = []
        errors: list[str] = []
        source_status = "not_available"
        use_auth = bool(self.token)

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for query in repo_queries:
                try:
                    items = await self._search_repositories(client, query, effective_limit, use_auth=use_auth)
                except GitHubRateLimitError as exc:
                    errors.append(str(exc))
                    source_status = "rate_limited"
                    break
                except GitHubDiscoveryError as exc:
                    errors.append(str(exc))
                    if self.token and not self._fallback_to_anonymous and "token" in str(exc).lower():
                        self._fallback_to_anonymous = True
                        use_auth = False
                        try:
                            items = await self._search_repositories(client, query, effective_limit, use_auth=False)
                        except Exception as retry_exc:
                            errors.append(str(retry_exc))
                            source_status = "partial" if repo_candidates else "not_available"
                            continue
                    else:
                        source_status = "partial" if repo_candidates else "not_available"
                        continue
                except Exception as exc:  # pragma: no cover - defensive guard
                    logger.warning("GitHub repository search failed for %s: %s", skill_slug, exc)
                    errors.append(str(exc))
                    source_status = "partial" if repo_candidates else "not_available"
                    continue

                for item in items:
                    candidate = self._normalize_repository(skill_slug, skill_name, item, query)
                    repo_candidates.append(candidate)

            if self.issue_discovery_enabled and source_status != "rate_limited":
                for query in issue_queries:
                    try:
                        items = await self._search_issues(client, query, effective_limit, use_auth=use_auth)
                    except GitHubRateLimitError as exc:
                        errors.append(str(exc))
                        source_status = "rate_limited"
                        break
                    except GitHubDiscoveryError as exc:
                        errors.append(str(exc))
                        if self.token and not self._fallback_to_anonymous and "token" in str(exc).lower():
                            self._fallback_to_anonymous = True
                            use_auth = False
                            try:
                                items = await self._search_issues(client, query, effective_limit, use_auth=False)
                            except Exception as retry_exc:
                                errors.append(str(retry_exc))
                                source_status = "partial" if (repo_candidates or issue_candidates) else "not_available"
                                continue
                        else:
                            source_status = "partial" if (repo_candidates or issue_candidates) else "not_available"
                            continue
                    except Exception as exc:  # pragma: no cover - defensive guard
                        logger.warning("GitHub issue search failed for %s: %s", skill_slug, exc)
                        errors.append(str(exc))
                        source_status = "partial" if (repo_candidates or issue_candidates) else "not_available"
                        continue

                    for item in items:
                        if item.get("pull_request"):
                            continue
                        issue_candidates.append(self._normalize_issue(skill_slug, skill_name, item, query))

        deduped_repos: dict[str, GitHubRepositoryCandidate] = {}
        for candidate in repo_candidates:
            existing = deduped_repos.get(candidate.full_name)
            if existing is None:
                deduped_repos[candidate.full_name] = candidate
                continue
            if self._repo_sort_key(candidate.to_dict()) > self._repo_sort_key(existing.to_dict()):
                deduped_repos[candidate.full_name] = candidate

        repositories = sorted(
            deduped_repos.values(),
            key=lambda item: self._repo_sort_key(item.to_dict()),
            reverse=True,
        )[:effective_limit]
        templates = [item for item in repositories if item.is_template or any(marker in item.full_name.lower() for marker in ["template", "starter", "boilerplate"])]
        good_first_issues = sorted(issue_candidates, key=lambda item: item.score, reverse=True)[:effective_limit]

        if source_status == "not_available":
            if repositories and good_first_issues:
                source_status = "available"
            elif repositories or good_first_issues:
                source_status = "partial"

        return GitHubSkillDiscoveryResult(
            skill_slug=skill_slug,
            skill_name=skill_name,
            source_status=source_status,
            repositories=repositories,
            templates=templates,
            good_first_issues=good_first_issues,
            search_queries=repo_queries + issue_queries,
            errors=errors,
        )


@lru_cache(maxsize=1)
def get_github_project_discovery_provider() -> GitHubProjectDiscoveryProvider:
    return GitHubProjectDiscoveryProvider(token=settings.GITHUB_TOKEN)
