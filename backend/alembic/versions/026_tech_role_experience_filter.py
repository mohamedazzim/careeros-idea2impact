"""026 — Add tech-role classification and experience filtering to jobs.

Revision ID: 026
Revises: 025_india_market_filter
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa

revision = "026_tech_role_experience_filter"
down_revision = "025_india_market_filter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("is_tech_role", sa.Boolean(), nullable=True, default=None))
    op.add_column("jobs", sa.Column("tech_role_category", sa.String(64), nullable=True))
    op.add_column("jobs", sa.Column("tech_role_confidence", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("role_classification_reason", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("experience_min_years", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("experience_max_years", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("seniority_level", sa.String(32), nullable=True))
    op.add_column("jobs", sa.Column("experience_filter_status", sa.String(32), nullable=True))

    op.create_index("ix_jobs_tech_role", "jobs", ["is_tech_role"], postgresql_where="is_tech_role = true")
    op.create_index("ix_jobs_seniority", "jobs", ["seniority_level"])


def downgrade() -> None:
    op.drop_index("ix_jobs_seniority", table_name="jobs")
    op.drop_index("ix_jobs_tech_role", table_name="jobs")
    op.drop_column("jobs", "experience_filter_status")
    op.drop_column("jobs", "seniority_level")
    op.drop_column("jobs", "experience_max_years")
    op.drop_column("jobs", "experience_min_years")
    op.drop_column("jobs", "role_classification_reason")
    op.drop_column("jobs", "tech_role_confidence")
    op.drop_column("jobs", "tech_role_category")
    op.drop_column("jobs", "is_tech_role")
