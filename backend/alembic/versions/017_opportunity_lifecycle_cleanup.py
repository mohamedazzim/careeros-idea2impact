"""Normalize opportunity lifecycle states for RC2.

Revision ID: 017_opp_lifecycle_cleanup
Revises: 016_theirstack_opp_intel
Create Date: 2026-06-04
"""

from alembic import op


revision = "017_opp_lifecycle_cleanup"
down_revision = "016_theirstack_opp_intel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE jobs
        SET lifecycle_state = 'EXPIRED',
            status = 'expired',
            deleted_at = COALESCE(deleted_at, NOW()),
            updated_at = NOW()
        WHERE deleted_at IS NOT NULL
           OR status = 'expired'
           OR freshness_bucket = 'stale'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE jobs
        SET lifecycle_state = 'NEW'
        WHERE lifecycle_state = 'EXPIRED'
          AND status = 'expired'
        """
    )
