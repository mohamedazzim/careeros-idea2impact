"""Phase 17.5 — New models migration.

Revision ID: 005
Revises: 004
Create Date: 2026-05-30

Creates tables: jobs, job_matches, approvals, approval_items, approval_comments,
approval_notifications, roadmaps, roadmap_goals, roadmap_tasks, evaluation_runs,
hallucination_audits, user_preferences
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Jobs ─────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("job_uid", sa.String(64), unique=True, nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("company", sa.String(256), nullable=True),
        sa.Column("location", sa.String(256), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(64), server_default="linkedin"),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("salary_range", sa.String(128), nullable=True),
        sa.Column("skills_required", postgresql.JSON(), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("match_details", postgresql.JSON(), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", index=True),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.text("now()"), index=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_jobs_source_status", "jobs", ["source", "status"])
    op.create_index("ix_jobs_title_search", "jobs", ["title"])

    op.create_table(
        "job_matches",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("job_id", sa.Integer(), nullable=False, index=True),
        sa.Column("overall_score", sa.Float(), default=0.0),
        sa.Column("skill_match", sa.Float(), default=0.0),
        sa.Column("experience_match", sa.Float(), default=0.0),
        sa.Column("education_match", sa.Float(), default=0.0),
        sa.Column("strengths", postgresql.JSON(), nullable=True),
        sa.Column("gaps", postgresql.JSON(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_job_matches_user_job", "job_matches", ["user_id", "job_id"])

    # ── Approvals ────────────────────────────────────────────────────
    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("approval_uid", sa.String(64), unique=True, nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("channel", sa.String(64), nullable=False, server_default="linkedin"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending", index=True),
        sa.Column("draft_content", postgresql.JSON(), nullable=True),
        sa.Column("final_content", postgresql.JSON(), nullable=True),
        sa.Column("auto_generated", sa.Boolean(), default=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("execution_status", sa.String(32), nullable=True),
        sa.Column("execution_result", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), index=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_approvals_user_status", "approvals", ["user_id", "status"])
    op.create_index("ix_approvals_channel", "approvals", ["channel"])

    op.create_table(
        "approval_items",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("approval_id", sa.Integer(), sa.ForeignKey("approvals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("item_type", sa.String(64), nullable=False),
        sa.Column("content", postgresql.JSON(), nullable=True),
        sa.Column("metadata", postgresql.JSON(), nullable=True),
        sa.Column("order_index", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.create_table(
        "approval_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("approval_id", sa.Integer(), sa.ForeignKey("approvals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.create_table(
        "approval_notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("notification_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("read", sa.Boolean(), default=False),
        sa.Column("related_approval_id", sa.Integer(), index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), index=True),
    )
    op.create_index("ix_approval_notif_user_read", "approval_notifications", ["user_id", "read"])

    # ── Roadmaps ─────────────────────────────────────────────────────
    op.create_table(
        "roadmaps",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("roadmap_uid", sa.String(64), unique=True, nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("title", sa.String(512), nullable=False, server_default="Career Roadmap"),
        sa.Column("target_role", sa.String(256), nullable=True),
        sa.Column("target_salary", sa.String(128), nullable=True),
        sa.Column("target_location", sa.String(256), nullable=True),
        sa.Column("target_timeline", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", index=True),
        sa.Column("progress_pct", sa.Float(), default=0.0),
        sa.Column("recommendations", postgresql.JSON(), nullable=True),
        sa.Column("velocity_history", postgresql.JSON(), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), index=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.create_table(
        "roadmap_goals",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("roadmap_id", sa.Integer(), sa.ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), default="skill"),
        sa.Column("priority", sa.Integer(), default=1),
        sa.Column("order_index", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.create_table(
        "roadmap_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("task_uid", sa.String(64), unique=True, nullable=False),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("roadmap_goals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("completed", sa.Boolean(), default=False),
        sa.Column("due_date", sa.String(64), nullable=True),
        sa.Column("order_index", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # ── Evaluation ───────────────────────────────────────────────────
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("run_uid", sa.String(64), unique=True, nullable=False),
        sa.Column("user_id", sa.String(128), index=True, nullable=True),
        sa.Column("benchmark_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", index=True),
        sa.Column("progress_pct", sa.Float(), default=0.0),
        sa.Column("metrics", postgresql.JSON(), nullable=True),
        sa.Column("results", postgresql.JSON(), nullable=True),
        sa.Column("errors", postgresql.JSON(), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), index=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_eval_runs_benchmark_status", "evaluation_runs", ["benchmark_name", "status"])

    op.create_table(
        "hallucination_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(128), index=True, nullable=True),
        sa.Column("run_id", sa.String(64), index=True, nullable=True),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column("is_hallucination", sa.Boolean(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("keywords_detected", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # ── User Preferences ─────────────────────────────────────────────
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("notification_email", sa.String(320), nullable=True),
        sa.Column("alert_threshold", sa.Integer(), server_default="75"),
        sa.Column("quiet_hours_start", sa.String(8), nullable=True),
        sa.Column("quiet_hours_end", sa.String(8), nullable=True),
        sa.Column("theme", sa.String(32), server_default="system"),
        sa.Column("language", sa.String(16), server_default="en"),
        sa.Column("extra", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_table("hallucination_audits")
    op.drop_table("evaluation_runs")
    op.drop_table("roadmap_tasks")
    op.drop_table("roadmap_goals")
    op.drop_table("roadmaps")
    op.drop_table("approval_notifications")
    op.drop_table("approval_comments")
    op.drop_table("approval_items")
    op.drop_table("approvals")
    op.drop_table("job_matches")
    op.drop_table("jobs")
