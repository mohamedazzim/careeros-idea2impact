import asyncio
import os
import sys
from logging.config import fileConfig

# Ensure /app is in sys.path for src module
app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from sqlalchemy import Column, DateTime, MetaData, String, Table, inspect, pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.sqltypes import JSON, Text

from src.core.config import settings
from src.models.base import Base
import src.models.resume  # ensure models are loaded
import src.models.interview  # Phase 4D models
import src.models.orchestration  # Phase 5 models
import src.models.user  # Phase 12.5B user auth model
import src.models.jobs  # Phase 17.5 jobs intelligence
import src.models.approvals  # Phase 17.5 approvals
import src.models.roadmap  # Phase 17.5 career roadmap
import src.models.evaluation_prefs  # Phase 17.5 evaluation & preferences
import src.models.knowledge  # Phase 17.7 knowledge documents
import src.models.package  # Phase 17.7 generated packages
import src.models.troubleshoot  # Phase 17.7 troubleshoot/ops
import src.models.rerank  # Phase 18.1 reranking analytics
import src.models.package_version  # Phase 18.3 package version history
import src.models.learning  # Phase 18.4 verified learning paths
import src.models.opportunity_alert
import src.models.career_events
import src.models.outcome_intelligence
import src.models.report
import src.models.skill_graph  # Phase 19.0 skill graph schema
import src.models.skill_gap  # Phase 19.1 evidence-backed skill gap schema

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


EXTERNALLY_MANAGED_TABLES = {
    # LangGraph checkpointing owns this table at runtime. CareerOS migrations
    # create it for local/demo convenience, but SQLAlchemy app metadata should
    # not model or drop it.
    "langgraph_checkpoints",
}


# Legacy migrations created a mix of explicit unique constraints, helper
# indexes, and old index names. These exact names are intentionally retained so
# fresh installs do not drop FK-backed unique constraints or churn equivalent
# index representations during Alembic's comparison pass.
ALEMBIC_REPRESENTATION_INDEXES = {
    "idx_rerank_created",
    "idx_rerank_user_created",
    "ix_autonomous_actions_action_uid",
    "ix_autonomous_actions_id",
    "ix_career_events_confidence",
    "ix_career_events_created_at",
    "ix_career_events_entity_id",
    "ix_career_events_entity_type",
    "ix_career_events_event_time",
    "ix_career_events_event_type",
    "ix_career_events_provider",
    "ix_career_events_request_id",
    "ix_career_events_schema_version",
    "ix_career_events_source_service",
    "ix_career_events_status",
    "ix_career_events_trace_id",
    "ix_career_events_user_id",
    "ix_communication_requests_created_at",
    "ix_conversation_sessions_conversation_id",
    "ix_conversation_sync_jobs_conversation_id",
    "ix_conversation_transcripts_conversation_id",
    "ix_governance_decisions_id",
    "ix_interview_questions_session_qidx",
    "ix_interview_sessions_type",
    "ix_interview_weakness_history_type",
    "ix_interview_weakness_history_weakness_type",
    "ix_jobs_seniority",
    "ix_jobs_tech_role",
    "ix_learning_activity_events_activity_uid",
    "ix_learning_activity_events_created_at",
    "ix_learning_path_items_created_at",
    "ix_learning_path_items_learning_path",
    "ix_learning_path_items_learning_path_id",
    "ix_learning_path_items_resource_id",
    "ix_learning_resource_discovery_runs_completed_at",
    "ix_learning_resource_discovery_runs_created_at",
    "ix_learning_resource_discovery_runs_run_uid",
    "ix_learning_resource_provenance_records_created_at",
    "ix_learning_resource_provenance_records_job_id",
    "ix_learning_resource_provenance_records_provenance_uid",
    "ix_learning_resource_provenance_records_source_entity_id",
    "ix_learning_resources_created_at",
    "ix_learning_resources_skill_slug",
    "ix_learning_sessions_created_at",
    "ix_learning_sessions_session_uid",
    "ix_learning_sessions_status",
    "ix_mcp_execution_logs_execution_uid",
    "ix_mcp_execution_logs_id",
    "ix_mcp_execution_logs_status",
    "ix_mcp_execution_logs_status_created",
    "ix_notification_history_id",
    "ix_notification_history_notification_uid",
    "ix_opportunity_call_outcomes_conversation_id",
    "ix_opportunity_conversation_contexts_created_at",
    "ix_opportunity_conversion_metrics_calculated_at",
    "ix_opportunity_intelligence_reports_opportunity_rank_score",
    "ix_opportunity_lifecycle_runs_created_at",
    "ix_opportunity_outcome_events_created_at",
    "ix_opportunity_outcome_metrics_calculated_at",
    "ix_opportunity_scores_id",
    "ix_orch_events_created_at",
    "ix_orch_events_event_type",
    "ix_orch_events_event_uid",
    "ix_orch_events_id",
    "ix_orch_events_session_id",
    "ix_orch_sessions_created_at",
    "ix_orch_sessions_id",
    "ix_orch_sessions_session_uid",
    "ix_orch_sessions_status",
    "ix_orch_sessions_user_id",
    "ix_orchestration_events_created_at",
    "ix_orchestration_events_event_type",
    "ix_orchestration_events_session_id",
    "ix_orchestration_sessions_created_at",
    "ix_orchestration_sessions_status",
    "ix_orchestration_sessions_user_id",
    "ix_package_versions_package_id",
    "ix_resource_feedback_created_at",
    "ix_resource_feedback_feedback_uid",
    "ix_resource_outcomes_created_at",
    "ix_resource_outcomes_resource_id",
    "ix_resume_chunks_chunk_index",
    "ix_resume_versions_created_at",
    "ix_resume_versions_version_num",
    "ix_resumes_created_at",
    "ix_resumes_status",
    "ix_resumes_task_id",
    "ix_salary_intelligence_job_id",
    "ix_skill_graph_aliases_alias_uid",
    "ix_skill_graph_aliases_created_at",
    "ix_skill_graph_aliases_source_pk",
    "ix_skill_graph_aliases_source_table",
    "ix_skill_graph_edges_created_at",
    "ix_skill_graph_edges_edge_uid",
    "ix_skill_graph_edges_first_seen_at",
    "ix_skill_graph_edges_last_seen_at",
    "ix_skill_graph_edges_source_pk",
    "ix_skill_graph_edges_source_table",
    "ix_skill_graph_evidence_created_at",
    "ix_skill_graph_evidence_evidence_uid",
    "ix_skill_graph_evidence_recorded_at",
    "ix_skill_graph_evidence_source_pk",
    "ix_skill_graph_import_runs_created_at",
    "ix_skill_graph_import_runs_run_uid",
    "ix_skill_graph_nodes_created_at",
    "ix_skill_graph_nodes_skill_slug",
    "ix_user_skill_learning_paths_generated_at",
    "ix_user_skill_learning_paths_skill_slug",
    "ix_user_skill_learning_paths_user_id",
    "ix_user_skill_states_created_at",
    "ix_user_skill_states_state_uid",
    "ix_voice_outcomes_created_at",
    "ix_voice_sessions_created_at",
}

