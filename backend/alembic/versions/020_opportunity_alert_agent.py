"""Add the public Opportunity Alert Agent decision ledger.

Revision ID: 020_opportunity_alert
Revises: 019_rc3_opp_agent
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "020_opportunity_alert"
down_revision = "019_rc3_opp_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opportunity_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.String(length=128), nullable=False),
        sa.Column("job_title", sa.String(length=512), nullable=False),
        sa.Column("company", sa.String(length=256), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("hours_since_posted", sa.Float(), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("called", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("call_sid", sa.String(length=128), nullable=True),
        sa.Column("webhook_status", sa.String(length=32), nullable=True),
        sa.Column("provider_response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_opportunity_alerts_candidate_id", "opportunity_alerts", ["candidate_id"])
    op.create_index("ix_opportunity_alerts_decision", "opportunity_alerts", ["decision"])
    op.create_index("ix_opportunity_alerts_call_sid", "opportunity_alerts", ["call_sid"])
    op.create_index("ix_opportunity_alerts_webhook_status", "opportunity_alerts", ["webhook_status"])
    op.create_index("ix_opportunity_alerts_created_at", "opportunity_alerts", ["created_at"])


def downgrade() -> None:
    op.drop_table("opportunity_alerts")
