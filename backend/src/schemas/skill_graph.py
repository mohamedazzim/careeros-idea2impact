"""Pydantic schemas for the CareerOS skill graph APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SkillGraphImportRequest(BaseModel):
    scope: Literal["full"] = "full"
    include_user_states: bool = True
    include_edges: bool = True
    include_evidence: bool = True
    notes: Optional[str] = None


class SkillGraphNodeResponse(BaseModel):
    skill_slug: str
    skill_name: str
    category: str
    status: str
    evidence_count: int
    source_count: int
    user_count: int
    demand_count: int
    supply_count: int
    trust_score: float
    relevance_score: float
    freshness_score: float
    confidence_score: float
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    last_import_run_uid: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillGraphAliasResponse(BaseModel):
    raw_value: str
    normalized_value: str
    source_entity_type: str
    source_entity_id: str
    source_field: str
    source_table: Optional[str] = None
    source_pk: Optional[str] = None
    provider: Optional[str] = None
    alias_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class SkillGraphEdgeResponse(BaseModel):
    edge_uid: str
    source_skill_slug: str
    source_skill_name: str
    target_skill_slug: str
    target_skill_name: str
    edge_type: str
    source_entity_type: str
    source_entity_id: str
    source_table: Optional[str] = None
    source_pk: Optional[str] = None
    source_title: Optional[str] = None
    provider: Optional[str] = None
    weight: float
    evidence_count: int
    confidence_score: float
    relation_summary: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None


class SkillGraphEvidenceResponse(BaseModel):
    evidence_uid: str
    skill_slug: str
    skill_name: str
    source_entity_type: str
    source_entity_id: str
    source_table: Optional[str] = None
    source_pk: Optional[str] = None
    source_field: str
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    provider: Optional[str] = None
    evidence_kind: str
    raw_value: str
    normalized_value: str
    trust_score: float
    relevance_score: float
    freshness_score: float
    confidence: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_at: Optional[str] = None


class SkillGraphUserStateResponse(BaseModel):
    state_uid: str
    user_id: str
    skill_slug: str
    skill_name: str
    category: str
    status: str
    confidence_score: float
    evidence_count: int
    demand_count: int
    supply_count: int
    learning_signal_count: int
    resume_signal_count: int
    started_count: int
    completion_count: int
    feedback_count: int
    average_rating: Optional[float] = None
    last_activity_at: Optional[str] = None
    last_import_run_uid: Optional[str] = None
    recommended_action: Optional[str] = None
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillGraphImportRunResponse(BaseModel):
    run_uid: str
    user_id: Optional[str] = None
    scope: str
    status: str
    strategy: str
    node_count: int
    edge_count: int
    evidence_count: int
    alias_count: int
    user_state_count: int
    source_counts: dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SkillGraphSummaryResponse(BaseModel):
    status: str
    total_nodes: int
    total_edges: int
    total_evidence: int
    total_aliases: int
    total_user_states: int
    source_counts: dict[str, Any] = Field(default_factory=dict)
    top_nodes: list[SkillGraphNodeResponse] = Field(default_factory=list)
    user_states: list[SkillGraphUserStateResponse] = Field(default_factory=list)
    latest_import_run: Optional[SkillGraphImportRunResponse] = None


class SkillGraphNodeListResponse(BaseModel):
    status: str
    total: int
    nodes: list[SkillGraphNodeResponse] = Field(default_factory=list)


class SkillGraphStateListResponse(BaseModel):
    status: str
    total: int
    states: list[SkillGraphUserStateResponse] = Field(default_factory=list)


class SkillGraphImportRunListResponse(BaseModel):
    status: str
    total: int
    runs: list[SkillGraphImportRunResponse] = Field(default_factory=list)


class SkillGraphDetailResponse(BaseModel):
    status: str
    node: SkillGraphNodeResponse
    aliases: list[SkillGraphAliasResponse] = Field(default_factory=list)
    edges: list[SkillGraphEdgeResponse] = Field(default_factory=list)
    evidence: list[SkillGraphEvidenceResponse] = Field(default_factory=list)
    user_states: list[SkillGraphUserStateResponse] = Field(default_factory=list)


class SkillGraphImportResponse(BaseModel):
    status: str
    run: SkillGraphImportRunResponse
    node_count: int
    edge_count: int
    evidence_count: int
    alias_count: int
    user_state_count: int
    source_counts: dict[str, Any] = Field(default_factory=dict)


class SkillGraphHealthResponse(BaseModel):
    status: str
    ready: bool
    tables: list[str] = Field(default_factory=list)
    collection: str = "skill_graph"
    message: Optional[str] = None
