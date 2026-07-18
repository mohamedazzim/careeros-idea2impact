"""Add Phase 2 autonomous opportunity intelligence tables.

Revision ID: 018_phase2_opp_intel
Revises: 017_opp_lifecycle_cleanup
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "018_phase2_opp_intel"
down_revision = "017_opp_lifecycle_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opportunity_intelligence_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_doc_uid", sa.String(length=64), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("skill_gap_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("learning_effort_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("application_urgency", sa.Float(), nullable=False, server_default="0"),
        sa.Column("competition_risk", sa.Float(), nullable=False, server_default="0"),
        sa.Column("domain_alignment", sa.Float(), nullable=False, server_default="0"),
        sa.Column("career_growth_potential", sa.Float(), nullable=False, server_default="0"),
        sa.Column("salary_potential", sa.Float(), nullable=False, server_default="0"),
        sa.Column("remote_compatibility", sa.Float(), nullable=False, server_default="0"),
        sa.Column("opportunity_rank_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recommended_priority", sa.String(length=32), nullable=False, server_default="DASHBOARD_ONLY"),
        sa.Column("report", sa.JSON(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_opp_intel_user_job_resume",
        "opportunity_intelligence_reports",
        ["user_id", "job_id", "resume_doc_uid"],
    )
    op.create_index("ix_opp_intel_user_rank", "opportunity_intelligence_reports", ["user_id", "opportunity_rank_score"])
    op.create_index("ix_opportunity_intelligence_reports_user_id", "opportunity_intelligence_reports", ["user_id"])
    op.create_index("ix_opportunity_intelligence_reports_job_id", "opportunity_intelligence_reports", ["job_id"])
    op.create_index("ix_opportunity_intelligence_reports_resume_doc_uid", "opportunity_intelligence_reports", ["resume_doc_uid"])
    op.create_index("ix_opportunity_intelligence_reports_recommended_priority", "opportunity_intelligence_reports", ["recommended_priority"])

    op.create_table(
        "salary_intelligence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("salary_min", sa.Float(), nullable=True),
        sa.Column("salary_max", sa.Float(), nullable=True),
        sa.Column("salary_currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("salary_period", sa.String(length=16), nullable=False, server_default="year"),
        sa.Column("monthly_min", sa.Float(), nullable=True),
        sa.Column("monthly_max", sa.Float(), nullable=True),
        sa.Column("yearly_min", sa.Float(), nullable=True),
        sa.Column("yearly_max", sa.Float(), nullable=True),
        sa.Column("salary_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="description_extraction"),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_salary_intelligence_job_id", "salary_intelligence", ["job_id"])

    op.create_table(
        "interview_preparation_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_doc_uid", sa.String(length=64), nullable=True),
        sa.Column("technical_questions", sa.JSON(), nullable=True),
        sa.Column("hr_questions", sa.JSON(), nullable=True),
        sa.Column("system_design_questions", sa.JSON(), nullable=True),
        sa.Column("coding_topics", sa.JSON(), nullable=True),
        sa.Column("preparation_plan", sa.JSON(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_interview_prep_user_job_resume",
        "interview_preparation_plans",
        ["user_id", "job_id", "resume_doc_uid"],
    )
    op.create_index("ix_interview_preparation_plans_user_id", "interview_preparation_plans", ["user_id"])
    op.create_index("ix_interview_preparation_plans_job_id", "interview_preparation_plans", ["job_id"])

    op.create_table(
        "application_timeline_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False, server_default="STATUS_CHANGE"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_application_timeline_events_user_id", "application_timeline_events", ["user_id"])
    op.create_index("ix_application_timeline_events_job_id", "application_timeline_events", ["job_id"])
    op.create_index("ix_application_timeline_events_status", "application_timeline_events", ["status"])
    op.create_index("ix_application_timeline_events_created_at", "application_timeline_events", ["created_at"])
    op.create_index("ix_application_timeline_user_job", "application_timeline_events", ["user_id", "job_id"])

    op.create_table(
        "career_memory",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_table", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_career_memory_user_id", "career_memory", ["user_id"])
    op.create_index("ix_career_memory_event_type", "career_memory", ["event_type"])
    op.create_index("ix_career_memory_job_id", "career_memory", ["job_id"])
    op.create_index("ix_career_memory_created_at", "career_memory", ["created_at"])
    op.create_index("ix_career_memory_user_time", "career_memory", ["user_id", "created_at"])

    op.create_table(
        "alert_decision_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="NONE"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_alert_decision_audits_user_id", "alert_decision_audits", ["user_id"])
    op.create_index("ix_alert_decision_audits_job_id", "alert_decision_audits", ["job_id"])
    op.create_index("ix_alert_decision_audits_decision", "alert_decision_audits", ["decision"])
    op.create_index("ix_alert_decision_audits_created_at", "alert_decision_audits", ["created_at"])


def downgrade() -> None:
    op.drop_table("alert_decision_audits")
    op.drop_table("career_memory")
    op.drop_table("application_timeline_events")
    op.drop_table("interview_preparation_plans")
    op.drop_table("salary_intelligence")
    op.drop_table("opportunity_intelligence_reports")
