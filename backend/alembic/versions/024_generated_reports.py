"""generated reports

Revision ID: 024_generated_reports
Revises: 023_phase6_career_intelligence_coach
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "024_generated_reports"
down_revision = "023_phase6_coach_intel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generated_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_uid", sa.String(length=64), nullable=False, unique=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("report_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_generated_reports_user_id", "generated_reports", ["user_id"])
    op.create_index("ix_generated_reports_report_type", "generated_reports", ["report_type"])
    op.create_index("ix_generated_reports_format", "generated_reports", ["format"])
    op.create_index("ix_generated_reports_status", "generated_reports", ["status"])
    op.create_index("ix_generated_reports_created_at", "generated_reports", ["created_at"])
    op.create_index("ix_generated_reports_user_type", "generated_reports", ["user_id", "report_type"])


def downgrade() -> None:
    op.drop_index("ix_generated_reports_user_type", table_name="generated_reports")
    op.drop_index("ix_generated_reports_created_at", table_name="generated_reports")
    op.drop_index("ix_generated_reports_status", table_name="generated_reports")
    op.drop_index("ix_generated_reports_format", table_name="generated_reports")
    op.drop_index("ix_generated_reports_report_type", table_name="generated_reports")
    op.drop_index("ix_generated_reports_user_id", table_name="generated_reports")
    op.drop_table("generated_reports")
