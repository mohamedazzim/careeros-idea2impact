"""Pydantic schemas for evidence-backed skill gap analysis."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SkillGapAnalyzeRequest(BaseModel):
    job_id: Optional[int] = None
    target_role_slug: Optional[str] = None
    source_scope: Literal["job", "role", "user", "roadmap"] = "job"


class SkillGapSummaryResponse(BaseModel):
    required_skill_count: int = 0
    missing_skill_count: int = 0
    learning_skill_count: int = 0
    evidenced_skill_count: int = 0
    validated_skill_count: int = 0
    insufficient_data_count: int = 0


class SkillGapEvidenceResponse(BaseModel):
    evidence_uid: str
    finding_uid: str
    user_id: str
    skill_slug: str
    evidence_type: str
    source_table: Optional[str] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    evidence_strength: str
    supports_status: str
    quote_or_snippet: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    confidence: str
    created_at: Optional[str] = None


class SkillGapFindingResponse(BaseModel):
    finding_uid: str
    run_uid: str
    user_id: str
    job_id: Optional[int] = None
    skill_node_uid: Optional[str] = None
    skill_slug: str
    skill_name: str
    required_by_type: str
    required_by_id: Optional[str] = None
    gap_status: str
    confidence: str
    evidence_count: int = 0
    missing_evidence: list[dict[str, Any]] = Field(default_factory=list)
    reason_summary: str
    recommendation_summary: Optional[str] = None
    calculation_metadata_json: dict[str, Any] = Field(default_factory=dict)
    evidence: list[SkillGapEvidenceResponse] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SkillGapRunSummaryResponse(BaseModel):
    run_uid: str
    user_id: str
    job_id: Optional[int] = None
    target_role_slug: Optional[str] = None
    source_scope: str
    source_service: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    required_skill_count: int = 0
    missing_skill_count: int = 0
    evidenced_skill_count: int = 0
    learning_skill_count: int = 0
    validated_skill_count: int = 0
    insufficient_data_count: int = 0
    confidence: str
    failure_reason: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class SkillGapAnalysisResponse(BaseModel):
    run_uid: str
    status: str
    summary: SkillGapSummaryResponse
    findings: list[SkillGapFindingResponse] = Field(default_factory=list)


class SkillGapRunListResponse(BaseModel):
    status: str
    total: int
    runs: list[SkillGapRunSummaryResponse] = Field(default_factory=list)


class SkillGapFindingListResponse(BaseModel):
    status: str
    total: int
    findings: list[SkillGapFindingResponse] = Field(default_factory=list)


class SkillGapRunDetailResponse(BaseModel):
    status: str
    run: SkillGapRunSummaryResponse
    summary: SkillGapSummaryResponse
    findings: list[SkillGapFindingResponse] = Field(default_factory=list)


class SkillGapSnapshotResponse(BaseModel):
    status: str
    snapshot_uid: str
    user_id: str
    target_role_slug: Optional[str] = None
    job_id: Optional[int] = None
    run_uid: str
    summary_json: dict[str, Any] = Field(default_factory=dict)
    missing_count: int = 0
    learning_count: int = 0
    evidenced_count: int = 0
    validated_count: int = 0
    insufficient_data_count: int = 0
    created_at: Optional[str] = None
    latest_run: Optional[SkillGapRunSummaryResponse] = None
    findings: list[SkillGapFindingResponse] = Field(default_factory=list)


class SkillGapSkillEvidenceResponse(BaseModel):
    status: str
    skill_slug: str
    evidence: list[SkillGapEvidenceResponse] = Field(default_factory=list)
    total: int = 0


class SkillGapJobResponse(BaseModel):
    status: str
    job_id: int
    latest_run: Optional[SkillGapRunSummaryResponse] = None
    summary: SkillGapSummaryResponse = Field(default_factory=SkillGapSummaryResponse)
    findings: list[SkillGapFindingResponse] = Field(default_factory=list)


class SkillGapUserResponse(BaseModel):
    status: str
    snapshot: Optional[SkillGapSnapshotResponse] = None
