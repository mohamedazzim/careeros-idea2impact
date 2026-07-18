"""India-eligible job classification engine.

Single source of truth for determining whether a job posting is
eligible for the India market. Used during ingestion, reclassification,
and dashboard filtering.

Rules (evaluated in order — strict):
  1. Country code is IN / contains India keyword / Indian city → eligible
  2. Non-India restricted country present → REJECT (even if remote)
  3. "Remote India" explicitly mentioned → eligible
  4. Worldwide/Global/APAC + India mentioned in description → eligible
  5. Bare "Remote" without India evidence → REJECT
  6. No location + no remote evidence → REJECT (ambiguous = reject)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.core.config import settings

INDIA_CITIES = [
    "bengaluru", "bangalore", "hyderabad", "chennai", "pune", "mumbai",
    "delhi", "gurugram", "gurgaon", "noida", "kolkata", "coimbatore",
    "kochi", "ahmedabad", "jaipur", "indore", "trivandrum",
    "thiruvananthapuram", "lucknow", "chandigarh", "bhopal", "nagpur",
    "visakhapatnam", "mysore", "manipal", "goa", "pondicherry",
    "faridabad", "ghaziabad", "udaipur", "jodhpur", "patna", "ranchi",
    "guwahati", "bhubaneswar", "mangalore", "hubli", "belgaum",
]

INDIA_KEYWORDS = [
    "india", "indian", "bharat",
]

INDIA_COUNTRY_CODES = {"IN", "IND", "INDIA"}

NON_INDIA_RESTRICTED_COUNTRIES = {
    "US", "USA", "United States", "United States of America",
    "GB", "UK", "United Kingdom",
    "DE", "Germany",
    "FR", "France",
    "CA", "Canada",
    "AU", "Australia",
    "JP", "Japan",
    "BR", "Brazil",
    "NL", "Netherlands",
    "SE", "Sweden",
    "SG", "Singapore",
}

INDIA_EXPLICIT_REMOTE_PHRASES = [
    "remote india", "india remote", "work from india",
    "india based", "based in india", "india eligible",
    "open to candidates in india", "candidates in india",
    "india time zone", "indian candidates",
]

NON_INDIA_LOCATION_PATTERNS = [
    "united states", "usa", "u.s.", "us-based", "us based",
    "united kingdom", "uk-based", "uk based",
    "germany", "german",
    "canada", "canadian",
    "london", "berlin", "munich", "frankfurt",
    "san francisco", "new york", "seattle", "austin", "boston",
    "ontario", "toronto", "vancouver",
    "europe", "european", "eu-based",
    "amsterdam", "paris", "tokyo", "singapore",
    "australia", "australian", "sydney", "melbourne",
]


@dataclass
class LocationDecision:
    is_india_eligible: bool
    location_country: Optional[str]
    location_region: Optional[str]
    location_city: Optional[str]
    is_remote: bool
    remote_region: Optional[str]
    exclusion_reason: Optional[str]


MAX_LOCATION_LENGTH = 500


def _norm(text: str) -> str:
    sanitized = (text or "")[:MAX_LOCATION_LENGTH]
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", sanitized)
    return re.sub(r"\s+", " ", sanitized).strip().lower()


def _contains_india_city(text: str) -> Optional[str]:
    normalized = _norm(text)
    for city in INDIA_CITIES:
        if city in normalized:
            return city
    return None


def _contains_india_keyword(text: str) -> bool:
    normalized = f" {_norm(text)} "
    for kw in INDIA_KEYWORDS:
        if kw in normalized:
            return True
    return False


def _detect_country_code(raw_location: str) -> Optional[str]:
    normalized = _norm(raw_location)
    words = re.findall(r"\b[a-z0-9_-]+\b", normalized)
    for code in INDIA_COUNTRY_CODES:
        if code.lower() in words:
            return "IN"
    for keyword in ["india", "indian", "bharat"]:
        if keyword in normalized:
            return "IN"
    return None


def _is_non_india_restricted(raw_location: str) -> Optional[str]:
    normalized = _norm(raw_location)
    words = re.findall(r"\b[a-z0-9_-]+\b", normalized)
    for country in NON_INDIA_RESTRICTED_COUNTRIES:
        country_norm = _norm(country)
        if len(country_norm) <= 3:
            if country_norm in words:
                return country
        else:
            if country_norm in normalized:
                return country
    return None


def _has_non_india_location_pattern(raw_location: str) -> Optional[str]:
    normalized = _norm(raw_location)
    words = re.findall(r"\b[a-z0-9_-]+\b", normalized)
    for pattern in NON_INDIA_LOCATION_PATTERNS:
        pattern_norm = _norm(pattern)
        if len(pattern_norm) <= 3:
            if pattern_norm in words:
                return pattern
        else:
            if pattern_norm in normalized:
                return pattern
    return None


def _is_explicit_remote_india(raw_location: str, description: Optional[str] = None) -> bool:
    combined = f" {_norm(raw_location)} {_norm(description or '')} "
    for phrase in INDIA_EXPLICIT_REMOTE_PHRASES:
        if phrase in combined:
            return True
    return False


def _classify_remote_region(text: str) -> Optional[str]:
    normalized = _norm(text)
    if any(r in normalized for r in ["worldwide", "global", "anywhere", "earth"]):
        return "worldwide"
    if "apac" in normalized:
        return "apac"
    if "asia" in normalized and "india" not in normalized:
        return "asia"
    if "remote india" in normalized or "india remote" in normalized:
        return "india"
    if "remote" in normalized:
        return "remote"
    return None


def classify_job_location(
    location_raw: Optional[str] = None,
    is_remote: Optional[bool] = None,
    remote_region: Optional[str] = None,
    country_code: Optional[str] = None,
    company: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> LocationDecision:
    """Classify a job's India eligibility based on available location data.

    Strict rules (evaluated in order):
    1. Country code is IN → eligible
    2. Location contains India city → eligible
    3. Location contains "India" keyword → eligible
    4. Non-India restricted country present → REJECT (even if remote)
    5. Bare "Remote" without India mention → REJECT
    6. Remote India explicitly stated → eligible
    7. Worldwide/Global + India in description → eligible
    8. No location + no remote evidence → REJECT
    """
    raw = location_raw or ""
    combined_text = " ".join(filter(None, [raw, title or "", description or ""]))

    detected_country = country_code or _detect_country_code(raw)
    location_title_text = " ".join(filter(None, [raw, title or ""]))
    india_city = _contains_india_city(location_title_text)
    has_india_keyword = _contains_india_keyword(raw) or _contains_india_keyword(title or "")

    location_country = None
    location_region = None
    location_city = india_city

    detected_remote_region = remote_region or _classify_remote_region(raw)
    is_actually_remote = is_remote or detected_remote_region is not None

    if detected_country == "IN":
        return LocationDecision(
            is_india_eligible=True,
            location_country="IN",
            location_region=location_region,
            location_city=location_city,
            is_remote=bool(is_remote),
            remote_region=remote_region,
            exclusion_reason=None,
        )

    if india_city:
        return LocationDecision(
            is_india_eligible=True,
            location_country="IN",
            location_region=location_region,
            location_city=india_city,
            is_remote=bool(is_remote),
            remote_region=remote_region,
            exclusion_reason=None,
        )

    if has_india_keyword:
        return LocationDecision(
            is_india_eligible=True,
            location_country="IN",
            location_region=location_region,
            location_city=location_city,
            is_remote=is_actually_remote,
            remote_region=detected_remote_region,
            exclusion_reason=None,
        )

    non_india_country = _is_non_india_restricted(raw)
    if non_india_country:
        return LocationDecision(
            is_india_eligible=False,
            location_country=non_india_country[:2].upper() if len(non_india_country) == 2 else None,
            location_region=location_region,
            location_city=location_city,
            is_remote=is_actually_remote,
            remote_region=detected_remote_region,
            exclusion_reason=f"non_india_location: {non_india_country}",
        )

    non_india_pattern = _has_non_india_location_pattern(raw)
    if non_india_pattern:
        return LocationDecision(
            is_india_eligible=False,
            location_country=None,
            location_region=location_region,
            location_city=location_city,
            is_remote=is_actually_remote,
            remote_region=detected_remote_region,
            exclusion_reason=f"non_india_location: {non_india_pattern}",
        )

    if is_actually_remote:
        if detected_remote_region == "india":
            return LocationDecision(
                is_india_eligible=True,
                location_country="IN",
                location_region=location_region,
                location_city=location_city,
                is_remote=True,
                remote_region="india",
                exclusion_reason=None,
            )

        if detected_remote_region in ("worldwide", "apac"):
            if _contains_india_keyword(combined_text) or india_city:
                return LocationDecision(
                    is_india_eligible=True,
                    location_country=detected_country,
                    location_region=location_region,
                    location_city=location_city,
                    is_remote=True,
                    remote_region=detected_remote_region,
                    exclusion_reason=None,
                )

        if settings.JOB_ALLOW_GLOBAL_REMOTE and detected_remote_region in (
            "remote", "worldwide", "apac", "asia"
        ):
            return LocationDecision(
                is_india_eligible=True,
                location_country=detected_country,
                location_region=location_region,
                location_city=location_city,
                is_remote=True,
                remote_region=detected_remote_region,
                exclusion_reason=None,
            )

        return LocationDecision(
            is_india_eligible=False,
            location_country=detected_country,
            location_region=location_region,
            location_city=location_city,
            is_remote=True,
            remote_region=detected_remote_region,
            exclusion_reason=f"non_india_location: remote ({detected_remote_region or 'unspecified'}) without India evidence",
        )

    if not raw.strip():
        return LocationDecision(
            is_india_eligible=False,
            location_country=None,
            location_region=None,
            location_city=None,
            is_remote=False,
            remote_region=None,
            exclusion_reason="non_india_location: no location and no remote eligibility evidence",
        )

    return LocationDecision(
        is_india_eligible=False,
        location_country=detected_country,
        location_region=location_region,
        location_city=location_city,
        is_remote=is_actually_remote,
        remote_region=detected_remote_region,
        exclusion_reason=f"non_india_location: '{raw[:80]}' does not match India eligibility criteria",
    )
