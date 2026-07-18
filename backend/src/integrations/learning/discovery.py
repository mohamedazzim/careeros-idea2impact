"""Real learning-resource discovery providers.

The learning path flow uses a small provider abstraction so we can mix curated
seeded resources with live discovery from public sources without baking any one
search surface into the service layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import html
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional, Protocol
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from src.core.config import settings
from src.integrations.youtube.client import YouTubeLearningClient, YouTubeQuotaExceededError
from src.services.learning.skill_normalizer import canonical_display_name, normalize_skill

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)

_WEB_TRUSTED_DOMAINS = {
    "aws.amazon.com",
    "docs.aws.amazon.com",
    "dev.java",
    "docs.oracle.com",
    "oracle.com",
    "openjdk.org",
    "spring.io",
    "jetbrains.com",
    "freecodecamp.org",
    "learn.microsoft.com",
    "codecademy.com",
    "edx.org",
    "developer.mozilla.org",
    "docs.docker.com",
    "fastapi.tiangolo.com",
    "git-scm.com",
    "kubernetes.io",
    "www.postgresql.org",
    "python.langchain.com",
    "docs.langchain.com",
    "react.dev",
    "www.tensorflow.org",
    "docs.pytorch.org",
    "www.youtube.com",
    "coursera.org",
    "www.coursera.org",
    "udemy.com",
    "www.udemy.com",
}

_SUPPORTED_WEB_SEARCH_BACKENDS = {"bing", "tavily", "serpapi"}


def _normalize_web_search_backend(value: str | None) -> str:
    backend = (value or "").strip().lower()
    if backend in {"", "brave"}:
        return "bing"
    if backend in _SUPPORTED_WEB_SEARCH_BACKENDS:
        return backend
    return "bing"


@dataclass(slots=True)
class DiscoveryCandidate:
    skill_slug: str
    skill_name: str
    title: str
    provider: str
    source_type: str
    source_url: str
    channel_name: Optional[str] = None
    duration_minutes: Optional[int] = None
    difficulty: Optional[str] = None
    format: Optional[str] = None
    is_free: bool = True
    language: str = "en"
    trust_score: float = 0.75
    relevance_score: float = 0.75
    freshness_score: float = 0.5
    last_verified_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SearchItem:
    title: str
    url: str
    description: str
    published_at: Optional[datetime] = None


class DiscoveryProvider(Protocol):
    name: str

    def health(self) -> dict[str, Any]: ...

    async def discover(self, skill_name: str, skill_slug: str, limit: int = 5) -> list[DiscoveryCandidate]: ...


def _simplify_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", value.lower())).strip()


def _domain_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    return parsed.netloc.lower()


def _domain_matches(url: str, allowed_domains: set[str]) -> bool:
    if not allowed_domains:
        return True
    host = _domain_from_url(url)
    if not host:
        return False
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def _extract_redirect_target(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    if parsed.netloc.endswith("bing.com") and parsed.path == "/aclick":
        params = parse_qs(parsed.query)
        redirect = params.get("u", [""])[0]
        return unquote(redirect) if redirect else url
    return url


def _looks_free(title: str, description: str, url: str) -> bool:
    combined = f"{title} {description} {url}".lower()
    free_markers = {
        "free",
        "audit",
        "no cost",
        "open source",
        "learn for free",
        "enroll for free",
    }
    return any(marker in combined for marker in free_markers)


def _price_status_for_candidate(provider_name: str, free_verified: bool, verified: bool) -> str:
    if provider_name in {"coursera", "udemy"}:
        if free_verified and verified:
            return "verified_free"
        if verified:
            return "verified_paid_or_unknown"
        return "unverified"
    if free_verified:
        return "free"
    return "paid_or_unknown"


def _is_relevant(skill_name: str, title: str, description: str) -> bool:
    normalized_skill = _simplify_text(skill_name)
    if not normalized_skill:
        return True
    title_text = _simplify_text(title)
    description_text = _simplify_text(description)
    tokens = [token for token in normalized_skill.split() if len(token) > 1]
    if not tokens:
        return True
    hit_count = sum(1 for token in tokens if token in title_text or token in description_text)
    return hit_count > 0


def _parse_bing_rss_payload(text: str) -> list[SearchItem]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        logger.warning("Failed to parse Bing RSS payload: %s", exc)
        return []

    items: list[SearchItem] = []
    for item in root.findall("./channel/item"):
        title = html.unescape((item.findtext("title") or "").strip())
        link = html.unescape((item.findtext("link") or "").strip())
        description = html.unescape((item.findtext("description") or "").strip())
        if not title or not link:
            continue
        published_raw = (item.findtext("pubDate") or "").strip()
        published_at: Optional[datetime] = None
        if published_raw:
            try:
                published_at = datetime.strptime(published_raw, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
            except ValueError:
                published_at = datetime.now(timezone.utc)
        items.append(SearchItem(title=title, url=link, description=description, published_at=published_at))
    return items


class BingSearchDiscoveryProvider:
    """Searches Bing RSS for public learning resources on named domains."""

    def __init__(
        self,
        name: str,
        display_name: str,
        query_templates: tuple[str, ...],
        allowed_domains: tuple[str, ...],
        source_type: str,
        format: str,
        step_type: str,
        trust_score: float,
        relevance_score: float,
        freshness_score: float,
        search_backend: str = "bing",
        require_free_signal: bool = False,
        channel_name: Optional[str] = None,
        is_free: bool = True,
        timeout_seconds: int = 20,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.display_name = display_name
        self.query_templates = query_templates
        self.allowed_domains = tuple(sorted({domain.lower() for domain in allowed_domains if domain}))
        self.source_type = source_type
        self.format = format
        self.step_type = step_type
        self.trust_score = trust_score
        self.relevance_score = relevance_score
        self.freshness_score = freshness_score
        self.search_backend = _normalize_web_search_backend(search_backend)
        self.require_free_signal = require_free_signal
        self.channel_name = channel_name
        self.is_free = is_free
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled
        self.last_error: Optional[str] = None
        self.last_checked_at: Optional[datetime] = None
        self.last_success_at: Optional[datetime] = None
        self.last_result_count: int = 0
        self.last_status: str = "skipped"

    def _backend_configured(self) -> bool:
        if self.search_backend == "tavily":
            return bool(settings.TAVILY_API_KEY)
        if self.search_backend == "serpapi":
            return bool(settings.SERPAPI_API_KEY)
        return True

    def health(self) -> dict[str, Any]:
        status = self.last_status
        if not self.enabled:
            status = "skipped"
        elif not self._backend_configured():
            status = "missing_api_key"
        elif self.last_checked_at and not self.last_error and status == "skipped":
            status = "success"
        if not self.enabled:
            message = "Provider disabled."
        elif not self._backend_configured():
            if self.search_backend == "tavily":
                message = "TAVILY_API_KEY is not configured."
            elif self.search_backend == "serpapi":
                message = "SERPAPI_API_KEY is not configured."
            else:
                message = "Search backend is not configured."
        elif status == "success":
            message = "Verified results returned for this provider." if self.last_result_count else "No verified results returned for this query yet."
        elif status == "error":
            message = self.last_error or "Discovery failed."
        else:
            message = "Discovery has not run yet."
        return {
            "name": self.name,
            "display_name": self.display_name,
            "status": status,
            "configured": self.enabled and self._backend_configured(),
            "enabled": self.enabled,
            "search_backend": self.search_backend,
            "allowed_domains": list(self.allowed_domains),
            "query_templates": list(self.query_templates),
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_error": self.last_error,
            "last_result_count": self.last_result_count,
            "message": message,
        }

    async def _search_bing(self, client: httpx.AsyncClient, query: str) -> list[SearchItem]:
        response = await client.get(
            "https://www.bing.com/search",
            params={"q": query, "format": "rss"},
            headers={"User-Agent": _DEFAULT_USER_AGENT},
        )
        response.raise_for_status()
        return _parse_bing_rss_payload(response.text)

    async def _search_tavily(self, client: httpx.AsyncClient, query: str, limit: int) -> list[SearchItem]:
        payload: dict[str, Any] = {
            "query": query,
            "search_depth": "basic",
            "max_results": max(1, min(limit, 10)),
            "include_answer": False,
            "include_images": False,
            "include_raw_content": False,
            "include_favicon": True,
        }
        domains = [domain for domain in self.allowed_domains if domain]
        if domains:
            payload["include_domains"] = domains[:10]
        response = await client.post(
            "https://api.tavily.com/search",
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.TAVILY_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": _DEFAULT_USER_AGENT,
            },
        )
        response.raise_for_status()
        body = response.json()
        items: list[SearchItem] = []
        for item in body.get("results", []) or []:
            if not isinstance(item, dict):
                continue
            title = html.unescape(str(item.get("title") or "").strip())
            url = html.unescape(str(item.get("url") or "").strip())
            description = html.unescape(str(item.get("content") or item.get("snippet") or "").strip())
            if not title or not url:
                continue
            items.append(SearchItem(title=title, url=url, description=description))
        return items

    async def _search_serpapi(self, client: httpx.AsyncClient, query: str, limit: int) -> list[SearchItem]:
        response = await client.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": query,
                "api_key": settings.SERPAPI_API_KEY,
                "num": max(1, min(limit, 10)),
                "hl": "en",
                "gl": "us",
            },
            headers={"User-Agent": _DEFAULT_USER_AGENT},
        )
        response.raise_for_status()
        body = response.json()
        items: list[SearchItem] = []
        for item in body.get("organic_results", []) or []:
            if not isinstance(item, dict):
                continue
            title = html.unescape(str(item.get("title") or "").strip())
            url = html.unescape(str(item.get("link") or "").strip())
            description = html.unescape(str(item.get("snippet") or "").strip())
            if not title or not url:
                continue
            items.append(SearchItem(title=title, url=url, description=description))
        return items

    async def _search(self, client: httpx.AsyncClient, query: str, limit: int) -> list[SearchItem]:
        if self.search_backend == "tavily":
            return await self._search_tavily(client, query, limit)
        if self.search_backend == "serpapi":
            return await self._search_serpapi(client, query, limit)
        return await self._search_bing(client, query)

    async def _verify_url(self, client: httpx.AsyncClient, url: str) -> bool:
        try:
            response = await client.get(
                url,
                headers={"User-Agent": _DEFAULT_USER_AGENT},
                follow_redirects=True,
                timeout=self.timeout_seconds,
            )
            return response.status_code < 400
        except Exception as exc:
            self.last_error = f"verification failed for {url}: {exc}"
            return False

    async def discover(self, skill_name: str, skill_slug: str, limit: int = 5) -> list[DiscoveryCandidate]:
        if not self.enabled:
            self.last_status = "skipped"
            return []
        if not self._backend_configured():
            self.last_status = "missing_api_key"
            return []

        normalized_skill = normalize_skill(skill_name)
        resolved_skill_name = normalized_skill.display_name or skill_name or canonical_display_name(skill_slug)
        queries = [
            template.format(skill_name=resolved_skill_name, skill_slug=skill_slug, skill_phrase=_simplify_text(resolved_skill_name))
            for template in self.query_templates
        ]

        candidates: list[DiscoveryCandidate] = []
        seen_urls: set[str] = set()
        self.last_checked_at = datetime.now(timezone.utc)
        self.last_error = None
        self.last_status = "skipped"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                for query in queries:
                    try:
                        results = await self._search(client, query, limit=limit)
                    except Exception as exc:
                        self.last_error = str(exc)
                        self.last_status = "error"
                        logger.info(
                            "%s lookup failed for provider=%s skill=%s query=%s: %s",
                            self.search_backend,
                            self.name,
                            skill_slug,
                            query,
                            exc,
                        )
                        continue

                    for item in results:
                        if len(candidates) >= limit:
                            break

                        target_url = _extract_redirect_target(item.url.strip())
                        if not target_url or target_url in seen_urls:
                            continue
                        if not _domain_matches(target_url, set(self.allowed_domains)):
                            continue
                        if self.require_free_signal and not _looks_free(item.title, item.description, target_url):
                            continue
                        if not _is_relevant(resolved_skill_name, item.title, item.description):
                            continue
                        verified = await self._verify_url(client, target_url)
                        if not verified:
                            continue
                        free_verified = _looks_free(item.title, item.description, target_url)

                        seen_urls.add(target_url)
                        last_verified_at = datetime.now(timezone.utc)
                        if item.published_at and item.published_at > last_verified_at:
                            last_verified_at = item.published_at
                        candidates.append(
                            DiscoveryCandidate(
                                skill_slug=skill_slug,
                                skill_name=resolved_skill_name,
                                title=item.title,
                                provider=self.display_name,
                                source_type=self.source_type,
                                source_url=target_url,
                                channel_name=self.channel_name or _domain_from_url(target_url) or None,
                                duration_minutes=None,
                                difficulty="beginner",
                                format=self.format,
                                is_free=free_verified if self.require_free_signal else self.is_free,
                                language="en",
                                trust_score=self.trust_score,
                                relevance_score=self.relevance_score,
                                freshness_score=self.freshness_score,
                                last_verified_at=last_verified_at,
                                metadata={
                                    "step_type": self.step_type,
                                    "discovery_source": self.name,
                                    "discovered_by": self.display_name,
                                    "verification_status": "verified" if verified else "unverified",
                                    "price_status": _price_status_for_candidate(self.name, free_verified, verified),
                                    "search_backend": self.search_backend,
                                    "search_query": query,
                                    "source_domain": _domain_from_url(target_url),
                                },
                            )
                        )
                        self.last_status = "success"
                        if len(candidates) >= limit:
                            break
        finally:
            self.last_result_count = len(candidates)
            if candidates:
                self.last_success_at = datetime.now(timezone.utc)
                self.last_status = "success"
            elif self.last_checked_at and not self.last_error:
                self.last_status = "success"

        return candidates[:limit]


class YouTubeDiscoveryProvider:
    """Wraps the YouTube API client behind the same discovery protocol."""

    name = "youtube"

    def __init__(self, youtube_client: YouTubeLearningClient, enabled: bool = True) -> None:
        self.youtube_client = youtube_client
        self.enabled = enabled
        self.last_checked_at: Optional[datetime] = None
        self.last_success_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.last_result_count: int = 0
        self.last_status: str = "skipped"

    def health(self) -> dict[str, Any]:
        if not self.enabled:
            status = "skipped"
        elif not self.youtube_client.configured:
            status = "missing_api_key"
        elif self.last_status == "quota_exceeded":
            status = "quota_exceeded"
        elif self.last_error:
            status = "error"
        elif self.last_checked_at:
            status = "success"
        else:
            status = "skipped"
        if not self.enabled:
            message = "Provider disabled."
        elif not self.youtube_client.configured:
            message = "YOUTUBE_API_KEY is not configured."
        elif status == "quota_exceeded":
            message = self.last_error or "YouTube quota was exhausted."
        elif status == "error":
            message = self.last_error or "YouTube discovery failed."
        elif status == "success":
            message = "Verified YouTube results returned for this query." if self.last_result_count else "No verified YouTube results returned for this query yet."
        else:
            message = "Discovery has not run yet."
        return {
            "name": self.name,
            "display_name": "YouTube",
            "status": status,
            "configured": self.youtube_client.configured,
            "enabled": self.enabled,
            "search_backend": "youtube_data_api",
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_error": self.last_error,
            "last_result_count": self.last_result_count,
            "message": message,
        }

    async def discover(self, skill_name: str, skill_slug: str, limit: int = 5) -> list[DiscoveryCandidate]:
        if not self.enabled or not self.youtube_client.configured:
            self.last_status = "missing_api_key" if self.enabled and not self.youtube_client.configured else "skipped"
            return []

        self.last_checked_at = datetime.now(timezone.utc)
        self.last_error = None
        self.last_status = "skipped"
        candidates: list[DiscoveryCandidate] = []
        try:
            results = await self.youtube_client.search(skill_name=skill_name, skill_slug=skill_slug, limit=limit)
        except YouTubeQuotaExceededError as exc:
            self.last_error = str(exc)
            self.last_status = "quota_exceeded"
            logger.warning("YouTube quota exhausted for skill=%s: %s", skill_slug, exc)
            self.last_result_count = 0
            return []
        except Exception as exc:
            self.last_error = str(exc)
            self.last_status = "error"
            logger.warning("YouTube lookup failed for skill=%s: %s", skill_slug, exc)
            self.last_result_count = 0
            return []

        for item in results[:limit]:
            candidates.append(
                DiscoveryCandidate(
                    skill_slug=skill_slug,
                    skill_name=skill_name,
                    title=item.title,
                    provider=item.provider,
                    source_type=item.source_type,
                    source_url=item.source_url,
                    channel_name=item.channel_name,
                    duration_minutes=item.duration_minutes,
                    difficulty=item.difficulty,
                    format=item.format,
                    is_free=item.is_free,
                    language=item.language,
                    trust_score=item.trust_score,
                    relevance_score=item.relevance_score,
                    freshness_score=item.freshness_score,
                    last_verified_at=item.last_verified_at,
                    metadata={
                        **(item.metadata or {}),
                        "discovery_source": self.name,
                        "discovered_by": "YouTube",
                        "verification_status": "verified",
                        "price_status": "free" if item.is_free else "paid",
                        "search_backend": "youtube_data_api",
                    },
                )
            )

        self.last_result_count = len(candidates)
        if candidates:
            self.last_success_at = datetime.now(timezone.utc)
            self.last_status = "success"
        return candidates


def build_default_discovery_providers(
    youtube_client: YouTubeLearningClient,
    enabled: bool = True,
) -> list[DiscoveryProvider]:
    discovery_enabled = bool(settings.LEARNING_RESOURCE_DISCOVERY_ENABLED and enabled)
    web_enabled = bool(settings.LEARNING_WEB_SEARCH_ENABLED and discovery_enabled)
    mode = str(settings.LEARNING_RESOURCE_PROVIDER or "").strip().lower()
    dynamic_enabled = any(token in {"dynamic", "all"} for token in re.split(r"[+,]", mode) if token.strip())

    def _is_enabled(name: str) -> bool:
        if not enabled:
            return False
        if "all" in mode:
            return True
        if name in mode:
            return True
        if name == "youtube" and "seeded+youtube" in mode:
            return True
        if name in {"web", "coursera", "udemy"} and ("seeded+web" in mode or "seeded+dynamic" in mode or dynamic_enabled):
            return True
        if mode in {"dynamic", "seeded+dynamic"} and name in {"web", "coursera", "udemy", "youtube"}:
            return True
        return False

    providers: list[DiscoveryProvider] = [
        YouTubeDiscoveryProvider(youtube_client=youtube_client, enabled=discovery_enabled and _is_enabled("youtube")),
        BingSearchDiscoveryProvider(
            name="web",
            display_name="Web search",
            query_templates=(
                '{skill_name} tutorial',
                '{skill_name} guide',
            ),
            allowed_domains=tuple(sorted(set(settings.LEARNING_WEB_SEARCH_ALLOWED_DOMAINS) | _WEB_TRUSTED_DOMAINS)),
            source_type="web_search_result",
            format="guide",
            step_type="foundation",
            trust_score=0.84,
            relevance_score=0.82,
            freshness_score=0.66,
            search_backend=settings.LEARNING_WEB_SEARCH_PROVIDER,
            require_free_signal=False,
            channel_name="Web search",
            is_free=True,
            timeout_seconds=settings.LEARNING_WEB_SEARCH_TIMEOUT_SECONDS,
            enabled=web_enabled and _is_enabled("web"),
        ),
        BingSearchDiscoveryProvider(
            name="coursera",
            display_name="Coursera",
            query_templates=(
                'site:coursera.org "{skill_name}" free course',
                'site:coursera.org "{skill_name}" audit course',
            ),
            allowed_domains=("coursera.org", "www.coursera.org"),
            source_type="coursera_course",
            format="course",
            step_type="hands_on",
            trust_score=0.8,
            relevance_score=0.86,
            freshness_score=0.62,
            search_backend=settings.LEARNING_WEB_SEARCH_PROVIDER,
            require_free_signal=True,
            channel_name="Coursera",
            is_free=True,
            timeout_seconds=settings.LEARNING_WEB_SEARCH_TIMEOUT_SECONDS,
            enabled=bool(settings.COURSERA_DISCOVERY_ENABLED and web_enabled and _is_enabled("coursera")),
        ),
        BingSearchDiscoveryProvider(
            name="udemy",
            display_name="Udemy",
            query_templates=(
                'site:udemy.com "{skill_name}" free course',
                'site:udemy.com "{skill_name}" beginner course free',
            ),
            allowed_domains=("udemy.com", "www.udemy.com"),
            source_type="udemy_course",
            format="course",
            step_type="hands_on",
            trust_score=0.76,
            relevance_score=0.84,
            freshness_score=0.58,
            search_backend=settings.LEARNING_WEB_SEARCH_PROVIDER,
            require_free_signal=True,
            channel_name="Udemy",
            is_free=False,
            timeout_seconds=settings.LEARNING_WEB_SEARCH_TIMEOUT_SECONDS,
            enabled=web_enabled and _is_enabled("udemy"),
        ),
    ]
    return providers
