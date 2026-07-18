"""
Interview schema migration — Phase 4D hardening.

Creates the interview persistence infrastructure:
- interview_sessions: Active and completed interview sessions
- interview_questions: Per-question records with evaluation data
- interview_weakness_history: Longitudinal weakness tracking

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'interview_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_uid', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=256), nullable=True),
        sa.Column('interview_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='active', nullable=False),
        sa.Column('difficulty_level', sa.String(length=16), server_default='intermediate', nullable=False),
        sa.Column('current_question_index', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_score', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('adaptation_history', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('confidence_progression', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_interview_sessions_id', 'interview_sessions', ['id'])
    op.create_index('ix_interview_sessions_session_uid', 'interview_sessions', ['session_uid'], unique=True)
    op.create_index('ix_interview_sessions_user_id', 'interview_sessions', ['user_id'])
    op.create_index('ix_interview_sessions_status', 'interview_sessions', ['status'])
    op.create_index('ix_interview_sessions_type', 'interview_sessions', ['interview_type'])

    op.create_table(
        'interview_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('question_index', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('answer_text', sa.Text(), server_default='', nullable=False),
        sa.Column('difficulty_level', sa.String(length=16), server_default='intermediate', nullable=False),
        sa.Column('score', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('confidence', sa.Float(), server_default='0.5', nullable=False),
        sa.Column('rubric_scores', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('contradictions_detected', sa.Integer(), server_default='0', nullable=False),
        sa.Column('strengths', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('weaknesses', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('improvement_suggestions', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('critique', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('governance_flags', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('trace', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_interview_questions_id', 'interview_questions', ['id'])
    op.create_index('ix_interview_questions_session_id', 'interview_questions', ['session_id'])
    op.create_index('ix_interview_questions_session_qidx', 'interview_questions', ['session_id', 'question_index'])

    op.create_table(
        'interview_weakness_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=256), nullable=True),
        sa.Column('weakness_type', sa.String(length=128), nullable=False),
        sa.Column('session_uid', sa.String(length=64), nullable=False),
        sa.Column('occurrences', sa.Integer(), server_default='0', nullable=False),
        sa.Column('severity', sa.String(length=16), server_default='low', nullable=False),
        sa.Column('pattern_classification', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_interview_weakness_history_id', 'interview_weakness_history', ['id'])
    op.create_index('ix_interview_weakness_history_user_id', 'interview_weakness_history', ['user_id'])
    op.create_index('ix_interview_weakness_history_type', 'interview_weakness_history', ['weakness_type'])


def downgrade() -> None:
    op.drop_index('ix_interview_weakness_history_type', table_name='interview_weakness_history')
    op.drop_index('ix_interview_weakness_history_user_id', table_name='interview_weakness_history')
    op.drop_index('ix_interview_weakness_history_id', table_name='interview_weakness_history')
    op.drop_table('interview_weakness_history')

    op.drop_index('ix_interview_questions_session_qidx', table_name='interview_questions')
    op.drop_index('ix_interview_questions_session_id', table_name='interview_questions')
    op.drop_index('ix_interview_questions_id', table_name='interview_questions')
    op.drop_table('interview_questions')

    op.drop_index('ix_interview_sessions_type', table_name='interview_sessions')
    op.drop_index('ix_interview_sessions_status', table_name='interview_sessions')
    op.drop_index('ix_interview_sessions_user_id', table_name='interview_sessions')
    op.drop_index('ix_interview_sessions_session_uid', table_name='interview_sessions')
    op.drop_index('ix_interview_sessions_id', table_name='interview_sessions')
    op.drop_table('interview_sessions')
