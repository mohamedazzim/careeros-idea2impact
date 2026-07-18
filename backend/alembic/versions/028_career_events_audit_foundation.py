"""028 - Add unified career event audit foundation.

Revision ID: 028_career_events_audit_foundation
Revises: 027_verified_learning_paths
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa

revision = "028_career_events_audit_foundation"
down_revision = "027_verified_learning_paths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_uid", sa.String(length=64), nullable=False, unique=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("source_service", sa.String(length=128), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("event_time", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'success'")),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_career_events_user_time", "career_events", ["user_id", "event_time"])
    op.create_index("ix_career_events_type_time", "career_events", ["event_type", "event_time"])
    op.create_index("ix_career_events_entity", "career_events", ["entity_type", "entity_id"])
    op.create_index("ix_career_events_source_time", "career_events", ["source_service", "event_time"])
    op.create_index("ix_career_events_trace", "career_events", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_career_events_trace", table_name="career_events")
    op.drop_index("ix_career_events_source_time", table_name="career_events")
    op.drop_index("ix_career_events_entity", table_name="career_events")
    op.drop_index("ix_career_events_type_time", table_name="career_events")
    op.drop_index("ix_career_events_user_time", table_name="career_events")
    op.drop_table("career_events")
