"""add package_versions for version history

Revision ID: 008
Revises: 007_rerank_runs
Create Date: 2026-05-30
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "package_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("generated_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("change_reason", sa.String(256), nullable=False, default="regenerated"),
        sa.Column("resume_content", sa.Text(), nullable=True),
        sa.Column("cover_letter_content", sa.Text(), nullable=True),
        sa.Column("outreach_content", sa.Text(), nullable=True),
        sa.Column("interview_guide_content", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_package_versions_package", "package_versions", ["package_id", "version_num"])


def downgrade():
    op.drop_index("ix_package_versions_package")
    op.drop_table("package_versions")
