"""031 - Add evidence-backed skill gap analysis tables.

Revision ID: 031_skill_gap_engine
Revises: 030_skill_graph_schema
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa

revision = "031_skill_gap_engine"
down_revision = "030_skill_graph_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_gap_analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_uid", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("target_role_slug", sa.String(length=128), nullable=True),
        sa.Column("source_scope", sa.String(length=32), nullable=False, server_default=sa.text("'job'")),
        sa.Column("source_service", sa.String(length=128), nullable=False, server_default=sa.text("'services.skill_gap.skill_gap_engine'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'running'")),
        sa.Column("required_skill_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("missing_skill_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("learning_skill_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("evidenced_skill_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("validated_skill_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("insufficient_data_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default=sa.text("'low'")),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("run_uid", name="uq_skill_gap_analysis_runs_run_uid"),
    )
    op.create_table(
        "skill_gap_findings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("finding_uid", sa.String(length=64), nullable=False),
        sa.Column("run_uid", sa.String(length=64), sa.ForeignKey("skill_gap_analysis_runs.run_uid", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("skill_node_uid", sa.String(length=64), nullable=True),
        sa.Column("skill_slug", sa.String(length=128), nullable=False),
        sa.Column("skill_name", sa.String(length=256), nullable=False),
        sa.Column("required_by_type", sa.String(length=32), nullable=False),
        sa.Column("required_by_id", sa.String(length=128), nullable=True),
        sa.Column("gap_status", sa.String(length=32), nullable=False, server_default=sa.text("'missing'")),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default=sa.text("'low'")),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("missing_evidence_json", sa.JSON(), nullable=True),
        sa.Column("reason_summary", sa.Text(), nullable=False),
        sa.Column("recommendation_summary", sa.Text(), nullable=True),
        sa.Column("calculation_metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("finding_uid", name="uq_skill_gap_findings_finding_uid"),
        sa.UniqueConstraint("run_uid", "skill_slug", "required_by_type", "required_by_id", name="uq_skill_gap_findings_run_skill_source"),
    )
    op.create_table(
        "skill_gap_finding_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("evidence_uid", sa.String(length=64), nullable=False),
        sa.Column("finding_uid", sa.String(length=64), sa.ForeignKey("skill_gap_findings.finding_uid", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("skill_slug", sa.String(length=128), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("evidence_strength", sa.String(length=32), nullable=False, server_default=sa.text("'weak'")),
        sa.Column("supports_status", sa.String(length=32), nullable=False, server_default=sa.text("'insufficient_data'")),
        sa.Column("quote_or_snippet", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default=sa.text("'low'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("evidence_uid", name="uq_skill_gap_finding_evidence_evidence_uid"),
    )
    op.create_table(
        "user_skill_gap_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("snapshot_uid", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("target_role_slug", sa.String(length=128), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("run_uid", sa.String(length=64), sa.ForeignKey("skill_gap_analysis_runs.run_uid", ondelete="CASCADE"), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("learning_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("evidenced_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("validated_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("insufficient_data_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("snapshot_uid", name="uq_user_skill_gap_snapshots_snapshot_uid"),
    )

def downgrade() -> None:
    op.drop_index("ix_user_skill_gap_snapshots_run_uid", table_name="user_skill_gap_snapshots")
    op.drop_index("ix_user_skill_gap_snapshots_job_id", table_name="user_skill_gap_snapshots")
    op.drop_index("ix_user_skill_gap_snapshots_target_role_slug", table_name="user_skill_gap_snapshots")
    op.drop_index("ix_user_skill_gap_snapshots_user_id", table_name="user_skill_gap_snapshots")
    op.drop_index("ix_user_skill_gap_snapshots_snapshot_uid", table_name="user_skill_gap_snapshots")
    op.drop_table("user_skill_gap_snapshots")

    op.drop_index("ix_skill_gap_finding_evidence_supports_status", table_name="skill_gap_finding_evidence")
    op.drop_index("ix_skill_gap_finding_evidence_source_table", table_name="skill_gap_finding_evidence")
    op.drop_index("ix_skill_gap_finding_evidence_evidence_type", table_name="skill_gap_finding_evidence")
    op.drop_index("ix_skill_gap_finding_evidence_skill_slug", table_name="skill_gap_finding_evidence")
    op.drop_index("ix_skill_gap_finding_evidence_user_id", table_name="skill_gap_finding_evidence")
    op.drop_index("ix_skill_gap_finding_evidence_evidence_uid", table_name="skill_gap_finding_evidence")
    op.drop_table("skill_gap_finding_evidence")

    op.drop_index("ix_skill_gap_findings_required_by_type", table_name="skill_gap_findings")
    op.drop_index("ix_skill_gap_findings_gap_status", table_name="skill_gap_findings")
    op.drop_index("ix_skill_gap_findings_skill_slug", table_name="skill_gap_findings")
    op.drop_index("ix_skill_gap_findings_job_id", table_name="skill_gap_findings")
    op.drop_index("ix_skill_gap_findings_user_id", table_name="skill_gap_findings")
    op.drop_index("ix_skill_gap_findings_finding_uid", table_name="skill_gap_findings")
    op.drop_table("skill_gap_findings")

    op.drop_index("ix_skill_gap_analysis_runs_completed_at", table_name="skill_gap_analysis_runs")
    op.drop_index("ix_skill_gap_analysis_runs_started_at", table_name="skill_gap_analysis_runs")
    op.drop_index("ix_skill_gap_analysis_runs_status", table_name="skill_gap_analysis_runs")
    op.drop_index("ix_skill_gap_analysis_runs_source_scope", table_name="skill_gap_analysis_runs")
    op.drop_index("ix_skill_gap_analysis_runs_target_role_slug", table_name="skill_gap_analysis_runs")
    op.drop_index("ix_skill_gap_analysis_runs_job_id", table_name="skill_gap_analysis_runs")
    op.drop_index("ix_skill_gap_analysis_runs_user_id", table_name="skill_gap_analysis_runs")
    op.drop_index("ix_skill_gap_analysis_runs_run_uid", table_name="skill_gap_analysis_runs")
    op.drop_table("skill_gap_analysis_runs")
