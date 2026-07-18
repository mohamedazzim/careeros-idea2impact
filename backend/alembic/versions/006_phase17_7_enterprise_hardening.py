"""Phase 17.7 — Enterprise hardening migration.

Revision ID: 006
Revises: 005
Create Date: 2026-05-30

Adds:
- New tables: knowledge_docs, generated_packages, circuit_states, audit_logs, pending_jobs
- deleted_at columns to all 26 existing tables
- created_by/updated_by columns to business entities
- FK constraints that were missing (job_matches.job_id → jobs.id, etc.)
- Unique constraints that were missing
- Account lockout columns on users (failed_login_attempts, locked_until)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New tables ───────────────────────────────────────────────────

    print("STEP 01 - create_table knowledge_docs")
    op.create_table(
        "knowledge_docs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("doc_uid", sa.String(64), unique=True, nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source", sa.String(64), server_default="upload"),
        sa.Column("chunk_count", sa.Integer(), default=0),
        sa.Column("status", sa.String(32), server_default="pending", index=True),
        sa.Column("analysis_results", postgresql.JSON(), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), index=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    print("STEP 02 - create_index ix_knowledge_docs_user_status")
    op.create_index("ix_knowledge_docs_user_status", "knowledge_docs", ["user_id", "status"])

    print("STEP 03 - create_table generated_packages")
    op.create_table(
        "generated_packages",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("package_uid", sa.String(64), unique=True, nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), index=True, nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("resume_tailored", sa.Text(), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("outreach_message", sa.Text(), nullable=True),
        sa.Column("interview_guide", sa.Text(), nullable=True),
        sa.Column("readiness_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default="draft", index=True),
        sa.Column("metadata", postgresql.JSON(), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), index=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    print("STEP 04 - create_index ix_generated_packages_user_status")
    op.create_index("ix_generated_packages_user_status", "generated_packages", ["user_id", "status"])

    print("STEP 05 - create_table circuit_states")
    op.create_table(
        "circuit_states",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("circuit_uid", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False, index=True),
        sa.Column("service", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), server_default="closed"),
        sa.Column("failure_count", sa.Integer(), default=0),
        sa.Column("last_failure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSON(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    print("STEP 06 - create_table audit_logs")
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(128), index=True, nullable=True),
        sa.Column("action", sa.String(128), nullable=False, index=True),
        sa.Column("resource", sa.String(256), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("details", postgresql.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("severity", sa.String(32), server_default="info"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), index=True),
    )
    print("STEP 07 - create_index ix_audit_logs_user_action")
    op.create_index("ix_audit_logs_user_action", "audit_logs", ["user_id", "action"])
    print("STEP 08 - create_index ix_audit_logs_resource")
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource", "created_at"])

    print("STEP 09 - create_table pending_jobs")
    op.create_table(
        "pending_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("job_uid", sa.String(64), unique=True, nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False, index=True),
        sa.Column("status", sa.String(32), server_default="pending", index=True),
        sa.Column("priority", sa.Integer(), default=0),
        sa.Column("payload", postgresql.JSON(), nullable=True),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("max_retries", sa.Integer(), default=3),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), index=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    print("STEP 10 - create_index ix_pending_jobs_status_priority")
    op.create_index("ix_pending_jobs_status_priority", "pending_jobs", ["status", "priority"])

    # ── deleted_at on existing tables ────────────────────────────────

    deleted_at_tables = [
        "resumes", "resume_versions", "resume_chunks",
        "interview_sessions", "interview_questions", "interview_weakness_history",
        "orchestration_sessions", "orchestration_events", "autonomous_actions",
        "notification_history", "opportunity_scores", "governance_decisions",
        "mcp_execution_logs",
        "jobs", "job_matches",
        "approvals", "approval_items", "approval_comments", "approval_notifications",
        "roadmaps", "roadmap_goals", "roadmap_tasks",
        "evaluation_runs", "hallucination_audits", "user_preferences",
    ]
    step = 10
    for table in deleted_at_tables:
        step += 1
        try:
            print(f"STEP {step:02d} - add_column deleted_at on {table}")
            op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        except Exception as e:
            print(f"STEP {step:02d} - FAILED: {e}")

    # ── created_by / updated_by on business entities ─────────────────
    # Only add to existing tables, NOT to the new ones already created above
    business_tables = [
        "resumes", "interview_sessions", "orchestration_sessions",
        "jobs", "approvals", "roadmaps", "evaluation_runs",
    ]
    for table in business_tables:
        step += 1
        try:
            print(f"STEP {step:02d} - add_column created_by on {table}")
            op.add_column(table, sa.Column("created_by", sa.String(128), nullable=True))
        except Exception as e:
            print(f"STEP {step:02d} - FAILED: {e}")
        step += 1
        try:
            print(f"STEP {step:02d} - add_column updated_by on {table}")
            op.add_column(table, sa.Column("updated_by", sa.String(128), nullable=True))
        except Exception as e:
            print(f"STEP {step:02d} - FAILED: {e}")

    # ── Account lockout on users ─────────────────────────────────────
    step += 1
    try:
        print(f"STEP {step:02d} - add_column failed_login_attempts on users")
        op.add_column("users", sa.Column("failed_login_attempts", sa.Integer(), server_default="0"))
    except Exception as e:
        print(f"STEP {step:02d} - FAILED: {e}")
    step += 1
    try:
        print(f"STEP {step:02d} - add_column locked_until on users")
        op.add_column("users", sa.Column("locked_until", sa.DateTime(), nullable=True))
    except Exception as e:
        print(f"STEP {step:02d} - FAILED: {e}")
    step += 1
    try:
        print(f"STEP {step:02d} - add_column deleted_at on users")
        op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    except Exception as e:
        print(f"STEP {step:02d} - FAILED: {e}")

    # ── FK fix: job_matches.job_id → jobs.id ─────────────────────────
    step += 1
    try:
        print(f"STEP {step:02d} - create_foreign_key fk_job_matches_job_id")
        op.create_foreign_key(
            "fk_job_matches_job_id", "job_matches", "jobs",
            ["job_id"], ["id"], ondelete="CASCADE"
        )
    except Exception as e:
        print(f"STEP {step:02d} - FAILED: {e}")
    step += 1
    try:
        print(f"STEP {step:02d} - create_unique_constraint uq_job_match_user_job")
        op.create_unique_constraint("uq_job_match_user_job", "job_matches", ["user_id", "job_id"])
    except Exception as e:
        print(f"STEP {step:02d} - FAILED: {e}")

    # ── FK fix: approval_notifications.related_approval_id → approvals.id ──
    step += 1
    try:
        print(f"STEP {step:02d} - create_foreign_key fk_approval_notif_approval")
        op.create_foreign_key(
            "fk_approval_notif_approval", "approval_notifications", "approvals",
            ["related_approval_id"], ["id"], ondelete="SET NULL"
        )
    except Exception as e:
        print(f"STEP {step:02d} - FAILED: {e}")

    # ── FK fix: hallucination_audits.run_id → evaluation_runs.id ─────
    step += 1
    try:
        print(f"STEP {step:02d} - execute ALTER TABLE hallucination_audits ALTER run_id TYPE INTEGER")
        op.execute("ALTER TABLE hallucination_audits ALTER COLUMN run_id TYPE INTEGER USING run_id::INTEGER")
    except Exception as e:
        print(f"STEP {step:02d} - FAILED: {e}")
    step += 1
    try:
        print(f"STEP {step:02d} - create_foreign_key fk_hallucination_audit_run")
        op.create_foreign_key(
            "fk_hallucination_audit_run", "hallucination_audits", "evaluation_runs",
            ["run_id"], ["id"], ondelete="SET NULL"
        )
    except Exception as e:
        print(f"STEP {step:02d} - FAILED: {e}")

    print("UPGRADE COMPLETE — all steps executed")


def downgrade() -> None:
    # Drop unique constraints (only those created by 006)
    try:
        op.drop_constraint("uq_job_match_user_job", "job_matches", type_="unique")
    except Exception:
        pass

    # Drop FKs (only those created by 006; resume FKs from 001 are left intact)
    try:
        op.drop_constraint("fk_hallucination_audit_run", "hallucination_audits", type_="foreignkey")
    except Exception:
        pass
    try:
        op.drop_constraint("fk_approval_notif_approval", "approval_notifications", type_="foreignkey")
    except Exception:
        pass
    try:
        op.drop_constraint("fk_job_matches_job_id", "job_matches", type_="foreignkey")
    except Exception:
        pass

    # Drop account lockout columns
    try:
        op.drop_column("users", "deleted_at")
    except Exception:
        pass
    try:
        op.drop_column("users", "locked_until")
    except Exception:
        pass
    try:
        op.drop_column("users", "failed_login_attempts")
    except Exception:
        pass

    # Drop created_by/updated_by from existing tables
    business_tables = [
        "resumes", "interview_sessions", "orchestration_sessions",
        "jobs", "approvals", "roadmaps", "evaluation_runs",
    ]
    for table in business_tables:
        try:
            op.drop_column(table, "updated_by")
        except Exception:
            pass
        try:
            op.drop_column(table, "created_by")
        except Exception:
            pass

    # Drop deleted_at from all tables
    deleted_at_tables = [
        "resumes", "resume_versions", "resume_chunks",
        "interview_sessions", "interview_questions", "interview_weakness_history",
        "orchestration_sessions", "orchestration_events", "autonomous_actions",
        "notification_history", "opportunity_scores", "governance_decisions",
        "mcp_execution_logs",
        "jobs", "job_matches",
        "approvals", "approval_items", "approval_comments", "approval_notifications",
        "roadmaps", "roadmap_goals", "roadmap_tasks",
        "evaluation_runs", "hallucination_audits", "user_preferences",
    ]
    for table in deleted_at_tables + ["users"]:
        try:
            op.drop_column(table, "deleted_at")
        except Exception:
            pass

    # Drop new tables
    try:
        op.drop_table("pending_jobs")
    except Exception:
        pass
    try:
        op.drop_table("audit_logs")
    except Exception:
        pass
    try:
        op.drop_table("circuit_states")
    except Exception:
        pass
    try:
        op.drop_table("generated_packages")
    except Exception:
        pass
    try:
        op.drop_table("knowledge_docs")
    except Exception:
        pass
