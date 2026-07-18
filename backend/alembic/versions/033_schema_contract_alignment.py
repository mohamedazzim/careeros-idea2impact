"""Align nullable schema contracts with SQLAlchemy models.

Revision ID: 033_schema_contract_alignment
Revises: 032_skill_gap_schema_alignment
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "033_schema_contract_alignment"
down_revision = "032_skill_gap_schema_alignment"
branch_labels = None
depends_on = None


NOT_NULL_BACKFILLS = (
    ("approval_comments", "created_at", "now()"),
    ("approval_items", "order_index", "0"),
    ("approval_items", "created_at", "now()"),
    ("approval_notifications", "read", "false"),
    ("approval_notifications", "created_at", "now()"),
    ("approvals", "auto_generated", "false"),
    ("approvals", "created_at", "now()"),
    ("approvals", "updated_at", "now()"),
    ("audit_logs", "severity", "'info'"),
    ("audit_logs", "created_at", "now()"),
    ("career_coach_goals", "current_value", "0"),
    ("circuit_states", "state", "'closed'"),
    ("circuit_states", "failure_count", "0"),
    ("circuit_states", "created_at", "now()"),
    ("circuit_states", "updated_at", "now()"),
    ("evaluation_runs", "status", "'pending'"),
    ("evaluation_runs", "progress_pct", "0"),
    ("evaluation_runs", "created_at", "now()"),
    ("generated_packages", "status", "'draft'"),
    ("generated_packages", "created_at", "now()"),
    ("generated_packages", "updated_at", "now()"),
    ("hallucination_audits", "created_at", "now()"),
    ("job_matches", "overall_score", "0"),
    ("job_matches", "skill_match", "0"),
    ("job_matches", "experience_match", "0"),
    ("job_matches", "education_match", "0"),
    ("job_matches", "created_at", "now()"),
    ("jobs", "source", "'unknown'"),
    ("jobs", "status", "'active'"),
    ("jobs", "ingested_at", "now()"),
    ("jobs", "updated_at", "now()"),
    ("knowledge_docs", "source", "'upload'"),
    ("knowledge_docs", "chunk_count", "0"),
    ("knowledge_docs", "status", "'pending'"),
    ("knowledge_docs", "created_at", "now()"),
    ("knowledge_docs", "updated_at", "now()"),
    ("pending_jobs", "status", "'pending'"),
    ("pending_jobs", "priority", "0"),
    ("pending_jobs", "retry_count", "0"),
    ("pending_jobs", "max_retries", "3"),
    ("pending_jobs", "created_at", "now()"),
    ("pending_jobs", "updated_at", "now()"),
    ("resumes", "updated_at", "COALESCE(created_at, now())"),
    ("roadmap_goals", "category", "'general'"),
    ("roadmap_goals", "priority", "0"),
    ("roadmap_goals", "order_index", "0"),
    ("roadmap_goals", "created_at", "now()"),
    ("roadmap_tasks", "completed", "false"),
    ("roadmap_tasks", "order_index", "0"),
    ("roadmap_tasks", "created_at", "now()"),
    ("roadmap_tasks", "updated_at", "now()"),
    ("roadmaps", "status", "'active'"),
    ("roadmaps", "progress_pct", "0"),
    ("roadmaps", "created_at", "now()"),
    ("roadmaps", "updated_at", "now()"),
    ("user_preferences", "alert_threshold", "70"),
    ("user_preferences", "theme", "'dark'"),
    ("user_preferences", "language", "'en'"),
    ("user_preferences", "created_at", "now()"),
    ("user_preferences", "updated_at", "now()"),
)


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _set_not_null(table: str, column: str, fallback_sql: str) -> None:
    table_sql = _quote(table)
    column_sql = _quote(column)
    op.execute(
        sa.text(
            f"UPDATE {table_sql} SET {column_sql} = {fallback_sql} "
            f"WHERE {column_sql} IS NULL"
        )
    )
    op.alter_column(table, column, nullable=False)


def upgrade() -> None:
    for table, column, fallback_sql in NOT_NULL_BACKFILLS:
        _set_not_null(table, column, fallback_sql)


def downgrade() -> None:
    for table, column, _fallback_sql in reversed(NOT_NULL_BACKFILLS):
        op.alter_column(table, column, nullable=True)
