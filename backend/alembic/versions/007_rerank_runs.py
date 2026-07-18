"""add rerank_runs for enterprise analytics

Revision ID: 007
Revises: 006_phase17_7_enterprise_hardening
Create Date: 2026-05-30
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "rerank_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=True, index=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("chunks_submitted", sa.Integer(), nullable=False, default=0),
        sa.Column("chunks_returned", sa.Integer(), nullable=False, default=0),
        sa.Column("primary_provider", sa.String(64), nullable=False, default="nvidia"),
        sa.Column("primary_success", sa.Boolean(), nullable=False, default=False),
        sa.Column("primary_latency_ms", sa.Float(), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, default=False),
        sa.Column("fallback_strategy", sa.String(32), nullable=True),
        sa.Column("fallback_reason", sa.String(256), nullable=True),
        sa.Column("circuit_breaker_open", sa.Boolean(), nullable=False, default=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
        sa.Column("confidence_avg", sa.Float(), nullable=True),
        sa.Column("score_distribution", sa.JSON(), nullable=True),
        sa.Column("rank_correlation", sa.Float(), nullable=True),
        sa.Column("rank_inversion_rate", sa.Float(), nullable=True),
        sa.Column("boost_skills_applied", sa.Boolean(), nullable=False, default=False),
        sa.Column("boost_sections_applied", sa.Boolean(), nullable=False, default=False),
        sa.Column("boost_chronology_applied", sa.Boolean(), nullable=False, default=False),
        sa.Column("top_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("top_chunk_scores", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_rerank_created", "rerank_runs", ["created_at"])
    op.create_index("idx_rerank_user_created", "rerank_runs", ["user_id", "created_at"])


def downgrade():
    op.drop_index("idx_rerank_user_created")
    op.drop_index("idx_rerank_created")
    op.drop_table("rerank_runs")
