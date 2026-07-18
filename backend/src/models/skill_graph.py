"""Skill graph schema for CareerOS M4.

The graph is additive and evidence-backed:
- canonical skill nodes
- alias records for raw source values
- skill-to-skill edges derived from real co-occurrence data
- evidence rows that preserve provenance
- import runs that summarize refresh activity
- per-user skill states for grounded progress tracking
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class SkillGraphNode(Base):
    __tablename__ = "skill_graph_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    skill_name: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="skill", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="insufficient_data", index=True)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    demand_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_import_run_uid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    aliases: Mapped[list["SkillGraphAlias"]] = relationship("SkillGraphAlias", back_populates="skill_node")
    outgoing_edges: Mapped[list["SkillGraphEdge"]] = relationship(
        "SkillGraphEdge",
        back_populates="source_node",
        foreign_keys="SkillGraphEdge.source_skill_node_id",
    )
    incoming_edges: Mapped[list["SkillGraphEdge"]] = relationship(
        "SkillGraphEdge",
        back_populates="target_node",
        foreign_keys="SkillGraphEdge.target_skill_node_id",
    )
    evidence: Mapped[list["SkillGraphEvidence"]] = relationship("SkillGraphEvidence", back_populates="skill_node")
    user_states: Mapped[list["UserSkillState"]] = relationship("UserSkillState", back_populates="skill_node")


class SkillGraphAlias(Base):
    __tablename__ = "skill_graph_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alias_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    skill_node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skill_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_value: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    normalized_value: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    source_entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_field: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_table: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_pk: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    alias_type: Mapped[str] = mapped_column(String(64), nullable=False, default="source_value", index=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    skill_node: Mapped["SkillGraphNode"] = relationship(back_populates="aliases")

    __table_args__ = (
        UniqueConstraint(
            "skill_node_id",
            "raw_value",
            "source_entity_type",
            "source_entity_id",
            "source_field",
            name="uq_skill_graph_aliases_source_alias",
        ),
    )


class SkillGraphEdge(Base):
    __tablename__ = "skill_graph_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    edge_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    source_skill_node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skill_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_skill_node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skill_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_table: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_pk: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    relation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    source_node: Mapped["SkillGraphNode"] = relationship(
        back_populates="outgoing_edges",
        foreign_keys=[source_skill_node_id],
    )
    target_node: Mapped["SkillGraphNode"] = relationship(
        back_populates="incoming_edges",
        foreign_keys=[target_skill_node_id],
    )
    evidence: Mapped[list["SkillGraphEvidence"]] = relationship("SkillGraphEvidence", back_populates="edge")

    __table_args__ = (
        UniqueConstraint(
            "source_skill_node_id",
            "target_skill_node_id",
            "edge_type",
            "source_entity_type",
            "source_entity_id",
            name="uq_skill_graph_edge_source_target",
        ),
        Index("ix_skill_graph_edges_pair_type", "source_skill_node_id", "target_skill_node_id", "edge_type"),
    )


class SkillGraphEvidence(Base):
    __tablename__ = "skill_graph_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    skill_node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skill_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edge_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("skill_graph_edges.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_table: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_pk: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_field: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    evidence_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="low", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success", index=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    skill_node: Mapped["SkillGraphNode"] = relationship(back_populates="evidence")
    edge: Mapped[Optional["SkillGraphEdge"]] = relationship(back_populates="evidence")

    __table_args__ = (
        UniqueConstraint(
            "skill_node_id",
            "source_entity_type",
            "source_entity_id",
            "source_field",
            "evidence_kind",
            "raw_value",
            name="uq_skill_graph_evidence_source",
        ),
    )


class SkillGraphImportRun(Base):
    __tablename__ = "skill_graph_import_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="full", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running", index=True)
    strategy: Mapped[str] = mapped_column(String(128), nullable=False, default="real_data_import_v1")
    node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alias_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_state_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_counts: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_skill_graph_import_runs_scope_status", "scope", "status"),
    )


class UserSkillState(Base):
    __tablename__ = "user_skill_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    skill_node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skill_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="insufficient_data", index=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    demand_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    learning_signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resume_signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    feedback_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_import_run_uid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    skill_node: Mapped["SkillGraphNode"] = relationship(back_populates="user_states")

    __table_args__ = (
        UniqueConstraint("user_id", "skill_node_id", name="uq_user_skill_states_user_skill"),
        Index("ix_user_skill_states_user_status", "user_id", "status"),
    )
