"""Add a server default for resumes.updated_at.

Revision ID: 034_resume_updated_at_default
Revises: 033_schema_contract_alignment
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "034_resume_updated_at_default"
down_revision = "033_schema_contract_alignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "resumes",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.alter_column(
        "resumes",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=None,
    )
