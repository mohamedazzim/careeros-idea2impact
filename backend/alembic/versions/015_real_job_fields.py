"""Add real-provider job fields and retire search-link seeds.

Revision ID: 015_real_job_fields
Revises: 014_drop_jm_user_job_unique
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015_real_job_fields"
down_revision: Union[str, None] = "014_drop_jm_user_job_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEARCH_SOURCES = (
    "naukri",
    "internshala",
    "foundit",
    "cutshort",
    "wellfound",
    "indeed_india",
    "linkedin_jobs",
)


def upgrade() -> None:
    op.add_column("jobs", sa.Column("source_provider", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("apply_url", sa.String(length=1024), nullable=True))
    op.add_column("jobs", sa.Column("posted_date", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("fetched_at", sa.DateTime(), nullable=True))
    op.create_index("ix_jobs_fetched_at", "jobs", ["fetched_at"])

    op.execute("UPDATE jobs SET source_provider = source WHERE source_provider IS NULL")
    op.execute("UPDATE jobs SET apply_url = source_url WHERE apply_url IS NULL")
    op.execute("UPDATE jobs SET fetched_at = ingested_at WHERE fetched_at IS NULL")

    sources = ", ".join(f"'{source}'" for source in SEARCH_SOURCES)
    op.execute(
        f"""
        UPDATE jobs
        SET status = 'removed_search_link',
            deleted_at = NOW(),
            updated_at = NOW()
        WHERE source IN ({sources})
           OR source_url ILIKE '%/jobs/search%'
           OR source_url ILIKE '%/search/%'
           OR source_url ILIKE '%/srp/results%'
           OR source_url ILIKE '%keywords=%'
           OR source_url ILIKE '%/internships/keywords-%'
           OR source_url ILIKE '%-jobs-in-india%'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_fetched_at", table_name="jobs")
    op.drop_column("jobs", "fetched_at")
    op.drop_column("jobs", "posted_date")
    op.drop_column("jobs", "apply_url")
    op.drop_column("jobs", "source_provider")
