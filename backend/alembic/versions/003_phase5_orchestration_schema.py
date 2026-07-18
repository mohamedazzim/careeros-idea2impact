"""
Phase 5 orchestration schema migration.

Creates the Phase 5 persistence infrastructure:
- orchestration_sessions: Orchestration run lifecycle tracking
- orchestration_events: Event history per session
- autonomous_actions: Autonomously-triggered actions
- notification_history: Voice/email/SMS notification log
- opportunity_scores: Multi-dimensional opportunity fit scores
- governance_decisions: Governance enforcement log
- mcp_execution_logs: MCP tool invocation audit

Revision ID: 003
Revises: 002
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── orchestration_sessions ──────────────────────────────────
    op.create_table(
        'orchestration_sessions',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('session_uid', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=128), nullable=False),
        sa.Column('graph_name', sa.String(length=128), server_default='opportunity_graph', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='active', nullable=False),
        sa.Column('current_node', sa.String(length=128), nullable=True),
        sa.Column('completion_pct', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('errors', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=False), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_orch_sessions_id', 'orchestration_sessions', ['id'])
    op.create_index('ix_orch_sessions_session_uid', 'orchestration_sessions', ['session_uid'], unique=True)
    op.create_index('ix_orch_sessions_user_id', 'orchestration_sessions', ['user_id'])
    op.create_index('ix_orch_sessions_status', 'orchestration_sessions', ['status'])
    op.create_index('ix_orch_sessions_user_status', 'orchestration_sessions', ['user_id', 'status'])
    op.create_index('ix_orch_sessions_created_at', 'orchestration_sessions', ['created_at'])

    # ── orchestration_events ────────────────────────────────────
    op.create_table(
        'orchestration_events',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('event_uid', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.BigInteger(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('node_name', sa.String(length=128), nullable=True),
        sa.Column('agent_name', sa.String(length=128), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='completed', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('duration_ms', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['orchestration_sessions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_orch_events_id', 'orchestration_events', ['id'])
    op.create_index('ix_orch_events_event_uid', 'orchestration_events', ['event_uid'], unique=True)
    op.create_index('ix_orch_events_session_id', 'orchestration_events', ['session_id'])
    op.create_index('ix_orch_events_event_type', 'orchestration_events', ['event_type'])
    op.create_index('ix_orch_events_session_type', 'orchestration_events', ['session_id', 'event_type'])
    op.create_index('ix_orch_events_created_at', 'orchestration_events', ['created_at'])

    # ── autonomous_actions ──────────────────────────────────────
    op.create_table(
        'autonomous_actions',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('action_uid', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.String(length=128), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='pending', nullable=False),
        sa.Column('confidence', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('reasoning_chain', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('evidence_chain', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('governance_verdict', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('suppressed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('suppression_reason', sa.String(length=256), nullable=True),
        sa.Column('mcp_tool_used', sa.String(length=128), nullable=True),
        sa.Column('mcp_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['orchestration_sessions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_autonomous_actions_id', 'autonomous_actions', ['id'])
    op.create_index('ix_autonomous_actions_action_uid', 'autonomous_actions', ['action_uid'], unique=True)
    op.create_index('ix_autonomous_actions_session_id', 'autonomous_actions', ['session_id'])
    op.create_index('ix_autonomous_actions_user_id', 'autonomous_actions', ['user_id'])
    op.create_index('ix_autonomous_actions_action_type', 'autonomous_actions', ['action_type'])
    op.create_index('ix_autonomous_actions_status', 'autonomous_actions', ['status'])
    op.create_index('ix_autonomous_actions_session_status', 'autonomous_actions', ['session_id', 'status'])
    op.create_index('ix_autonomous_actions_user_type', 'autonomous_actions', ['user_id', 'action_type'])
    op.create_index('ix_autonomous_actions_created_at', 'autonomous_actions', ['created_at'])

    # ── notification_history ────────────────────────────────────
    op.create_table(
        'notification_history',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('notification_uid', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=128), nullable=False),
        sa.Column('opportunity_id', sa.String(length=128), nullable=True),
        sa.Column('channel', sa.String(length=32), server_default='voice', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='queued', nullable=False),
        sa.Column('voice_script', sa.Text(), nullable=True),
        sa.Column('elevenlabs_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('twilio_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('call_sid', sa.String(length=128), nullable=True),
        sa.Column('call_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('urgency_score', sa.Float(), nullable=True),
        sa.Column('suppressed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('suppression_reason', sa.String(length=256), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notification_history_id', 'notification_history', ['id'])
    op.create_index('ix_notification_history_notification_uid', 'notification_history', ['notification_uid'], unique=True)
    op.create_index('ix_notification_history_user_id', 'notification_history', ['user_id'])
    op.create_index('ix_notification_history_opportunity_id', 'notification_history', ['opportunity_id'])
    op.create_index('ix_notification_history_channel', 'notification_history', ['channel'])
    op.create_index('ix_notification_history_status', 'notification_history', ['status'])
    op.create_index('ix_notification_history_opp_status', 'notification_history', ['opportunity_id', 'status'])
    op.create_index('ix_notification_history_created_at', 'notification_history', ['created_at'])

    # ── opportunity_scores ──────────────────────────────────────
    op.create_table(
        'opportunity_scores',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('opportunity_id', sa.String(length=128), nullable=False),
        sa.Column('user_id', sa.String(length=128), nullable=False),
        sa.Column('session_id', sa.BigInteger(), nullable=True),
        sa.Column('overall_score', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('confidence', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('dimension_scores', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('dimension_weights', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('evidence_citations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reasoning', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('priority_rank', sa.Integer(), nullable=True),
        sa.Column('urgency_score', sa.Float(), nullable=True),
        sa.Column('generated_by', sa.String(length=64), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['orchestration_sessions.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('opportunity_id', 'user_id', 'session_id'),
    )
    op.create_index('ix_opportunity_scores_id', 'opportunity_scores', ['id'])
    op.create_index('ix_opportunity_scores_opportunity_id', 'opportunity_scores', ['opportunity_id'])
    op.create_index('ix_opportunity_scores_user_id', 'opportunity_scores', ['user_id'])
    op.create_index('ix_opportunity_scores_user_rank', 'opportunity_scores', ['user_id', 'priority_rank'])
    op.create_index('ix_opportunity_scores_created_at', 'opportunity_scores', ['created_at'])

    # ── governance_decisions ────────────────────────────────────
    op.create_table(
        'governance_decisions',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('session_id', sa.BigInteger(), nullable=False),
        sa.Column('action_id', sa.BigInteger(), nullable=True),
        sa.Column('decision_type', sa.String(length=64), nullable=False),
        sa.Column('verdict', sa.String(length=32), server_default='passed', nullable=False),
        sa.Column('rule_violated', sa.String(length=256), nullable=True),
        sa.Column('confidence_before', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('confidence_after', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('penalty_applied', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['orchestration_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['action_id'], ['autonomous_actions.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_governance_decisions_id', 'governance_decisions', ['id'])
    op.create_index('ix_governance_decisions_session_id', 'governance_decisions', ['session_id'])
    op.create_index('ix_governance_decisions_decision_type', 'governance_decisions', ['decision_type'])
    op.create_index('ix_governance_decisions_verdict', 'governance_decisions', ['verdict'])
    op.create_index('ix_governance_decisions_session_verdict', 'governance_decisions', ['session_id', 'verdict'])
    op.create_index('ix_governance_decisions_created_at', 'governance_decisions', ['created_at'])

    # ── mcp_execution_logs ──────────────────────────────────────
    op.create_table(
        'mcp_execution_logs',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('execution_uid', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.BigInteger(), nullable=False),
        sa.Column('action_id', sa.BigInteger(), nullable=True),
        sa.Column('tool_name', sa.String(length=128), nullable=False),
        sa.Column('server_name', sa.String(length=64), server_default='unknown', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='pending', nullable=False),
        sa.Column('attempt', sa.Integer(), server_default='1', nullable=False),
        sa.Column('request_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('response_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.BigInteger(), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['orchestration_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['action_id'], ['autonomous_actions.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_mcp_execution_logs_id', 'mcp_execution_logs', ['id'])
    op.create_index('ix_mcp_execution_logs_execution_uid', 'mcp_execution_logs', ['execution_uid'], unique=True)
    op.create_index('ix_mcp_execution_logs_session_id', 'mcp_execution_logs', ['session_id'])
    op.create_index('ix_mcp_execution_logs_tool_name', 'mcp_execution_logs', ['tool_name'])
    op.create_index('ix_mcp_execution_logs_status', 'mcp_execution_logs', ['status'])
    op.create_index('ix_mcp_execution_logs_session_tool', 'mcp_execution_logs', ['session_id', 'tool_name'])
    op.create_index('ix_mcp_execution_logs_status_created', 'mcp_execution_logs', ['status', 'created_at'])
    op.create_index('ix_mcp_execution_logs_created_at', 'mcp_execution_logs', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_mcp_execution_logs_created_at', table_name='mcp_execution_logs')
    op.drop_index('ix_mcp_execution_logs_status_created', table_name='mcp_execution_logs')
    op.drop_index('ix_mcp_execution_logs_session_tool', table_name='mcp_execution_logs')
    op.drop_index('ix_mcp_execution_logs_status', table_name='mcp_execution_logs')
    op.drop_index('ix_mcp_execution_logs_tool_name', table_name='mcp_execution_logs')
    op.drop_index('ix_mcp_execution_logs_session_id', table_name='mcp_execution_logs')
    op.drop_index('ix_mcp_execution_logs_execution_uid', table_name='mcp_execution_logs')
    op.drop_index('ix_mcp_execution_logs_id', table_name='mcp_execution_logs')
    op.drop_table('mcp_execution_logs')

    op.drop_index('ix_governance_decisions_created_at', table_name='governance_decisions')
    op.drop_index('ix_governance_decisions_session_verdict', table_name='governance_decisions')
    op.drop_index('ix_governance_decisions_verdict', table_name='governance_decisions')
    op.drop_index('ix_governance_decisions_decision_type', table_name='governance_decisions')
    op.drop_index('ix_governance_decisions_session_id', table_name='governance_decisions')
    op.drop_index('ix_governance_decisions_id', table_name='governance_decisions')
    op.drop_table('governance_decisions')

    op.drop_index('ix_opportunity_scores_created_at', table_name='opportunity_scores')
    op.drop_index('ix_opportunity_scores_user_rank', table_name='opportunity_scores')
    op.drop_index('ix_opportunity_scores_user_id', table_name='opportunity_scores')
    op.drop_index('ix_opportunity_scores_opportunity_id', table_name='opportunity_scores')
    op.drop_index('ix_opportunity_scores_id', table_name='opportunity_scores')
    op.drop_table('opportunity_scores')

    op.drop_index('ix_notification_history_created_at', table_name='notification_history')
    op.drop_index('ix_notification_history_opp_status', table_name='notification_history')
    op.drop_index('ix_notification_history_status', table_name='notification_history')
    op.drop_index('ix_notification_history_channel', table_name='notification_history')
    op.drop_index('ix_notification_history_opportunity_id', table_name='notification_history')
    op.drop_index('ix_notification_history_user_id', table_name='notification_history')
    op.drop_index('ix_notification_history_notification_uid', table_name='notification_history')
    op.drop_index('ix_notification_history_id', table_name='notification_history')
    op.drop_table('notification_history')

    op.drop_index('ix_autonomous_actions_created_at', table_name='autonomous_actions')
    op.drop_index('ix_autonomous_actions_user_type', table_name='autonomous_actions')
    op.drop_index('ix_autonomous_actions_session_status', table_name='autonomous_actions')
    op.drop_index('ix_autonomous_actions_status', table_name='autonomous_actions')
    op.drop_index('ix_autonomous_actions_action_type', table_name='autonomous_actions')
    op.drop_index('ix_autonomous_actions_user_id', table_name='autonomous_actions')
    op.drop_index('ix_autonomous_actions_session_id', table_name='autonomous_actions')
    op.drop_index('ix_autonomous_actions_action_uid', table_name='autonomous_actions')
    op.drop_index('ix_autonomous_actions_id', table_name='autonomous_actions')
    op.drop_table('autonomous_actions')

    op.drop_index('ix_orch_events_created_at', table_name='orchestration_events')
    op.drop_index('ix_orch_events_session_type', table_name='orchestration_events')
    op.drop_index('ix_orch_events_event_type', table_name='orchestration_events')
    op.drop_index('ix_orch_events_session_id', table_name='orchestration_events')
    op.drop_index('ix_orch_events_event_uid', table_name='orchestration_events')
    op.drop_index('ix_orch_events_id', table_name='orchestration_events')
    op.drop_table('orchestration_events')

    op.drop_index('ix_orch_sessions_created_at', table_name='orchestration_sessions')
    op.drop_index('ix_orch_sessions_user_status', table_name='orchestration_sessions')
    op.drop_index('ix_orch_sessions_status', table_name='orchestration_sessions')
    op.drop_index('ix_orch_sessions_user_id', table_name='orchestration_sessions')
    op.drop_index('ix_orch_sessions_session_uid', table_name='orchestration_sessions')
    op.drop_index('ix_orch_sessions_id', table_name='orchestration_sessions')
    op.drop_table('orchestration_sessions')
