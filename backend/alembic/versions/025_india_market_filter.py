"""Add India market classification fields to jobs table.

Revision ID: 025
Revises: 024
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "025_india_market_filter"
down_revision = "024_generated_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("location_country", sa.String(2), nullable=True))
    op.add_column("jobs", sa.Column("location_region", sa.String(100), nullable=True))
    op.add_column("jobs", sa.Column("location_city", sa.String(100), nullable=True))
    op.add_column("jobs", sa.Column("is_remote", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("jobs", sa.Column("remote_region", sa.String(50), nullable=True))
    op.add_column("jobs", sa.Column("is_india_eligible", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("jobs", sa.Column("exclusion_reason", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("eligibility_checked_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("ingestion_run_id", sa.String(64), nullable=True))

    op.create_index(
        "ix_jobs_india_eligible",
        "jobs",
        ["is_india_eligible"],
        postgresql_where=sa.text("is_india_eligible = true"),
    )
    op.create_index(
        "ix_jobs_provider_active",
        "jobs",
        ["source", "status"],
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_provider_active", table_name="jobs")
    op.drop_index("ix_jobs_india_eligible", table_name="jobs")
    op.drop_column("jobs", "ingestion_run_id")
    op.drop_column("jobs", "eligibility_checked_at")
    op.drop_column("jobs", "exclusion_reason")
    op.drop_column("jobs", "is_india_eligible")
    op.drop_column("jobs", "remote_region")
    op.drop_column("jobs", "is_remote")
    op.drop_column("jobs", "location_city")
    op.drop_column("jobs", "location_region")
    op.drop_column("jobs", "location_country")
