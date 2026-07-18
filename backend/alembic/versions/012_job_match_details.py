"""Persist job match explainability details.

Revision ID: 012_job_match_details
Revises: 011_opportunity_provenance
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012_job_match_details"
down_revision: Union[str, None] = "011_opportunity_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_matches", sa.Column("match_details", sa.JSON(), nullable=True))
    op.add_column("job_matches", sa.Column("resume_doc_uid", sa.String(length=64), nullable=True))
    op.add_column("job_matches", sa.Column("resume_name", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("job_matches", "resume_name")
    op.drop_column("job_matches", "resume_doc_uid")
    op.drop_column("job_matches", "match_details")
