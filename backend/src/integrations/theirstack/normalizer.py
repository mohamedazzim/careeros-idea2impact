"""Normalize TheirStack job responses into CareerOS jobs."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from .schemas import NormalizedTheirStackJob


TECH_SKILLS = [
    "python", "sql", "power bi", "powerbi", "machine learning", "ai", "generative ai",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "matplotlib", "nlp",
    "fastapi", "django", "docker", "aws", "azure", "gcp", "react", "typescript",
    "javascript", "nextjs", "node", "postgresql", "mongodb", "redis", "kubernetes",
]


def _first_present(record: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def extract_skills(text: str) -> List[str]:
    compact = re.sub(r"\s+", " ", (text or "").lower())
    normalized = f" {compact} "
    found = []
    for skill in TECH_SKILLS:
        needle = skill.replace("nextjs", "next.js")
        if skill in normalized or needle in normalized:
            found.append("power bi" if skill == "powerbi" else skill)
    return sorted(set(found))


def is_direct_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    lowered = url.lower()
    query = parsed.query.lower()
    blocked = ["/jobs/search", "/search/", "/srp/results", "keywords=", "/internships/keywords-", "-jobs-in-india"]
    return not any(marker in lowered for marker in blocked) and "q=" not in query


def freshness(posted_at: datetime) -> tuple[float, str]:
    age_hours = max(
        0.0,
        (datetime.now(timezone.utc).replace(tzinfo=None) - posted_at).total_seconds() / 3600,
    )
    if age_hours <= 24:
        return 100.0, "fresh"
    if age_hours <= 72:
        return 85.0, "recent"
    if age_hours <= 24 * 7:
        return 70.0, "active"
    if age_hours <= 24 * 30:
        return 40.0, "aging"
    return 0.0, "stale"


def provider_quality(source: str) -> float:
    source = (source or "").lower()
    if source in {"theirstack", "greenhouse", "lever", "ashby"}:
        return 95.0
    if source == "remoteok":
        return 85.0
    return 50.0


def salary_quality(record: Dict[str, Any]) -> tuple[float, Optional[str]]:
    min_salary = _first_present(record, ["salary_min", "min_salary", "annual_salary_min", "base_salary_min"])
    max_salary = _first_present(record, ["salary_max", "max_salary", "annual_salary_max", "base_salary_max"])
    currency = _first_present(record, ["salary_currency", "currency"]) or ""
    interval = _first_present(record, ["salary_interval", "pay_period"]) or ""
    if min_salary or max_salary:
        salary = f"{currency} {min_salary or ''}-{max_salary or ''} {interval}".strip()
        return 90.0, salary
    salary_text = _first_present(record, ["salary", "salary_string", "compensation"])
    if salary_text:
        return 75.0, str(salary_text)[:128]
    return 30.0, None


def normalize_job(record: Dict[str, Any]) -> Optional[NormalizedTheirStackJob]:
    title = str(_first_present(record, ["job_title", "title", "name"]) or "").strip()
    company = str(_first_present(record, ["company", "company_name", "organization"]) or "").strip()
    description = str(_first_present(record, ["description", "job_description", "full_description", "text"]) or "").strip()
    apply_url = str(_first_present(record, ["final_url", "apply_url", "url", "source_url"]) or "").strip()
    posted_at = _parse_datetime(_first_present(record, ["posted_at", "date_posted", "created_at", "first_seen_at"]))
    if not (title and company and description and apply_url and posted_at):
        return None
    if not is_direct_url(apply_url):
        return None

    source_job_id = str(_first_present(record, ["id", "job_id", "source_job_id", "external_id"]) or "").strip()
    if not source_job_id:
        source_job_id = hashlib.sha256(f"theirstack|{apply_url}|{title}".encode("utf-8")).hexdigest()[:64]
    location = str(_first_present(record, ["location", "formatted_location", "city", "country"]) or "").strip()
    original_provider = str(_first_present(record, ["source", "source_provider", "provider", "job_board"]) or "theirstack").strip().lower()
    score, bucket = freshness(posted_at)
    salary_score, salary = salary_quality(record)
    skills = extract_skills(f"{title}\n{description}")
    return NormalizedTheirStackJob(
        source_job_id=source_job_id[:128],
        title=title[:500],
        company=company[:256],
        location=location[:256],
        full_description=description[:50000],
        apply_url=apply_url[:1024],
        posted_at=posted_at,
        extracted_skills=skills,
        salary=salary,
        remote=bool(_first_present(record, ["remote", "is_remote"])) if _first_present(record, ["remote", "is_remote"]) is not None else None,
        original_provider=original_provider,
        original_provider_metadata=record,
        freshness_score=score,
        freshness_bucket=bucket,
        provider_quality_score=95.0,
        salary_quality_score=salary_score,
        apply_url_valid=True,
    )
