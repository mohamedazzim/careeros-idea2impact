"""Phase 2 outcome intelligence and candidate memory.

Revision ID: 021_outcome_memory
Revises: 020_opportunity_alert
"""

from alembic import op
import sqlalchemy as sa

revision = "021_outcome_memory"
down_revision = "020_opportunity_alert"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("conversation_sessions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("candidate_id", sa.String(128), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL")), sa.Column("conversation_id", sa.String(128), unique=True),
        sa.Column("call_sid", sa.String(128)), sa.Column("agent_id", sa.String(128)), sa.Column("job_title", sa.String(512), nullable=False),
        sa.Column("company", sa.String(256), nullable=False), sa.Column("started_at", sa.DateTime()), sa.Column("ended_at", sa.DateTime()),
        sa.Column("duration_seconds", sa.Integer()), sa.Column("status", sa.String(32), nullable=False, server_default="INITIATED"),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    for col in ("candidate_id", "job_id", "conversation_id", "call_sid", "status", "created_at"):
        op.create_index(f"ix_conversation_sessions_{col}", "conversation_sessions", [col])
    op.create_table("conversation_transcripts",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("conversation_id", sa.String(128), nullable=False, unique=True),
        sa.Column("candidate_id", sa.String(128), nullable=False), sa.Column("raw_transcript", sa.Text(), nullable=False),
        sa.Column("speaker_turns", sa.JSON()), sa.Column("provider_metadata", sa.JSON()), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_conversation_transcripts_conversation_id", "conversation_transcripts", ["conversation_id"])
    op.create_index("ix_conversation_transcripts_candidate_id", "conversation_transcripts", ["candidate_id"])
    op.create_table("candidate_concerns",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("candidate_id", sa.String(128), nullable=False),
        sa.Column("conversation_id", sa.String(128), nullable=False), sa.Column("concern_type", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False), sa.Column("evidence", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("conversation_id", "concern_type", name="uq_conversation_concern_type"))
    for col in ("candidate_id", "conversation_id", "concern_type"):
        op.create_index(f"ix_candidate_concerns_{col}", "candidate_concerns", [col])
    op.create_table("candidate_preference_memory",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("candidate_id", sa.String(128), nullable=False),
        sa.Column("preference_type", sa.String(64), nullable=False), sa.Column("preference_value", sa.String(512), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"), sa.Column("evidence", sa.Text()),
        sa.Column("source_conversation_id", sa.String(128)), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("candidate_id", "preference_type", "preference_value", name="uq_candidate_preference"))
    op.create_index("ix_candidate_preference_memory_candidate_id", "candidate_preference_memory", ["candidate_id"])
    op.create_index("ix_candidate_preference_memory_preference_type", "candidate_preference_memory", ["preference_type"])
    op.create_table("opportunity_call_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("candidate_id", sa.String(128), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL")), sa.Column("conversation_id", sa.String(128), nullable=False, unique=True),
        sa.Column("call_sid", sa.String(128)), sa.Column("outcome", sa.String(32), nullable=False), sa.Column("interest_level", sa.String(32), nullable=False),
        sa.Column("primary_concern", sa.String(64)), sa.Column("followup_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("summary", sa.Text(), nullable=False), sa.Column("confidence", sa.Float(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    for col in ("candidate_id", "job_id", "conversation_id", "call_sid", "outcome", "created_at"):
        op.create_index(f"ix_opportunity_call_outcomes_{col}", "opportunity_call_outcomes", [col])


def downgrade() -> None:
    for table in ("opportunity_call_outcomes", "candidate_preference_memory", "candidate_concerns", "conversation_transcripts", "conversation_sessions"):
        op.drop_table(table)
