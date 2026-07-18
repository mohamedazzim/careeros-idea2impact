"""Remove stale user/job uniqueness from job matches.

Revision ID: 014_drop_jm_user_job_unique
Revises: 013_job_match_resume_uniqueness
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op


revision: str = "014_drop_jm_user_job_unique"
down_revision: Union[str, None] = "013_job_match_resume_uniqueness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Revision 011 already removes this legacy constraint on a normal upgrade path.
    # Keep the later cleanup safe for fresh databases and partially migrated installs.
    op.execute(
        "ALTER TABLE job_matches "
        "DROP CONSTRAINT IF EXISTS uq_job_match_user_job"
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_job_match_user_job",
        "job_matches",
        ["user_id", "job_id"],
    )
