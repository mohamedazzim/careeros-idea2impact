"""RC3 opportunity intelligence agent platform.

Revision ID: 019_rc3_opp_agent
Revises: 018_phase2_opp_intel
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "019_rc3_opp_agent"
down_revision = "018_phase2_opp_intel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alert_decision_audits", sa.Column("decision_factors", sa.JSON(), nullable=True))
    op.add_column("alert_decision_audits", sa.Column("decision_confidence", sa.Float(), nullable=True))

    op.create_table(
        "communication_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_uid", sa.String(length=64), nullable=False, unique=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("opportunity_id", sa.String(length=128), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("communication_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("communication_provider", sa.String(length=64), nullable=True),
        sa.Column("communication_result", sa.JSON(), nullable=True),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decision_factors", sa.JSON(), nullable=True),
        sa.Column("decision_confidence", sa.Float(), nullable=True),
        sa.Column("pipedream_request", sa.JSON(), nullable=True),
        sa.Column("pipedream_response", sa.JSON(), nullable=True),
        sa.Column("webhook_status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_communication_requests_correlation_id", "communication_requests", ["correlation_id"])
    op.create_index("ix_communication_requests_user_id", "communication_requests", ["user_id"])
    op.create_index("ix_communication_requests_job_id", "communication_requests", ["job_id"])
    op.create_index("ix_communication_requests_opportunity_id", "communication_requests", ["opportunity_id"])
    op.create_index("ix_communication_requests_channel", "communication_requests", ["channel"])
    op.create_index("ix_communication_requests_communication_status", "communication_requests", ["communication_status"])
    op.create_index("ix_communication_requests_webhook_status", "communication_requests", ["webhook_status"])
    op.create_index("ix_comm_requests_user_status", "communication_requests", ["user_id", "communication_status"])
    op.create_index("ix_comm_requests_job_channel", "communication_requests", ["job_id", "channel"])

    op.create_table(
        "voice_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_uid", sa.String(length=64), nullable=False, unique=True),
        sa.Column("communication_request_id", sa.Integer(), sa.ForeignKey("communication_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("voice_provider", sa.String(length=64), nullable=True),
        sa.Column("voice_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_voice_sessions_communication_request_id", "voice_sessions", ["communication_request_id"])
    op.create_index("ix_voice_sessions_user_id", "voice_sessions", ["user_id"])
    op.create_index("ix_voice_sessions_job_id", "voice_sessions", ["job_id"])
    op.create_index("ix_voice_sessions_status", "voice_sessions", ["status"])

    op.create_table(
        "voice_conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("voice_session_id", sa.Integer(), sa.ForeignKey("voice_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="agent"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("intelligence_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_voice_conversations_voice_session_id", "voice_conversations", ["voice_session_id"])
    op.create_index("ix_voice_conversations_created_at", "voice_conversations", ["created_at"])

    op.create_table(
        "voice_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("voice_session_id", sa.Integer(), sa.ForeignKey("voice_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("provider_status", sa.String(length=64), nullable=True),
        sa.Column("call_sid", sa.String(length=128), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_voice_outcomes_voice_session_id", "voice_outcomes", ["voice_session_id"])
    op.create_index("ix_voice_outcomes_outcome", "voice_outcomes", ["outcome"])
    op.create_index("ix_voice_outcomes_call_sid", "voice_outcomes", ["call_sid"])

    op.create_table(
        "opportunity_conversation_contexts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("context_uid", sa.String(length=64), nullable=False, unique=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_context", sa.JSON(), nullable=False),
        sa.Column("context_sources", sa.JSON(), nullable=True),
        sa.Column("context_confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_opportunity_conversation_contexts_user_id", "opportunity_conversation_contexts", ["user_id"])
    op.create_index("ix_opportunity_conversation_contexts_job_id", "opportunity_conversation_contexts", ["job_id"])

    op.create_table(
        "opportunity_outcome_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_uid", sa.String(length=64), nullable=False, unique=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("communication_request_id", sa.Integer(), sa.ForeignKey("communication_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_opportunity_outcome_events_user_id", "opportunity_outcome_events", ["user_id"])
    op.create_index("ix_opportunity_outcome_events_job_id", "opportunity_outcome_events", ["job_id"])
    op.create_index("ix_opportunity_outcome_events_communication_request_id", "opportunity_outcome_events", ["communication_request_id"])
    op.create_index("ix_opportunity_outcome_events_status", "opportunity_outcome_events", ["status"])
    op.create_index("ix_opportunity_outcome_events_channel", "opportunity_outcome_events", ["channel"])

    op.create_table(
        "opportunity_outcome_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("dimensions", sa.JSON(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_opportunity_outcome_metrics_user_id", "opportunity_outcome_metrics", ["user_id"])
    op.create_index("ix_opportunity_outcome_metrics_metric_name", "opportunity_outcome_metrics", ["metric_name"])

    op.create_table(
        "opportunity_conversion_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("notified_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("applied_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interview_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("offer_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conversion_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_opportunity_conversion_metrics_user_id", "opportunity_conversion_metrics", ["user_id"])
    op.create_index("ix_opportunity_conversion_metrics_channel", "opportunity_conversion_metrics", ["channel"])

    op.create_table(
        "opportunity_lifecycle_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_uid", sa.String(length=64), nullable=False, unique=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("monitored_counts", sa.JSON(), nullable=True),
        sa.Column("triggered_actions", sa.JSON(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_opportunity_lifecycle_runs_user_id", "opportunity_lifecycle_runs", ["user_id"])
    op.create_index("ix_opportunity_lifecycle_runs_status", "opportunity_lifecycle_runs", ["status"])


def downgrade() -> None:
    op.drop_table("opportunity_lifecycle_runs")
    op.drop_table("opportunity_conversion_metrics")
    op.drop_table("opportunity_outcome_metrics")
    op.drop_table("opportunity_outcome_events")
    op.drop_table("opportunity_conversation_contexts")
    op.drop_table("voice_outcomes")
    op.drop_table("voice_conversations")
    op.drop_table("voice_sessions")
    op.drop_table("communication_requests")
    op.drop_column("alert_decision_audits", "decision_confidence")
    op.drop_column("alert_decision_audits", "decision_factors")
