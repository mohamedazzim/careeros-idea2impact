"""028 - Add learning resource provenance ledger.

Revision ID: 028_resource_provenance_ledger
Revises: 027_verified_learning_paths
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa

revision = "028_resource_provenance_ledger"
down_revision = "027_verified_learning_paths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_resource_discovery_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_uid", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("skill_slug", sa.String(length=128), nullable=True),
        sa.Column("skill_name", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'running'")),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("stored_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("run_uid", name="uq_learning_resource_discovery_runs_run_uid"),
    )
    op.create_index("ix_learning_resource_discovery_runs_run_uid", "learning_resource_discovery_runs", ["run_uid"])
    op.create_index("ix_learning_resource_discovery_runs_user_id", "learning_resource_discovery_runs", ["user_id"])
    op.create_index("ix_learning_resource_discovery_runs_skill_slug", "learning_resource_discovery_runs", ["skill_slug"])
    op.create_index("ix_learning_resource_discovery_runs_started_at", "learning_resource_discovery_runs", ["started_at"])
    op.create_index("ix_learning_resource_discovery_runs_skill_status", "learning_resource_discovery_runs", ["skill_slug", "status"])

    op.create_table(
        "learning_resource_provenance_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provenance_uid", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("learning_resources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("discovery_run_id", sa.Integer(), sa.ForeignKey("learning_resource_discovery_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("skill_slug", sa.String(length=128), nullable=False),
        sa.Column("skill_name", sa.String(length=128), nullable=False),
        sa.Column("source_entity_type", sa.String(length=64), nullable=False),
        sa.Column("source_entity_id", sa.String(length=128), nullable=False),
        sa.Column("provenance_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=True),
        sa.Column("source_pk", sa.String(length=128), nullable=True),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("freshness_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("score_total", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("score_formula", sa.String(length=256), nullable=False, server_default=sa.text("'trust*0.45 + relevance*0.35 + freshness*0.20'")),
        sa.Column("score_breakdown", sa.JSON(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'success'")),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("provenance_uid", name="uq_learning_resource_provenance_records_uid"),
    )
    op.create_index("ix_learning_resource_provenance_records_provenance_uid", "learning_resource_provenance_records", ["provenance_uid"])
    op.create_index("ix_learning_resource_provenance_records_resource_id", "learning_resource_provenance_records", ["resource_id"])
    op.create_index("ix_learning_resource_provenance_records_discovery_run_id", "learning_resource_provenance_records", ["discovery_run_id"])
    op.create_index("ix_learning_resource_provenance_records_user_id", "learning_resource_provenance_records", ["user_id"])
    op.create_index("ix_learning_resource_provenance_records_skill_slug", "learning_resource_provenance_records", ["skill_slug"])
    op.create_index("ix_learning_resource_provenance_records_source_entity_type", "learning_resource_provenance_records", ["source_entity_type"])
    op.create_index("ix_learning_resource_provenance_records_provenance_type", "learning_resource_provenance_records", ["provenance_type"])
    op.create_index("ix_learning_resource_provenance_records_recorded_at", "learning_resource_provenance_records", ["recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_learning_resource_provenance_records_recorded_at", table_name="learning_resource_provenance_records")
    op.drop_index("ix_learning_resource_provenance_records_provenance_type", table_name="learning_resource_provenance_records")
    op.drop_index("ix_learning_resource_provenance_records_source_entity_type", table_name="learning_resource_provenance_records")
    op.drop_index("ix_learning_resource_provenance_records_skill_slug", table_name="learning_resource_provenance_records")
    op.drop_index("ix_learning_resource_provenance_records_user_id", table_name="learning_resource_provenance_records")
    op.drop_index("ix_learning_resource_provenance_records_discovery_run_id", table_name="learning_resource_provenance_records")
    op.drop_index("ix_learning_resource_provenance_records_resource_id", table_name="learning_resource_provenance_records")
    op.drop_index("ix_learning_resource_provenance_records_provenance_uid", table_name="learning_resource_provenance_records")
    op.drop_table("learning_resource_provenance_records")

    op.drop_index("ix_learning_resource_discovery_runs_skill_status", table_name="learning_resource_discovery_runs")
    op.drop_index("ix_learning_resource_discovery_runs_started_at", table_name="learning_resource_discovery_runs")
    op.drop_index("ix_learning_resource_discovery_runs_skill_slug", table_name="learning_resource_discovery_runs")
    op.drop_index("ix_learning_resource_discovery_runs_user_id", table_name="learning_resource_discovery_runs")
    op.drop_index("ix_learning_resource_discovery_runs_run_uid", table_name="learning_resource_discovery_runs")
    op.drop_table("learning_resource_discovery_runs")
