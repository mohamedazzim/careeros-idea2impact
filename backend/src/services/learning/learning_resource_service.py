"""Verified learning resource discovery and caching."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.integrations.learning.discovery import DiscoveryProvider, build_default_discovery_providers, _normalize_web_search_backend
from src.integrations.youtube.client import YouTubeLearningClient, get_youtube_learning_client
from src.models.learning import LearningResource
from src.services.learning.resource_provenance_service import get_resource_provenance_service
from src.services.learning.skill_normalizer import canonical_display_name, normalize_skill

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LearningResourceRecord:
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
    metadata: Optional[dict[str, Any]] = None

    def to_row(self) -> dict[str, Any]:
        data = asdict(self)
        if data.get("last_verified_at") is not None:
            verified_at = data["last_verified_at"]
            if getattr(verified_at, "tzinfo", None) is not None:
                data["last_verified_at"] = verified_at.astimezone(timezone.utc).replace(tzinfo=None)
        data["metadata"] = data.pop("metadata") or {}
        return data


def is_real_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _source_domain(source_url: str) -> str:
    try:
        return urlparse(source_url).netloc.lower()
    except Exception:
        return ""


class LearningResourceService:
    def __init__(
        self,
        youtube_client: Optional[YouTubeLearningClient] = None,
        discovery_providers: Optional[list[DiscoveryProvider]] = None,
    ) -> None:
        self.youtube_client = youtube_client or get_youtube_learning_client()
        self.discovery_providers = discovery_providers or build_default_discovery_providers(self.youtube_client, enabled=bool(settings.LEARNING_RESOURCES_ENABLED))
        self._seed_path = Path(__file__).resolve().parents[3] / "seeds" / "learning_resources.json"
        self.provenance_service = get_resource_provenance_service()

    def provider_health(self) -> dict[str, Any]:
        providers = [provider.health() for provider in self.discovery_providers]
        web_search_backend = _normalize_web_search_backend(settings.LEARNING_WEB_SEARCH_PROVIDER)
        live_statuses = [provider.get("status") for provider in providers if provider.get("enabled")]
        has_verified_results = any(
            int(provider.get("last_result_count") or 0) > 0 for provider in providers if provider.get("enabled")
        )
        if any(status == "success" for status in live_statuses):
            status = "success" if has_verified_results else ("seeded_fallback" if self._seed_path.exists() else "success")
        elif any(status == "quota_exceeded" for status in live_statuses):
            status = "quota_exceeded"
        elif any(status == "error" for status in live_statuses):
            status = "error"
        elif any(status == "missing_api_key" for status in live_statuses):
            status = "seeded_fallback" if self._seed_path.exists() else "missing_api_key"
        elif self._seed_path.exists():
            status = "seeded_fallback"
        else:
            status = "skipped"
        if status == "success" and has_verified_results:
            message = "Live discovery is available and returning verified resources."
        elif status == "success":
            message = "Live discovery ran but returned no verified resources yet."
        elif status == "quota_exceeded":
            message = "A live discovery provider hit quota limits. Showing verified curated fallback resources."
        elif status == "missing_api_key":
            message = "Live discovery providers are not fully configured. Showing verified curated fallback resources."
        elif status == "seeded_fallback":
            message = "Using verified curated fallback resources while live discovery is unavailable or returned no verified results."
        else:
            message = "Learning resource discovery is not enabled."
        return {
            "enabled": bool(settings.LEARNING_RESOURCES_ENABLED),
            "discovery_enabled": bool(settings.LEARNING_RESOURCE_DISCOVERY_ENABLED),
            "provider": settings.LEARNING_RESOURCE_PROVIDER,
            "provider_mode": settings.LEARNING_RESOURCE_PROVIDER,
            "status": status,
            "message": message,
            "youtube_configured": self.youtube_client.configured,
            "web_search_enabled": bool(settings.LEARNING_WEB_SEARCH_ENABLED),
            "web_search_provider": web_search_backend,
            "web_search_backend": web_search_backend,
            "cache_ttl_hours": settings.LEARNING_RESOURCE_CACHE_TTL_HOURS,
            "min_results_per_skill": settings.LEARNING_RESOURCE_MIN_RESULTS_PER_SKILL,
            "max_results_per_skill": settings.LEARNING_RESOURCE_MAX_RESULTS_PER_SKILL,
            "seed_file_present": self._seed_path.exists(),
            "trusted_sources": len(self._trusted_domains()),
            "search_backend": web_search_backend,
            "providers": providers,
        }

    def _trusted_domains(self) -> set[str]:
        return {
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
            "pytorch.org",
            "docs.pytorch.org",
            "tensorflow.org",
            "docs.docker.com",
            "kubernetes.io",
            "fastapi.tiangolo.com",
            "react.dev",
            "www.postgresql.org",
            "developer.mozilla.org",
            "git-scm.com",
            "python.langchain.com",
            "docs.langchain.com",
            "www.youtube.com",
            "coursera.org",
            "www.coursera.org",
            "udemy.com",
            "www.udemy.com",
        }

    def _provider_mode_tokens(self) -> set[str]:
        mode = str(settings.LEARNING_RESOURCE_PROVIDER or "").strip().lower()
        return {token.strip() for token in mode.replace(",", "+").split("+") if token.strip()}

    def _is_discovery_provider_enabled(self, name: str) -> bool:
        if not settings.LEARNING_RESOURCES_ENABLED:
            return False
        tokens = self._provider_mode_tokens()
        if not tokens:
            return False
        if "all" in tokens:
            return True
        if name in tokens:
            return True
        if "dynamic" in tokens and name in {"youtube", "web", "coursera", "udemy"}:
            return True
        if "seeded+dynamic" in str(settings.LEARNING_RESOURCE_PROVIDER or "").strip().lower() and name in {"youtube", "web", "coursera", "udemy"}:
            return True
        if "seeded+youtube" in str(settings.LEARNING_RESOURCE_PROVIDER or "").strip().lower() and name == "youtube":
            return True
        if "seeded+web" in str(settings.LEARNING_RESOURCE_PROVIDER or "").strip().lower() and name in {"web", "coursera", "udemy"}:
            return True
        return False

    async def ensure_seed_resources(self, db: AsyncSession) -> int:
        if not self._seed_path.exists():
            return 0

        try:
            seed_rows = json.loads(self._seed_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read learning resource seed file: %s", exc)
            return 0

        records: list[LearningResourceRecord] = []
        for raw in seed_rows:
            try:
                record = self._normalize_seed_record(raw)
            except ValueError as exc:
                logger.warning("Skipping invalid learning seed row: %s", exc)
                continue
            if record:
                records.append(record)

        return await self.upsert_resources(db, records)

    def _normalize_seed_record(self, raw: Any) -> Optional[LearningResourceRecord]:
        if not isinstance(raw, dict):
            raise ValueError("Seed row must be a mapping")

        normalized = normalize_skill(raw.get("skill_slug") or raw.get("skill_name") or raw.get("skill") or "")
        title = str(raw.get("title") or "").strip()
        source_url = str(raw.get("source_url") or "").strip()
        if not normalized.slug or not title or not source_url:
            raise ValueError("Seed row requires skill, title, and source_url")
        if not is_real_http_url(source_url):
            raise ValueError(f"Invalid source_url: {source_url}")

        last_verified_raw = raw.get("last_verified_at")
        last_verified_at = None
        if last_verified_raw:
            try:
                last_verified_at = datetime.fromisoformat(str(last_verified_raw).replace("Z", "+00:00"))
            except ValueError:
                last_verified_at = datetime.now(timezone.utc)

        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        metadata.setdefault("seeded", True)
        metadata.setdefault("step_type", str(metadata.get("step_type") or raw.get("step_type") or "foundation"))
        metadata.setdefault("discovery_source", "seed")
        metadata.setdefault("verification_status", "seeded_fallback")
        metadata.setdefault("price_status", "free" if bool(raw.get("is_free", True)) else "paid_or_unknown")
        metadata.setdefault("source_domain", _source_domain(source_url))
        metadata.setdefault("cache_status", "seed_cache")

        return LearningResourceRecord(
            skill_slug=normalized.slug,
            skill_name=str(raw.get("skill_name") or normalized.display_name or canonical_display_name(normalized.slug)).strip(),
            title=title,
            provider=str(raw.get("provider") or "Curated"),
            source_type=str(raw.get("source_type") or "curated_seed"),
            source_url=source_url,
            channel_name=(str(raw.get("channel_name")).strip() if raw.get("channel_name") else None),
            duration_minutes=self._coerce_int(raw.get("duration_minutes")),
            difficulty=(str(raw.get("difficulty")).strip() if raw.get("difficulty") else None),
            format=(str(raw.get("format")).strip() if raw.get("format") else None),
            is_free=bool(raw.get("is_free", True)),
            language=str(raw.get("language") or "en"),
            trust_score=float(raw.get("trust_score") or 0.75),
            relevance_score=float(raw.get("relevance_score") or 0.75),
            freshness_score=float(raw.get("freshness_score") or 0.5),
            last_verified_at=last_verified_at,
            metadata=metadata,
        )

    def _coerce_int(self, value: Any) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    async def upsert_resources(
        self,
        db: AsyncSession,
        resources: list[LearningResourceRecord],
        *,
        discovery_run_uid: str | None = None,
    ) -> int:
        if not resources:
            return 0

        rows = [record.to_row() for record in resources]
        stmt = insert(LearningResource.__table__).values(rows)
        update_columns = {
            "skill_name": stmt.excluded.skill_name,
            "title": stmt.excluded.title,
            "provider": stmt.excluded.provider,
            "source_type": stmt.excluded.source_type,
            "channel_name": stmt.excluded.channel_name,
            "duration_minutes": stmt.excluded.duration_minutes,
            "difficulty": stmt.excluded.difficulty,
            "format": stmt.excluded.format,
            "is_free": stmt.excluded.is_free,
            "language": stmt.excluded.language,
            "trust_score": stmt.excluded.trust_score,
            "relevance_score": stmt.excluded.relevance_score,
            "freshness_score": stmt.excluded.freshness_score,
            "last_verified_at": stmt.excluded.last_verified_at,
            "metadata": stmt.excluded.metadata,
            "updated_at": datetime.utcnow(),
        }
        stmt = stmt.on_conflict_do_update(
            constraint="uq_learning_resources_skill_source",
            set_=update_columns,
        )
        await db.execute(stmt)
        await db.commit()
        await self._record_provenance_for_resources(db, resources, discovery_run_uid=discovery_run_uid)
        return len(rows)

    async def _record_provenance_for_resources(
        self,
        db: AsyncSession,
        records: list[LearningResourceRecord],
        *,
        discovery_run_uid: str | None = None,
    ) -> None:
        for record in records:
            query = select(LearningResource).where(
                LearningResource.skill_slug == record.skill_slug,
                LearningResource.source_url == record.source_url,
            )
            result = await db.execute(query)
            resource = result.scalar_one_or_none()
            if resource is None:
                continue
            metadata = resource.metadata_ or {}
            provenance_type = str(metadata.get("verification_status") or metadata.get("discovery_source") or "resource_discovery")
            source_kind = "seed" if metadata.get("seeded") else "live"
            evidence = [
                {
                    "type": "db_record",
                    "table": "learning_resources",
                    "id": str(resource.id),
                    "note": "Learning resource stored or refreshed for skill guidance",
                    "extra": {
                        "seeded": bool(metadata.get("seeded")),
                        "discovery_source": metadata.get("discovery_source"),
                        "source_domain": metadata.get("source_domain"),
                        "cache_status": metadata.get("cache_status"),
                    },
                }
            ]
            try:
                await self.provenance_service.record_provenance(
                    db,
                    provenance_type=provenance_type,
                    source_entity_type="learning_resource",
                    source_entity_id=str(resource.id),
                    skill_slug=resource.skill_slug,
                    skill_name=resource.skill_name,
                    title=resource.title,
                    provider=resource.provider,
                    source_url=resource.source_url,
                    resource_id=resource.id,
                    discovery_run_uid=discovery_run_uid,
                    user_id=None,
                    source_table="learning_resources",
                    source_pk=resource.id,
                    trust_score=float(resource.trust_score or 0.0),
                    relevance_score=float(resource.relevance_score or 0.0),
                    freshness_score=float(resource.freshness_score or 0.0),
                    verification_status=str(metadata.get("verification_status") or provenance_type),
                    source_kind=source_kind,
                    status="success",
                    evidence=evidence,
                    source_context={
                        "seeded": bool(metadata.get("seeded")),
                        "discovery_source": metadata.get("discovery_source"),
                        "source_domain": metadata.get("source_domain"),
                        "cache_status": metadata.get("cache_status"),
                    },
                )
            except Exception as exc:  # pragma: no cover - provenance must not break resource persistence
                logger.debug("Failed to store resource provenance for resource_id=%s: %s", resource.id, exc)

    async def get_resources_for_skill(self, db: AsyncSession, skill_slug: str, limit: int = 6) -> list[LearningResource]:
        normalized = normalize_skill(skill_slug)
        if not normalized.slug:
            return []

        query = (
            select(LearningResource)
            .where(
                LearningResource.skill_slug == normalized.slug,
                LearningResource.is_free.is_(True),
            )
            .order_by(
                LearningResource.trust_score.desc(),
                LearningResource.relevance_score.desc(),
                LearningResource.freshness_score.desc(),
                LearningResource.last_verified_at.desc().nullslast(),
                LearningResource.created_at.desc(),
            )
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def discover_remote_resources(self, skill_name: str, skill_slug: str, limit: int = 5) -> list[LearningResourceRecord]:
        if not settings.LEARNING_RESOURCES_ENABLED or not settings.LEARNING_RESOURCE_DISCOVERY_ENABLED:
            return []

        discovered: list[LearningResourceRecord] = []
        seen_urls: set[str] = set()
        min_results = max(0, int(settings.LEARNING_RESOURCE_MIN_RESULTS_PER_SKILL))
        max_results = max(min_results, int(settings.LEARNING_RESOURCE_MAX_RESULTS_PER_SKILL))
        target_limit = min(max(limit, min_results), max_results)
        remaining = max(0, target_limit)
        for provider in self.discovery_providers:
            if remaining <= 0:
                break
            if not self._is_discovery_provider_enabled(provider.name):
                continue
            try:
                provider_candidates = await provider.discover(skill_name=skill_name, skill_slug=skill_slug, limit=remaining)
            except Exception as exc:
                logger.warning("Discovery provider failed for skill=%s provider=%s: %s", skill_slug, getattr(provider, "name", "unknown"), exc)
                continue

            for candidate in provider_candidates:
                if remaining <= 0:
                    break
                if not candidate.source_url or not is_real_http_url(candidate.source_url):
                    continue
                if candidate.source_url in seen_urls:
                    continue
                seen_urls.add(candidate.source_url)
                discovered.append(
                    LearningResourceRecord(
                        skill_slug=candidate.skill_slug,
                        skill_name=candidate.skill_name,
                        title=candidate.title,
                        provider=candidate.provider,
                        source_type=candidate.source_type,
                        source_url=candidate.source_url,
                        channel_name=candidate.channel_name,
                        duration_minutes=candidate.duration_minutes,
                        difficulty=candidate.difficulty,
                        format=candidate.format,
                        is_free=candidate.is_free,
                        language=candidate.language,
                        trust_score=candidate.trust_score,
                        relevance_score=candidate.relevance_score,
                        freshness_score=candidate.freshness_score,
                        last_verified_at=candidate.last_verified_at,
                        metadata={
                            **(candidate.metadata or {}),
                            "discovery_source": provider.name,
                            "discovered_by": getattr(provider, "display_name", provider.name),
                            "verification_status": candidate.metadata.get("verification_status", "verified"),
                            "price_status": candidate.metadata.get("price_status", "free" if candidate.is_free else "paid_or_unknown"),
                            "source_domain": candidate.metadata.get("source_domain", _source_domain(candidate.source_url)),
                            "cache_status": "live_discovery",
                            "discovery_provider": getattr(provider, "display_name", provider.name),
                        },
                    )
                )
                remaining -= 1
        return discovered

    async def ensure_skill_resources(
        self,
        db: AsyncSession,
        skill_slug: str,
        skill_name: Optional[str] = None,
        limit: int = 6,
        force_refresh: bool = False,
    ) -> list[LearningResource]:
        normalized = normalize_skill(skill_slug)
        if not normalized.slug:
            return []

        await self.ensure_seed_resources(db)
        resources = await self.get_resources_for_skill(db, normalized.slug, limit=limit)
        has_live_resources = any(not bool((resource.metadata_ or {}).get("seeded")) for resource in resources)
        if resources and has_live_resources and not force_refresh:
            return resources

        discovery_run_uid: str | None = None
        if force_refresh or (
            settings.LEARNING_RESOURCE_DISCOVERY_ENABLED
            and (settings.LEARNING_WEB_SEARCH_ENABLED or self.youtube_client.configured)
        ):
            try:
                discovery_run = await self.provenance_service.start_discovery_run(
                    db,
                    provider=settings.LEARNING_RESOURCE_PROVIDER,
                    source_type="learning_resource",
                    skill_slug=normalized.slug,
                    skill_name=skill_name or normalized.display_name,
                )
                discovery_run_uid = discovery_run.run_uid
            except Exception as exc:  # pragma: no cover - provenance must not block discovery
                logger.debug("Failed to start provenance discovery run for %s: %s", normalized.slug, exc)
            discovered = await self.discover_remote_resources(skill_name or normalized.display_name, normalized.slug, limit=limit)
            if discovered:
                await self.upsert_resources(db, discovered, discovery_run_uid=discovery_run_uid)
                resources = await self.get_resources_for_skill(db, normalized.slug, limit=limit)
            if discovery_run_uid:
                try:
                    await self.provenance_service.complete_discovery_run(
                        db,
                        run_uid=discovery_run_uid,
                        status="completed",
                        candidate_count=len(discovered),
                        stored_count=len(discovered),
                        response_payload={
                            "skill_slug": normalized.slug,
                            "skill_name": skill_name or normalized.display_name,
                            "resource_count": len(discovered),
                        },
                    )
                except Exception as exc:  # pragma: no cover - provenance must not block discovery
                    logger.debug("Failed to complete provenance discovery run for %s: %s", normalized.slug, exc)

        return resources


_SERVICE: Optional[LearningResourceService] = None


def get_learning_resource_service() -> LearningResourceService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = LearningResourceService()
    return _SERVICE
