"""add gap_score to job_matches

Revision ID: 010_add_gap_score
Revises: 009_auth_stabilization
Create Date: 2026-06-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('job_matches', sa.Column('gap_score', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('job_matches', 'gap_score')
