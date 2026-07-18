"""Scope job match uniqueness to the selected resume.

Revision ID: 013_job_match_resume_uniqueness
Revises: 012_job_match_details
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op


revision: str = "013_job_match_resume_uniqueness"
down_revision: Union[str, None] = "012_job_match_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_job_match_user_source_job", "job_matches", type_="unique")
    op.create_unique_constraint(
        "uq_job_match_user_source_resume",
        "job_matches",
        ["user_id", "source_job_id", "resume_doc_uid"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_job_match_user_source_resume", "job_matches", type_="unique")
    op.create_unique_constraint(
        "uq_job_match_user_source_job",
        "job_matches",
        ["user_id", "source_job_id"],
    )
