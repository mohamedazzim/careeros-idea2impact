"""Minimal YouTube Data API client for verified learning resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import re
from typing import Any, Optional

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

_TRUSTED_CHANNEL_HINTS = {
    "aws": {"amazon web services", "aws", "aws events"},
    "pytorch": {"pytorch", "pytorch official"},
    "tensorflow": {"tensorflow"},
    "docker": {"docker"},
    "kubernetes": {"kubernetes"},
    "react": {"react"},
    "fastapi": {"tiangolo", "fastapi"},
    "postgresql": {"postgresql"},
    "langchain": {"langchain"},
    "freecodecamp": {"freecodecamp"},
}


class YouTubeLearningError(RuntimeError):
    """Base error for YouTube discovery."""


class YouTubeQuotaExceededError(YouTubeLearningError):
    """Raised when the YouTube API quota is exhausted."""


def _iso8601_duration_to_minutes(duration: str | None) -> Optional[int]:
    if not duration:
        return None
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?",
        duration,
    )
    if not match:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    total_minutes = days * 24 * 60 + hours * 60 + minutes + (1 if seconds >= 30 else 0)
    return total_minutes or None


def _trusted_channel_match(skill_slug: str, channel_title: str, title: str) -> bool:
    hints = _TRUSTED_CHANNEL_HINTS.get(skill_slug, set()) | _TRUSTED_CHANNEL_HINTS.get("freecodecamp", set())
    normalized = f"{channel_title} {title}".lower()
    return any(hint in normalized for hint in hints)


@dataclass(slots=True)
class YouTubeLearningResource:
    title: str
    provider: str
    source_type: str
    source_url: str
    channel_name: str | None
    duration_minutes: int | None
    difficulty: str | None
    format: str | None
    is_free: bool
    language: str
    trust_score: float
    relevance_score: float
    freshness_score: float
    last_verified_at: datetime | None
    metadata: dict[str, Any]


class YouTubeLearningClient:
    """Searches the public YouTube API for free learning resources."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or settings.YOUTUBE_API_KEY or "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def search(self, skill_name: str, skill_slug: str, limit: int = 5) -> list[YouTubeLearningResource]:
        if not self.configured:
            return []

        query = f"{skill_name} free tutorial"
        params = {
            "part": "snippet",
            "type": "video",
            "maxResults": min(max(limit, 1), 10),
            "q": query,
            "key": self.api_key,
            "safeSearch": "strict",
            "order": "relevance",
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                search_resp = await client.get("https://www.googleapis.com/youtube/v3/search", params=params)
                if search_resp.status_code == 403 and "quota" in search_resp.text.lower():
                    logger.info("YouTube quota exhausted while searching skill=%s", skill_slug)
                    raise YouTubeQuotaExceededError("YouTube quota exhausted")
                search_resp.raise_for_status()
                search_data = search_resp.json()
                video_ids = [
                    item.get("id", {}).get("videoId")
                    for item in search_data.get("items", [])
                    if isinstance(item, dict)
                ]
                video_ids = [video_id for video_id in video_ids if video_id]
                if not video_ids:
                    return []

                detail_params = {
                    "part": "snippet,contentDetails",
                    "id": ",".join(video_ids[:10]),
                    "key": self.api_key,
                }
                detail_resp = await client.get("https://www.googleapis.com/youtube/v3/videos", params=detail_params)
                detail_resp.raise_for_status()
                detail_data = detail_resp.json()
        except Exception as exc:
            logger.warning("YouTube lookup failed for skill=%s: %s", skill_slug, exc)
            if isinstance(exc, YouTubeLearningError):
                raise
            return []

        results: list[YouTubeLearningResource] = []
        for item in detail_data.get("items", []):
            snippet = item.get("snippet", {}) if isinstance(item, dict) else {}
            channel_title = str(snippet.get("channelTitle") or "").strip() or None
            title = str(snippet.get("title") or "").strip()
            if not title:
                continue
            if channel_title and not _trusted_channel_match(skill_slug, channel_title, title):
                continue
            video_id = str(item.get("id") or "").strip()
            if not video_id:
                continue
            duration = _iso8601_duration_to_minutes(item.get("contentDetails", {}).get("duration"))
            published_at = snippet.get("publishedAt")
            try:
                last_verified_at = (
                    datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
                    if published_at
                    else datetime.now(timezone.utc)
                )
            except ValueError:
                last_verified_at = datetime.now(timezone.utc)
            results.append(
                YouTubeLearningResource(
                    title=title,
                    provider="YouTube",
                    source_type="youtube",
                    source_url=f"https://www.youtube.com/watch?v={video_id}",
                    channel_name=channel_title,
                    duration_minutes=duration,
                    difficulty="beginner",
                    format="video",
                    is_free=True,
                    language="en",
                    trust_score=0.88 if channel_title else 0.72,
                    relevance_score=0.82,
                    freshness_score=0.8,
                    last_verified_at=last_verified_at,
                    metadata={
                        "video_id": video_id,
                        "published_at": published_at,
                        "channel_title": channel_title,
                        "search_query": query,
                    },
                )
            )
        return results[:limit]


def get_youtube_learning_client() -> YouTubeLearningClient:
    return YouTubeLearningClient()