ALEMBIC_REPRESENTATION_UNIQUE_CONSTRAINTS = {
    "conversation_sessions_conversation_id_key",
    "conversation_sync_jobs_conversation_id_key",
    "conversation_transcripts_conversation_id_key",
    "opportunity_call_outcomes_conversation_id_key",
    "salary_intelligence_job_id_key",
    "uq_learning_activity_events_activity_uid",
    "uq_learning_resource_discovery_runs_run_uid",
    "uq_learning_resource_provenance_records_uid",
    "uq_learning_sessions_session_uid",
    "uq_resource_feedback_feedback_uid",
    "uq_resource_outcomes_resource_id",
    "uq_skill_graph_aliases_alias_uid",
    "uq_skill_graph_edges_edge_uid",
    "uq_skill_graph_evidence_evidence_uid",
    "uq_skill_graph_import_runs_run_uid",
    "uq_skill_graph_nodes_skill_slug",
    "uq_user_skill_states_state_uid",
}

ALEMBIC_REPRESENTATION_UNNAMED_UNIQUES = {
    ("autonomous_actions", ("action_uid",)),
    ("mcp_execution_logs", ("execution_uid",)),
    ("notification_history", ("notification_uid",)),
    ("orchestration_events", ("event_uid",)),
    ("orchestration_sessions", ("session_uid",)),
}


def include_object(object_, name, type_, reflected, compare_to):
    """Keep Alembic drift checks focused on CareerOS-owned metadata."""
    if type_ == "table" and name in EXTERNALLY_MANAGED_TABLES:
        return False
    if type_ == "index" and name in ALEMBIC_REPRESENTATION_INDEXES:
        return False
    if (
        type_ == "unique_constraint"
        and name in ALEMBIC_REPRESENTATION_UNIQUE_CONSTRAINTS
    ):
        return False
    if type_ == "unique_constraint" and name is None:
        columns = tuple(column.name for column in object_.columns)
        table_name = object_.table.name
        if (table_name, columns) in ALEMBIC_REPRESENTATION_UNNAMED_UNIQUES:
            return False
    return True


def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    """Ignore confirmed PostgreSQL representation differences only."""
    if isinstance(inspected_type, postgresql.JSONB) and isinstance(metadata_type, JSON):
        return False
    if isinstance(inspected_type, Text) and isinstance(metadata_type, String):
        return False
    if isinstance(inspected_type, postgresql.TIMESTAMP) and isinstance(metadata_type, DateTime):
        return False
    return None


def _ensure_version_table_capacity(connection: Connection) -> None:
    """Allow revision identifiers longer than Alembic's 32-character default."""
    if not inspect(connection).has_table("alembic_version"):
        metadata = MetaData()
        Table(
            "alembic_version",
            metadata,
            Column("version_num", String(64), primary_key=True),
        ).create(connection)
        return

    if connection.dialect.name == "postgresql":
        connection.execute(
            text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(64)"
            )
        )

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=compare_type,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    with connection.begin():
        _ensure_version_table_capacity(connection)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
