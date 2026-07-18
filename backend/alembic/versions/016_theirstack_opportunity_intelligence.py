"""Add TheirStack opportunity intelligence fields.

Revision ID: 016_theirstack_opp_intel
Revises: 015_real_job_fields
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "016_theirstack_opp_intel"
down_revision: Union[str, None] = "015_real_job_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("original_provider_metadata", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("freshness_score", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("freshness_bucket", sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("provider_quality_score", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("salary_quality_score", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("apply_url_valid", sa.Boolean(), nullable=True))
    op.add_column("jobs", sa.Column("opportunity_priority_score", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("lifecycle_state", sa.String(length=32), nullable=False, server_default="NEW"))
    op.create_index("ix_jobs_freshness_bucket", "jobs", ["freshness_bucket"])
    op.create_index("ix_jobs_lifecycle_state", "jobs", ["lifecycle_state"])

    op.execute(
        """
        UPDATE jobs
        SET provider_quality_score = CASE
                WHEN source IN ('theirstack', 'greenhouse', 'lever', 'ashby') THEN 95
                WHEN source = 'remoteok' THEN 85
                WHEN source = 'arbeitnow' THEN 80
                ELSE 50
            END,
            salary_quality_score = CASE
                WHEN salary_range IS NOT NULL AND salary_range <> '' THEN 90
                ELSE 30
            END,
            apply_url_valid = CASE
                WHEN apply_url IS NOT NULL AND apply_url <> '' THEN TRUE
                ELSE FALSE
            END,
            freshness_score = CASE
                WHEN posted_date IS NULL THEN 50
                WHEN posted_date >= NOW() - INTERVAL '1 day' THEN 100
                WHEN posted_date >= NOW() - INTERVAL '3 days' THEN 85
                WHEN posted_date >= NOW() - INTERVAL '7 days' THEN 70
                WHEN posted_date >= NOW() - INTERVAL '30 days' THEN 40
                ELSE 0
            END,
            freshness_bucket = CASE
                WHEN posted_date IS NULL THEN 'unknown'
                WHEN posted_date >= NOW() - INTERVAL '1 day' THEN 'fresh'
                WHEN posted_date >= NOW() - INTERVAL '3 days' THEN 'recent'
                WHEN posted_date >= NOW() - INTERVAL '7 days' THEN 'active'
                WHEN posted_date >= NOW() - INTERVAL '30 days' THEN 'aging'
                ELSE 'stale'
            END
        """
    )

    op.execute(
        """
        UPDATE jobs
        SET status = 'expired',
            deleted_at = COALESCE(deleted_at, NOW()),
            updated_at = NOW()
        WHERE freshness_bucket = 'stale'
          AND status = 'active'
        """
    )

    op.create_table(
        "opportunity_notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("viewed_at", sa.DateTime(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("send_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "job_id", "channel", name="uq_opportunity_notifications_user_job_channel"),
    )
    op.create_index("ix_opportunity_notifications_user_id", "opportunity_notifications", ["user_id"])
    op.create_index("ix_opportunity_notifications_job_id", "opportunity_notifications", ["job_id"])
    op.create_index("ix_opportunity_notifications_channel", "opportunity_notifications", ["channel"])
    op.create_index("ix_opportunity_notifications_status", "opportunity_notifications", ["status"])
    op.create_index("ix_opportunity_notifications_user_job", "opportunity_notifications", ["user_id", "job_id"])


def downgrade() -> None:
    op.drop_index("ix_opportunity_notifications_user_job", table_name="opportunity_notifications")
    op.drop_index("ix_opportunity_notifications_status", table_name="opportunity_notifications")
    op.drop_index("ix_opportunity_notifications_channel", table_name="opportunity_notifications")
    op.drop_index("ix_opportunity_notifications_job_id", table_name="opportunity_notifications")
    op.drop_index("ix_opportunity_notifications_user_id", table_name="opportunity_notifications")
    op.drop_table("opportunity_notifications")
    op.drop_index("ix_jobs_lifecycle_state", table_name="jobs")
    op.drop_index("ix_jobs_freshness_bucket", table_name="jobs")
    op.drop_column("jobs", "lifecycle_state")
    op.drop_column("jobs", "opportunity_priority_score")
    op.drop_column("jobs", "apply_url_valid")
    op.drop_column("jobs", "salary_quality_score")
    op.drop_column("jobs", "provider_quality_score")
    op.drop_column("jobs", "freshness_bucket")
    op.drop_column("jobs", "freshness_score")
    op.drop_column("jobs", "original_provider_metadata")

