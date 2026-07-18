"""027 - Add verified learning resources and skill-gap learning paths.

Revision ID: 027_verified_learning_paths
Revises: 026_tech_role_experience_filter
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa

revision = "027_verified_learning_paths"
down_revision = "026_tech_role_experience_filter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_resources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("skill_slug", sa.String(length=128), nullable=False),
        sa.Column("skill_name", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("channel_name", sa.String(length=256), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("difficulty", sa.String(length=64), nullable=True),
        sa.Column("format", sa.String(length=64), nullable=True),
        sa.Column("is_free", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("language", sa.String(length=32), nullable=False, server_default=sa.text("'en'")),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default=sa.text("0.75")),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default=sa.text("0.75")),
        sa.Column("freshness_score", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("skill_slug", "source_url", name="uq_learning_resources_skill_source"),
    )
    op.create_index("ix_learning_resources_skill_verified", "learning_resources", ["skill_slug", "last_verified_at"])

    op.create_table(
        "user_skill_learning_paths",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("skill_slug", sa.String(length=128), nullable=False),
        sa.Column("skill_name", sa.String(length=128), nullable=False),
        sa.Column("source_job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_match_id", sa.Integer(), sa.ForeignKey("job_matches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("estimated_hours", sa.Float(), nullable=True),
        sa.Column("resource_status", sa.String(length=32), nullable=False, server_default=sa.text("'available'")),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("refreshed_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "skill_slug", name="uq_learning_paths_user_skill"),
    )
    op.create_index("ix_learning_paths_user_priority", "user_skill_learning_paths", ["user_id", "priority"])

    op.create_table(
        "learning_path_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("learning_path_id", sa.Integer(), sa.ForeignKey("user_skill_learning_paths.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("learning_resources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("step_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("practice_project", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_learning_path_items_learning_path", "learning_path_items", ["learning_path_id"])


def downgrade() -> None:
    op.drop_index("ix_learning_path_items_learning_path", table_name="learning_path_items")
    op.drop_table("learning_path_items")
    op.drop_index("ix_learning_paths_user_priority", table_name="user_skill_learning_paths")
    op.drop_table("user_skill_learning_paths")
    op.drop_index("ix_learning_resources_skill_verified", table_name="learning_resources")
    op.drop_table("learning_resources")
