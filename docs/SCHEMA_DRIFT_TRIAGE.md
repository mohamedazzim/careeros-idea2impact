# Schema Drift Triage

This document records the Alembic/model drift found during the public
submission schema gate and how each class of drift was resolved.

Fresh database baseline:

| Check | Result |
|---|---|
| Initial Alembic head | `032_skill_gap_schema_alignment` |
| Initial detected operations | `300` |
| Post-dialect-filter detected operations | `238` |
| Post-model-alignment detected operations | `211` |
| Final Alembic head | `033_schema_contract_alignment` |
| Final detected operations | `0` |

## Triage Table

| Object | Operation | Category | Model Contract | Migration Contract | Runtime Impact | Resolution |
|---|---|---|---|---|---|---|
| `langgraph_checkpoints` | `remove_table` | INTENTIONAL EXTERNAL TABLE | Not part of CareerOS SQLAlchemy app metadata | Created by migration `022_autonomous_engagement_platform` for local/demo support | Needed by LangGraph checkpointing; dropping would break persisted agent state | Excluded exact table name in `backend/alembic/env.py`; no wildcard table exclusion |
| JSON payload columns | `modify_type` JSONB vs JSON | POSTGRESQL DIALECT DIFFERENCE | Models use portable SQLAlchemy `JSON` | PostgreSQL migrations created JSONB-compatible storage | No runtime mismatch for reads/writes used by the app | Exact JSONB-inspected-to-JSON-model type comparison ignored in `backend/alembic/env.py` |
| String/Text columns | `modify_type` Text vs String | ALEMBIC REPRESENTATION DIFFERENCE | Models use bounded/unbounded strings based on domain | PostgreSQL reflects text-like columns differently | No application behavior change | Exact Text-inspected-to-String-model comparison ignored in `backend/alembic/env.py` |
| Date/time columns | `modify_type` TIMESTAMP vs DateTime | POSTGRESQL DIALECT DIFFERENCE | Models use SQLAlchemy `DateTime`/`DateTime(timezone=True)` | PostgreSQL reflects `TIMESTAMP` dialect types | No serialization change introduced by the schema gate | Exact PostgreSQL TIMESTAMP-inspected-to-DateTime-model comparison ignored in `backend/alembic/env.py` |
| `approval_*`, `approvals`, `audit_logs`, `career_coach_goals`, `circuit_states`, `evaluation_runs`, `generated_packages`, `hallucination_audits`, `job_matches`, `jobs`, `knowledge_docs`, `pending_jobs`, `resumes`, `roadmap_*`, `user_preferences` | `modify_nullable` nullable DB to non-null model | REAL MISSING MIGRATION | Defaulted operational columns should be non-null after creation | Earlier migrations left these columns nullable | Nulls could weaken API assumptions and diagnostics | Added forward migration `033_schema_contract_alignment` with safe backfills then `SET NOT NULL` |
| `interview_sessions`, `interview_questions`, `interview_weakness_history` | `modify_nullable` non-null DB to nullable model | MODEL SEMANTIC ERROR | Defaulted interview runtime fields should remain non-null | Earlier migrations correctly enforced non-null | Weakening these fields would allow incomplete interview records | Updated `backend/src/models/interview.py` to declare the existing non-null contract |
| `skill_gap_analysis_runs.updated_at`, `skill_gap_finding_evidence.updated_at` | `remove_column` | MODEL SEMANTIC ERROR | Skill-gap audit rows benefit from update timestamps | Migrations created `updated_at` columns | Dropping would remove useful audit state | Added `updated_at` to `backend/src/models/skill_gap.py` |
| Named indexes listed in `ALEMBIC_REPRESENTATION_INDEXES` | `add_index` / `remove_index` | INDEX OR CONSTRAINT DIFFERENCE | Models and migrations differ on helper index naming and single-column index declarations | Existing migrations created old helper indexes and composite indexes | Not a correctness issue for the golden path; some are redundant or naming-only | Exact-name index comparison filter in `backend/alembic/env.py`; no global index ignore |
| Named unique constraints listed in `ALEMBIC_REPRESENTATION_UNIQUE_CONSTRAINTS` | `remove_constraint` | INDEX OR CONSTRAINT DIFFERENCE | Models often express uniqueness through `unique=True` or unique indexes | Existing DB has FK-backed unique constraints | Dropping these can break dependent foreign keys | Exact-name unique-constraint filter in `backend/alembic/env.py`; constraints remain in DB |
| Unnamed model unique constraints for `autonomous_actions`, `mcp_execution_logs`, `notification_history`, `orchestration_events`, `orchestration_sessions` | `add_constraint` | NAMING CONVENTION DIFFERENCE | Metadata has unnamed uniqueness declarations | DB has existing unique indexes/constraints with legacy names | Creating duplicates adds noise without improving correctness | Exact table/column tuple filter in `backend/alembic/env.py` |

## Runtime Verification Notes

The schema gate was verified from an isolated PostgreSQL container, not from a
personal or production database.

Required result:

| Command | Expected Result |
|---|---|
| `poetry -C backend run alembic heads` | One head: `033_schema_contract_alignment` |
| `poetry -C backend run alembic upgrade head` | Pass from an empty database |
| `poetry -C backend run alembic current` | `033_schema_contract_alignment (head)` |
| `poetry -C backend run alembic check` | `No new upgrade operations detected.` |

## Guardrails

- No global `compare_type=False` was used.
- No global `compare_server_default=False` was used.
- No wildcard table exclusion was used.
- No broad index ignore was used.
- `033_schema_contract_alignment` does not drop data-bearing columns.
- `033_schema_contract_alignment` backfills nullable values before enforcing
  `NOT NULL`.
