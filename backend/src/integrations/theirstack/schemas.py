"""Schemas for TheirStack job search requests and normalized jobs."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TheirStackSearchQuery(BaseModel):
    roles: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    remote: Optional[bool] = None
    experience_level: Optional[str] = None
    posted_at_max_age_days: int = 14
    limit: int = 25
    page: int = 0


class TheirStackSearchResult(BaseModel):
    request_payload: Dict[str, Any]
    response_payload: Dict[str, Any]
    jobs: List[Dict[str, Any]]
    quota: Dict[str, Any] = Field(default_factory=dict)
    rate_limit: Dict[str, Any] = Field(default_factory=dict)


class NormalizedTheirStackJob(BaseModel):
    source_job_id: str
    title: str
    company: str
    location: str = ""
    full_description: str
    apply_url: str
    posted_at: datetime
    source_provider: str = "theirstack"
    extracted_skills: List[str] = Field(default_factory=list)
    salary: Optional[str] = None
    remote: Optional[bool] = None
    original_provider: Optional[str] = None
    original_provider_metadata: Dict[str, Any] = Field(default_factory=dict)
    freshness_score: float = 0.0
    freshness_bucket: str = "unknown"
    provider_quality_score: float = 95.0
    salary_quality_score: float = 30.0
    apply_url_valid: bool = True

