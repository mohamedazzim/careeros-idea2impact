"""030 - Add skill graph schema and import ledger.

Revision ID: 030_skill_graph_schema
Revises: 029_learning_outcome_tracking
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa

revision = "030_skill_graph_schema"
down_revision = "029_learning_outcome_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_graph_nodes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("skill_slug", sa.String(length=128), nullable=False),
        sa.Column("skill_name", sa.String(length=256), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False, server_default=sa.text("'skill'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'insufficient_data'")),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("user_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("demand_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("supply_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("freshness_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_import_run_uid", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("skill_slug", name="uq_skill_graph_nodes_skill_slug"),
    )
    op.create_index("ix_skill_graph_nodes_skill_slug", "skill_graph_nodes", ["skill_slug"])
    op.create_index("ix_skill_graph_nodes_category", "skill_graph_nodes", ["category"])
    op.create_index("ix_skill_graph_nodes_status", "skill_graph_nodes", ["status"])
    op.create_index("ix_skill_graph_nodes_first_seen_at", "skill_graph_nodes", ["first_seen_at"])
    op.create_index("ix_skill_graph_nodes_last_seen_at", "skill_graph_nodes", ["last_seen_at"])
    op.create_index("ix_skill_graph_nodes_last_import_run_uid", "skill_graph_nodes", ["last_import_run_uid"])

    op.create_table(
        "skill_graph_import_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_uid", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False, server_default=sa.text("'full'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'running'")),
        sa.Column("strategy", sa.String(length=128), nullable=False, server_default=sa.text("'real_data_import_v1'")),
        sa.Column("node_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("edge_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("alias_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("user_state_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("source_counts", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("run_uid", name="uq_skill_graph_import_runs_run_uid"),
    )
    op.create_index("ix_skill_graph_import_runs_run_uid", "skill_graph_import_runs", ["run_uid"])
    op.create_index("ix_skill_graph_import_runs_user_id", "skill_graph_import_runs", ["user_id"])
    op.create_index("ix_skill_graph_import_runs_scope", "skill_graph_import_runs", ["scope"])
    op.create_index("ix_skill_graph_import_runs_status", "skill_graph_import_runs", ["status"])
    op.create_index("ix_skill_graph_import_runs_started_at", "skill_graph_import_runs", ["started_at"])
    op.create_index("ix_skill_graph_import_runs_completed_at", "skill_graph_import_runs", ["completed_at"])
    op.create_index("ix_skill_graph_import_runs_scope_status", "skill_graph_import_runs", ["scope", "status"])

    op.create_table(
        "skill_graph_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alias_uid", sa.String(length=64), nullable=False),
        sa.Column("skill_node_id", sa.Integer(), sa.ForeignKey("skill_graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_value", sa.String(length=256), nullable=False),
        sa.Column("normalized_value", sa.String(length=256), nullable=False),
        sa.Column("source_entity_type", sa.String(length=64), nullable=False),
        sa.Column("source_entity_id", sa.String(length=128), nullable=False),
        sa.Column("source_field", sa.String(length=128), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=True),
        sa.Column("source_pk", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("alias_type", sa.String(length=64), nullable=False, server_default=sa.text("'source_value'")),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("alias_uid", name="uq_skill_graph_aliases_alias_uid"),
        sa.UniqueConstraint(
            "skill_node_id",
            "raw_value",
            "source_entity_type",
            "source_entity_id",
            "source_field",
            name="uq_skill_graph_aliases_source_alias",
        ),
    )
    op.create_index("ix_skill_graph_aliases_alias_uid", "skill_graph_aliases", ["alias_uid"])
    op.create_index("ix_skill_graph_aliases_skill_node_id", "skill_graph_aliases", ["skill_node_id"])
    op.create_index("ix_skill_graph_aliases_raw_value", "skill_graph_aliases", ["raw_value"])
    op.create_index("ix_skill_graph_aliases_normalized_value", "skill_graph_aliases", ["normalized_value"])
    op.create_index("ix_skill_graph_aliases_source_entity_type", "skill_graph_aliases", ["source_entity_type"])
    op.create_index("ix_skill_graph_aliases_source_entity_id", "skill_graph_aliases", ["source_entity_id"])
    op.create_index("ix_skill_graph_aliases_source_field", "skill_graph_aliases", ["source_field"])
    op.create_index("ix_skill_graph_aliases_provider", "skill_graph_aliases", ["provider"])
    op.create_index("ix_skill_graph_aliases_alias_type", "skill_graph_aliases", ["alias_type"])

    op.create_table(
        "skill_graph_edges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("edge_uid", sa.String(length=64), nullable=False),
        sa.Column("source_skill_node_id", sa.Integer(), sa.ForeignKey("skill_graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_skill_node_id", sa.Integer(), sa.ForeignKey("skill_graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("edge_type", sa.String(length=64), nullable=False),
        sa.Column("source_entity_type", sa.String(length=64), nullable=False),
        sa.Column("source_entity_id", sa.String(length=128), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=True),
        sa.Column("source_pk", sa.String(length=128), nullable=True),
        sa.Column("source_title", sa.String(length=512), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1")),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("relation_summary", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("edge_uid", name="uq_skill_graph_edges_edge_uid"),
        sa.UniqueConstraint(
            "source_skill_node_id",
            "target_skill_node_id",
            "edge_type",
            "source_entity_type",
            "source_entity_id",
            name="uq_skill_graph_edge_source_target",
        ),
    )
    op.create_index("ix_skill_graph_edges_edge_uid", "skill_graph_edges", ["edge_uid"])
    op.create_index("ix_skill_graph_edges_source_skill_node_id", "skill_graph_edges", ["source_skill_node_id"])
    op.create_index("ix_skill_graph_edges_target_skill_node_id", "skill_graph_edges", ["target_skill_node_id"])
    op.create_index("ix_skill_graph_edges_edge_type", "skill_graph_edges", ["edge_type"])
    op.create_index("ix_skill_graph_edges_source_entity_type", "skill_graph_edges", ["source_entity_type"])
    op.create_index("ix_skill_graph_edges_source_entity_id", "skill_graph_edges", ["source_entity_id"])
    op.create_index("ix_skill_graph_edges_provider", "skill_graph_edges", ["provider"])
    op.create_index("ix_skill_graph_edges_pair_type", "skill_graph_edges", ["source_skill_node_id", "target_skill_node_id", "edge_type"])

    op.create_table(
        "skill_graph_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("evidence_uid", sa.String(length=64), nullable=False),
        sa.Column("skill_node_id", sa.Integer(), sa.ForeignKey("skill_graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("edge_id", sa.Integer(), sa.ForeignKey("skill_graph_edges.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_entity_type", sa.String(length=64), nullable=False),
        sa.Column("source_entity_id", sa.String(length=128), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=True),
        sa.Column("source_pk", sa.String(length=128), nullable=True),
        sa.Column("source_field", sa.String(length=128), nullable=False),
        sa.Column("source_title", sa.String(length=512), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("evidence_kind", sa.String(length=64), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.String(length=256), nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("freshness_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default=sa.text("'low'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'success'")),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("evidence_uid", name="uq_skill_graph_evidence_evidence_uid"),
        sa.UniqueConstraint(
            "skill_node_id",
            "source_entity_type",
            "source_entity_id",
            "source_field",
            "evidence_kind",
            "raw_value",
            name="uq_skill_graph_evidence_source",
        ),
    )
    op.create_index("ix_skill_graph_evidence_evidence_uid", "skill_graph_evidence", ["evidence_uid"])
    op.create_index("ix_skill_graph_evidence_skill_node_id", "skill_graph_evidence", ["skill_node_id"])
    op.create_index("ix_skill_graph_evidence_edge_id", "skill_graph_evidence", ["edge_id"])
    op.create_index("ix_skill_graph_evidence_source_entity_type", "skill_graph_evidence", ["source_entity_type"])
    op.create_index("ix_skill_graph_evidence_source_entity_id", "skill_graph_evidence", ["source_entity_id"])
    op.create_index("ix_skill_graph_evidence_source_table", "skill_graph_evidence", ["source_table"])
    op.create_index("ix_skill_graph_evidence_source_field", "skill_graph_evidence", ["source_field"])
    op.create_index("ix_skill_graph_evidence_provider", "skill_graph_evidence", ["provider"])
    op.create_index("ix_skill_graph_evidence_evidence_kind", "skill_graph_evidence", ["evidence_kind"])
    op.create_index("ix_skill_graph_evidence_confidence", "skill_graph_evidence", ["confidence"])
    op.create_index("ix_skill_graph_evidence_status", "skill_graph_evidence", ["status"])
    op.create_index("ix_skill_graph_evidence_normalized_value", "skill_graph_evidence", ["normalized_value"])

    op.create_table(
        "user_skill_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("state_uid", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("skill_node_id", sa.Integer(), sa.ForeignKey("skill_graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'insufficient_data'")),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("demand_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("supply_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("learning_signal_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("resume_signal_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("feedback_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("average_rating", sa.Float(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(), nullable=True),
        sa.Column("last_import_run_uid", sa.String(length=64), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("evidence_summary", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("state_uid", name="uq_user_skill_states_state_uid"),
        sa.UniqueConstraint("user_id", "skill_node_id", name="uq_user_skill_states_user_skill"),
    )
    op.create_index("ix_user_skill_states_state_uid", "user_skill_states", ["state_uid"])
    op.create_index("ix_user_skill_states_user_id", "user_skill_states", ["user_id"])
    op.create_index("ix_user_skill_states_skill_node_id", "user_skill_states", ["skill_node_id"])
    op.create_index("ix_user_skill_states_status", "user_skill_states", ["status"])
    op.create_index("ix_user_skill_states_last_activity_at", "user_skill_states", ["last_activity_at"])
    op.create_index("ix_user_skill_states_last_import_run_uid", "user_skill_states", ["last_import_run_uid"])
    op.create_index("ix_user_skill_states_user_status", "user_skill_states", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_user_skill_states_user_status", table_name="user_skill_states")
    op.drop_index("ix_user_skill_states_last_import_run_uid", table_name="user_skill_states")
    op.drop_index("ix_user_skill_states_last_activity_at", table_name="user_skill_states")
    op.drop_index("ix_user_skill_states_status", table_name="user_skill_states")
    op.drop_index("ix_user_skill_states_skill_node_id", table_name="user_skill_states")
    op.drop_index("ix_user_skill_states_user_id", table_name="user_skill_states")
    op.drop_index("ix_user_skill_states_state_uid", table_name="user_skill_states")
    op.drop_table("user_skill_states")

    op.drop_index("ix_skill_graph_evidence_status", table_name="skill_graph_evidence")
    op.drop_index("ix_skill_graph_evidence_confidence", table_name="skill_graph_evidence")
    op.drop_index("ix_skill_graph_evidence_normalized_value", table_name="skill_graph_evidence")
    op.drop_index("ix_skill_graph_evidence_evidence_kind", table_name="skill_graph_evidence")
    op.drop_index("ix_skill_graph_evidence_provider", table_name="skill_graph_evidence")
    op.drop_index("ix_skill_graph_evidence_source_field", table_name="skill_graph_evidence")
    op.drop_index("ix_skill_graph_evidence_source_table", table_name="skill_graph_evidence")
    op.drop_index("ix_skill_graph_evidence_source_entity_id", table_name="skill_graph_evidence")
    op.drop_index("ix_skill_graph_evidence_source_entity_type", table_name="skill_graph_evidence")
    op.drop_index("ix_skill_graph_evidence_edge_id", table_name="skill_graph_evidence")
    op.drop_index("ix_skill_graph_evidence_skill_node_id", table_name="skill_graph_evidence")
    op.drop_index("ix_skill_graph_evidence_evidence_uid", table_name="skill_graph_evidence")
    op.drop_table("skill_graph_evidence")

    op.drop_index("ix_skill_graph_edges_pair_type", table_name="skill_graph_edges")
    op.drop_index("ix_skill_graph_edges_provider", table_name="skill_graph_edges")
    op.drop_index("ix_skill_graph_edges_source_entity_id", table_name="skill_graph_edges")
    op.drop_index("ix_skill_graph_edges_source_entity_type", table_name="skill_graph_edges")
    op.drop_index("ix_skill_graph_edges_edge_type", table_name="skill_graph_edges")
    op.drop_index("ix_skill_graph_edges_target_skill_node_id", table_name="skill_graph_edges")
    op.drop_index("ix_skill_graph_edges_source_skill_node_id", table_name="skill_graph_edges")
    op.drop_index("ix_skill_graph_edges_edge_uid", table_name="skill_graph_edges")
    op.drop_table("skill_graph_edges")

    op.drop_index("ix_skill_graph_aliases_alias_type", table_name="skill_graph_aliases")
    op.drop_index("ix_skill_graph_aliases_provider", table_name="skill_graph_aliases")
    op.drop_index("ix_skill_graph_aliases_source_field", table_name="skill_graph_aliases")
    op.drop_index("ix_skill_graph_aliases_source_entity_id", table_name="skill_graph_aliases")
    op.drop_index("ix_skill_graph_aliases_source_entity_type", table_name="skill_graph_aliases")
    op.drop_index("ix_skill_graph_aliases_normalized_value", table_name="skill_graph_aliases")
    op.drop_index("ix_skill_graph_aliases_raw_value", table_name="skill_graph_aliases")
    op.drop_index("ix_skill_graph_aliases_skill_node_id", table_name="skill_graph_aliases")
    op.drop_index("ix_skill_graph_aliases_alias_uid", table_name="skill_graph_aliases")
    op.drop_table("skill_graph_aliases")

    op.drop_index("ix_skill_graph_import_runs_scope_status", table_name="skill_graph_import_runs")
    op.drop_index("ix_skill_graph_import_runs_completed_at", table_name="skill_graph_import_runs")
    op.drop_index("ix_skill_graph_import_runs_started_at", table_name="skill_graph_import_runs")
    op.drop_index("ix_skill_graph_import_runs_status", table_name="skill_graph_import_runs")
    op.drop_index("ix_skill_graph_import_runs_scope", table_name="skill_graph_import_runs")
    op.drop_index("ix_skill_graph_import_runs_user_id", table_name="skill_graph_import_runs")
    op.drop_index("ix_skill_graph_import_runs_run_uid", table_name="skill_graph_import_runs")
    op.drop_table("skill_graph_import_runs")

    op.drop_index("ix_skill_graph_nodes_last_import_run_uid", table_name="skill_graph_nodes")
    op.drop_index("ix_skill_graph_nodes_last_seen_at", table_name="skill_graph_nodes")
    op.drop_index("ix_skill_graph_nodes_first_seen_at", table_name="skill_graph_nodes")
    op.drop_index("ix_skill_graph_nodes_status", table_name="skill_graph_nodes")
    op.drop_index("ix_skill_graph_nodes_category", table_name="skill_graph_nodes")
    op.drop_index("ix_skill_graph_nodes_skill_slug", table_name="skill_graph_nodes")
    op.drop_table("skill_graph_nodes")
