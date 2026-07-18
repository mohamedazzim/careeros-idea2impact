"""Opportunity provenance repair.

Revision ID: 011_opportunity_provenance
Revises: 010
Create Date: 2026-06-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011_opportunity_provenance"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("source_job_id", sa.String(length=128), nullable=True))
    op.create_index("ix_jobs_source_job_id", "jobs", ["source_job_id"])

    op.add_column("job_matches", sa.Column("source_job_id", sa.String(length=128), nullable=True))
    op.add_column("job_matches", sa.Column("source_provider", sa.String(length=64), nullable=True))
    op.add_column("job_matches", sa.Column("source_url", sa.String(length=1024), nullable=True))
    op.add_column("job_matches", sa.Column("ingested_at", sa.DateTime(), nullable=True))
    op.create_index("ix_job_matches_source_job_id", "job_matches", ["source_job_id"])

    op.drop_constraint("uq_job_match_user_job", "job_matches", type_="unique")
    op.create_unique_constraint("uq_job_match_user_source_job", "job_matches", ["user_id", "source_job_id"])


def downgrade() -> None:
    op.drop_constraint("uq_job_match_user_source_job", "job_matches", type_="unique")
    op.create_unique_constraint("uq_job_match_user_job", "job_matches", ["user_id", "job_id"])

    op.drop_index("ix_job_matches_source_job_id", table_name="job_matches")
    op.drop_column("job_matches", "ingested_at")
    op.drop_column("job_matches", "source_url")
    op.drop_column("job_matches", "source_provider")
    op.drop_column("job_matches", "source_job_id")

    op.drop_index("ix_jobs_source_job_id", table_name="jobs")
    op.drop_column("jobs", "source_job_id")
