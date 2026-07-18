"""029 - Add learning outcome tracking tables.

Revision ID: 029_learning_outcome_tracking
Revises: 028_career_events_audit_foundation, 028_resource_provenance_ledger
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa

revision = "029_learning_outcome_tracking"
down_revision = ("028_career_events_audit_foundation", "028_resource_provenance_ledger")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_uid", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("learning_resources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provenance_uid", sa.String(length=64), nullable=True),
        sa.Column("path_id", sa.Integer(), sa.ForeignKey("user_skill_learning_paths.id", ondelete="SET NULL"), nullable=True),
        sa.Column("path_item_id", sa.Integer(), sa.ForeignKey("learning_path_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("skill_slug", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'opened'")),
        sa.Column("source_ui", sa.String(length=128), nullable=True),
        sa.Column("external_resource_url", sa.String(length=1024), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("completion_percentage", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("session_uid", name="uq_learning_sessions_session_uid"),
    )
    op.create_index("ix_learning_sessions_session_uid", "learning_sessions", ["session_uid"])
    op.create_index("ix_learning_sessions_user_id", "learning_sessions", ["user_id"])
    op.create_index("ix_learning_sessions_resource_id", "learning_sessions", ["resource_id"])
    op.create_index("ix_learning_sessions_provenance_uid", "learning_sessions", ["provenance_uid"])
    op.create_index("ix_learning_sessions_path_id", "learning_sessions", ["path_id"])
    op.create_index("ix_learning_sessions_path_item_id", "learning_sessions", ["path_item_id"])
    op.create_index("ix_learning_sessions_skill_slug", "learning_sessions", ["skill_slug"])
    op.create_index("ix_learning_sessions_job_id", "learning_sessions", ["job_id"])
    op.create_index("ix_learning_sessions_started_at", "learning_sessions", ["started_at"])
    op.create_index("ix_learning_sessions_last_activity_at", "learning_sessions", ["last_activity_at"])
    op.create_index("ix_learning_sessions_ended_at", "learning_sessions", ["ended_at"])
    op.create_index("ix_learning_sessions_user_resource_status", "learning_sessions", ["user_id", "resource_id", "status"])

    op.create_table(
        "resource_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("feedback_uid", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("learning_resources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provenance_uid", sa.String(length=64), nullable=True),
        sa.Column("session_uid", sa.String(length=64), sa.ForeignKey("learning_sessions.session_uid", ondelete="SET NULL"), nullable=True),
        sa.Column("skill_slug", sa.String(length=128), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("difficulty", sa.String(length=64), nullable=True),
        sa.Column("would_recommend", sa.Boolean(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("helpfulness_score", sa.Float(), nullable=True),
        sa.Column("outcome_tag", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("feedback_uid", name="uq_resource_feedback_feedback_uid"),
    )
    op.create_index("ix_resource_feedback_feedback_uid", "resource_feedback", ["feedback_uid"])
    op.create_index("ix_resource_feedback_user_id", "resource_feedback", ["user_id"])
    op.create_index("ix_resource_feedback_resource_id", "resource_feedback", ["resource_id"])
    op.create_index("ix_resource_feedback_provenance_uid", "resource_feedback", ["provenance_uid"])
    op.create_index("ix_resource_feedback_session_uid", "resource_feedback", ["session_uid"])
    op.create_index("ix_resource_feedback_skill_slug", "resource_feedback", ["skill_slug"])
    op.create_index("ix_resource_feedback_outcome_tag", "resource_feedback", ["outcome_tag"])
    op.create_index("ix_resource_feedback_user_resource", "resource_feedback", ["user_id", "resource_id"])

    op.create_table(
        "resource_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("learning_resources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provenance_uid", sa.String(length=64), nullable=True),
        sa.Column("skill_slug", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("completion_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("feedback_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("average_rating", sa.Float(), nullable=True),
        sa.Column("completion_rate", sa.Float(), nullable=True),
        sa.Column("drop_off_rate", sa.Float(), nullable=True),
        sa.Column("recommendation_rate", sa.Float(), nullable=True),
        sa.Column("average_completion_percentage", sa.Float(), nullable=True),
        sa.Column("average_duration_seconds", sa.Float(), nullable=True),
        sa.Column("last_calculated_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'insufficient_data'")),
        sa.Column("calculation_metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("resource_id", name="uq_resource_outcomes_resource_id"),
    )
    op.create_index("ix_resource_outcomes_resource_id", "resource_outcomes", ["resource_id"])
    op.create_index("ix_resource_outcomes_provenance_uid", "resource_outcomes", ["provenance_uid"])
    op.create_index("ix_resource_outcomes_skill_slug", "resource_outcomes", ["skill_slug"])
    op.create_index("ix_resource_outcomes_source_type", "resource_outcomes", ["source_type"])
    op.create_index("ix_resource_outcomes_provider", "resource_outcomes", ["provider"])
    op.create_index("ix_resource_outcomes_status", "resource_outcomes", ["status"])
    op.create_index("ix_resource_outcomes_last_calculated_at", "resource_outcomes", ["last_calculated_at"])

    op.create_table(
        "learning_activity_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("activity_uid", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("learning_resources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provenance_uid", sa.String(length=64), nullable=True),
        sa.Column("session_uid", sa.String(length=64), sa.ForeignKey("learning_sessions.session_uid", ondelete="SET NULL"), nullable=True),
        sa.Column("path_id", sa.Integer(), sa.ForeignKey("user_skill_learning_paths.id", ondelete="SET NULL"), nullable=True),
        sa.Column("path_item_id", sa.Integer(), sa.ForeignKey("learning_path_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("skill_slug", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("event_time", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("activity_uid", name="uq_learning_activity_events_activity_uid"),
    )
    op.create_index("ix_learning_activity_events_activity_uid", "learning_activity_events", ["activity_uid"])
    op.create_index("ix_learning_activity_events_user_id", "learning_activity_events", ["user_id"])
    op.create_index("ix_learning_activity_events_event_type", "learning_activity_events", ["event_type"])
    op.create_index("ix_learning_activity_events_resource_id", "learning_activity_events", ["resource_id"])
    op.create_index("ix_learning_activity_events_provenance_uid", "learning_activity_events", ["provenance_uid"])
    op.create_index("ix_learning_activity_events_session_uid", "learning_activity_events", ["session_uid"])
    op.create_index("ix_learning_activity_events_path_id", "learning_activity_events", ["path_id"])
    op.create_index("ix_learning_activity_events_path_item_id", "learning_activity_events", ["path_item_id"])
    op.create_index("ix_learning_activity_events_skill_slug", "learning_activity_events", ["skill_slug"])
    op.create_index("ix_learning_activity_events_job_id", "learning_activity_events", ["job_id"])
    op.create_index("ix_learning_activity_events_event_time", "learning_activity_events", ["event_time"])


def downgrade() -> None:
    op.drop_index("ix_learning_activity_events_event_time", table_name="learning_activity_events")
    op.drop_index("ix_learning_activity_events_job_id", table_name="learning_activity_events")
    op.drop_index("ix_learning_activity_events_skill_slug", table_name="learning_activity_events")
    op.drop_index("ix_learning_activity_events_path_item_id", table_name="learning_activity_events")
    op.drop_index("ix_learning_activity_events_path_id", table_name="learning_activity_events")
    op.drop_index("ix_learning_activity_events_session_uid", table_name="learning_activity_events")
    op.drop_index("ix_learning_activity_events_provenance_uid", table_name="learning_activity_events")
    op.drop_index("ix_learning_activity_events_resource_id", table_name="learning_activity_events")
    op.drop_index("ix_learning_activity_events_event_type", table_name="learning_activity_events")
    op.drop_index("ix_learning_activity_events_user_id", table_name="learning_activity_events")
    op.drop_index("ix_learning_activity_events_activity_uid", table_name="learning_activity_events")
    op.drop_table("learning_activity_events")

    op.drop_index("ix_resource_outcomes_last_calculated_at", table_name="resource_outcomes")
    op.drop_index("ix_resource_outcomes_status", table_name="resource_outcomes")
    op.drop_index("ix_resource_outcomes_provider", table_name="resource_outcomes")
    op.drop_index("ix_resource_outcomes_source_type", table_name="resource_outcomes")
    op.drop_index("ix_resource_outcomes_skill_slug", table_name="resource_outcomes")
    op.drop_index("ix_resource_outcomes_provenance_uid", table_name="resource_outcomes")
    op.drop_index("ix_resource_outcomes_resource_id", table_name="resource_outcomes")
    op.drop_table("resource_outcomes")

    op.drop_index("ix_resource_feedback_user_resource", table_name="resource_feedback")
    op.drop_index("ix_resource_feedback_outcome_tag", table_name="resource_feedback")
    op.drop_index("ix_resource_feedback_skill_slug", table_name="resource_feedback")
    op.drop_index("ix_resource_feedback_session_uid", table_name="resource_feedback")
    op.drop_index("ix_resource_feedback_provenance_uid", table_name="resource_feedback")
    op.drop_index("ix_resource_feedback_resource_id", table_name="resource_feedback")
    op.drop_index("ix_resource_feedback_user_id", table_name="resource_feedback")
    op.drop_index("ix_resource_feedback_feedback_uid", table_name="resource_feedback")
    op.drop_table("resource_feedback")

    op.drop_index("ix_learning_sessions_user_resource_status", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_ended_at", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_last_activity_at", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_started_at", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_job_id", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_skill_slug", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_path_item_id", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_path_id", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_provenance_uid", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_resource_id", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_user_id", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_session_uid", table_name="learning_sessions")
    op.drop_table("learning_sessions")
