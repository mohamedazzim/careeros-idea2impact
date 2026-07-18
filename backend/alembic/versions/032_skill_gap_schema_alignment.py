"""032 - Align the skill-gap schema with its SQLAlchemy models.

Revision ID: 032_skill_gap_schema_alignment
Revises: 031_skill_gap_engine
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "032_skill_gap_schema_alignment"
down_revision = "031_skill_gap_engine"
branch_labels = None
depends_on = None


def _rename_column_if_needed(table: str, old_name: str, new_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = '{table}'
                      AND column_name = '{old_name}'
                ) AND NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = '{table}'
                      AND column_name = '{new_name}'
                ) THEN
                    ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name};
                END IF;
            END $$;
            """
        )
    )


def _add_job_foreign_key_if_needed(table: str, constraint_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = '{constraint_name}'
                      AND conrelid = '{table}'::regclass
                ) THEN
                    ALTER TABLE {table}
                    ADD CONSTRAINT {constraint_name}
                    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL;
                END IF;
            END $$;
            """
        )
    )


def _create_index_if_needed(name: str, table: str, columns: str) -> None:
    op.execute(sa.text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})"))


def upgrade() -> None:
    _rename_column_if_needed("skill_gap_analysis_runs", "metadata_json", "metadata")
    _rename_column_if_needed("skill_gap_finding_evidence", "metadata", "metadata_json")

    op.alter_column(
        "skill_gap_findings",
        "skill_node_uid",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=True,
    )
    op.alter_column(
        "skill_gap_finding_evidence",
        "evidence_strength",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )

    _add_job_foreign_key_if_needed(
        "skill_gap_analysis_runs", "fk_skill_gap_analysis_runs_job_id"
    )
    _add_job_foreign_key_if_needed("skill_gap_findings", "fk_skill_gap_findings_job_id")
    _add_job_foreign_key_if_needed(
        "user_skill_gap_snapshots", "fk_user_skill_gap_snapshots_job_id"
    )

    indexes = (
        ("ix_skill_gap_analysis_runs_user_id", "skill_gap_analysis_runs", "user_id"),
        ("ix_skill_gap_analysis_runs_job_id", "skill_gap_analysis_runs", "job_id"),
        ("ix_skill_gap_analysis_runs_target_role_slug", "skill_gap_analysis_runs", "target_role_slug"),
        ("ix_skill_gap_analysis_runs_source_scope", "skill_gap_analysis_runs", "source_scope"),
        ("ix_skill_gap_analysis_runs_status", "skill_gap_analysis_runs", "status"),
        ("ix_skill_gap_analysis_runs_started_at", "skill_gap_analysis_runs", "started_at"),
        ("ix_skill_gap_analysis_runs_completed_at", "skill_gap_analysis_runs", "completed_at"),
        ("ix_skill_gap_analysis_runs_confidence", "skill_gap_analysis_runs", "confidence"),
        ("ix_skill_gap_analysis_runs_created_at", "skill_gap_analysis_runs", "created_at"),
        ("ix_skill_gap_analysis_runs_user_scope", "skill_gap_analysis_runs", "user_id, source_scope"),
        ("ix_skill_gap_analysis_runs_user_job", "skill_gap_analysis_runs", "user_id, job_id"),
        ("ix_skill_gap_analysis_runs_scope_status", "skill_gap_analysis_runs", "source_scope, status"),
        ("ix_skill_gap_findings_run_uid", "skill_gap_findings", "run_uid"),
        ("ix_skill_gap_findings_user_id", "skill_gap_findings", "user_id"),
        ("ix_skill_gap_findings_job_id", "skill_gap_findings", "job_id"),
        ("ix_skill_gap_findings_skill_node_uid", "skill_gap_findings", "skill_node_uid"),
        ("ix_skill_gap_findings_skill_slug", "skill_gap_findings", "skill_slug"),
        ("ix_skill_gap_findings_required_by_type", "skill_gap_findings", "required_by_type"),
        ("ix_skill_gap_findings_required_by_id", "skill_gap_findings", "required_by_id"),
        ("ix_skill_gap_findings_gap_status", "skill_gap_findings", "gap_status"),
        ("ix_skill_gap_findings_confidence", "skill_gap_findings", "confidence"),
        ("ix_skill_gap_findings_created_at", "skill_gap_findings", "created_at"),
        ("ix_skill_gap_findings_user_skill", "skill_gap_findings", "user_id, skill_slug"),
        ("ix_skill_gap_findings_run_status", "skill_gap_findings", "run_uid, gap_status"),
        ("ix_skill_gap_finding_evidence_finding_uid", "skill_gap_finding_evidence", "finding_uid"),
        ("ix_skill_gap_finding_evidence_user_id", "skill_gap_finding_evidence", "user_id"),
        ("ix_skill_gap_finding_evidence_skill_slug", "skill_gap_finding_evidence", "skill_slug"),
        ("ix_skill_gap_finding_evidence_evidence_type", "skill_gap_finding_evidence", "evidence_type"),
        ("ix_skill_gap_finding_evidence_source_table", "skill_gap_finding_evidence", "source_table"),
        ("ix_skill_gap_finding_evidence_source_id", "skill_gap_finding_evidence", "source_id"),
        ("ix_skill_gap_finding_evidence_evidence_strength", "skill_gap_finding_evidence", "evidence_strength"),
        ("ix_skill_gap_finding_evidence_supports_status", "skill_gap_finding_evidence", "supports_status"),
        ("ix_skill_gap_finding_evidence_confidence", "skill_gap_finding_evidence", "confidence"),
        ("ix_skill_gap_finding_evidence_created_at", "skill_gap_finding_evidence", "created_at"),
        ("ix_skill_gap_finding_evidence_user_skill", "skill_gap_finding_evidence", "user_id, skill_slug"),
        ("ix_skill_gap_finding_evidence_type", "skill_gap_finding_evidence", "evidence_type, supports_status"),
        ("ix_user_skill_gap_snapshots_user_id", "user_skill_gap_snapshots", "user_id"),
        ("ix_user_skill_gap_snapshots_target_role_slug", "user_skill_gap_snapshots", "target_role_slug"),
        ("ix_user_skill_gap_snapshots_job_id", "user_skill_gap_snapshots", "job_id"),
        ("ix_user_skill_gap_snapshots_run_uid", "user_skill_gap_snapshots", "run_uid"),
        ("ix_user_skill_gap_snapshots_created_at", "user_skill_gap_snapshots", "created_at"),
        ("ix_user_skill_gap_snapshots_user_job", "user_skill_gap_snapshots", "user_id, job_id"),
        ("ix_user_skill_gap_snapshots_user_role", "user_skill_gap_snapshots", "user_id, target_role_slug"),
    )
    for name, table, columns in indexes:
        _create_index_if_needed(name, table, columns)


def downgrade() -> None:
    index_names = (
        "ix_user_skill_gap_snapshots_user_role",
        "ix_user_skill_gap_snapshots_user_job",
        "ix_user_skill_gap_snapshots_created_at",
        "ix_user_skill_gap_snapshots_run_uid",
        "ix_user_skill_gap_snapshots_job_id",
        "ix_user_skill_gap_snapshots_target_role_slug",
        "ix_user_skill_gap_snapshots_user_id",
        "ix_skill_gap_finding_evidence_type",
        "ix_skill_gap_finding_evidence_user_skill",
        "ix_skill_gap_finding_evidence_created_at",
        "ix_skill_gap_finding_evidence_confidence",
        "ix_skill_gap_finding_evidence_supports_status",
        "ix_skill_gap_finding_evidence_evidence_strength",
        "ix_skill_gap_finding_evidence_source_id",
        "ix_skill_gap_finding_evidence_source_table",
        "ix_skill_gap_finding_evidence_evidence_type",
        "ix_skill_gap_finding_evidence_skill_slug",
        "ix_skill_gap_finding_evidence_user_id",
        "ix_skill_gap_finding_evidence_finding_uid",
        "ix_skill_gap_findings_run_status",
        "ix_skill_gap_findings_user_skill",
        "ix_skill_gap_findings_created_at",
        "ix_skill_gap_findings_confidence",
        "ix_skill_gap_findings_gap_status",
        "ix_skill_gap_findings_required_by_id",
        "ix_skill_gap_findings_required_by_type",
        "ix_skill_gap_findings_skill_slug",
        "ix_skill_gap_findings_skill_node_uid",
        "ix_skill_gap_findings_job_id",
        "ix_skill_gap_findings_user_id",
        "ix_skill_gap_findings_run_uid",
        "ix_skill_gap_analysis_runs_scope_status",
        "ix_skill_gap_analysis_runs_user_job",
        "ix_skill_gap_analysis_runs_user_scope",
        "ix_skill_gap_analysis_runs_created_at",
        "ix_skill_gap_analysis_runs_confidence",
        "ix_skill_gap_analysis_runs_completed_at",
        "ix_skill_gap_analysis_runs_started_at",
        "ix_skill_gap_analysis_runs_status",
        "ix_skill_gap_analysis_runs_source_scope",
        "ix_skill_gap_analysis_runs_target_role_slug",
        "ix_skill_gap_analysis_runs_job_id",
        "ix_skill_gap_analysis_runs_user_id",
    )
    for name in index_names:
        op.execute(sa.text(f"DROP INDEX IF EXISTS {name}"))

    for table, constraint_name in (
        ("skill_gap_analysis_runs", "fk_skill_gap_analysis_runs_job_id"),
        ("skill_gap_findings", "fk_skill_gap_findings_job_id"),
        ("user_skill_gap_snapshots", "fk_user_skill_gap_snapshots_job_id"),
    ):
        op.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint_name}"))

    op.alter_column(
        "skill_gap_finding_evidence",
        "evidence_strength",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        "skill_gap_findings",
        "skill_node_uid",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
    _rename_column_if_needed("skill_gap_finding_evidence", "metadata_json", "metadata")
    _rename_column_if_needed("skill_gap_analysis_runs", "metadata", "metadata_json")
