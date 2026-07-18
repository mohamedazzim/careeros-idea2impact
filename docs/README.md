# CareerOS Docs

Last verified from source code: 2026-06-20

This folder is the canonical documentation entrypoint for the current CareerOS snapshot.
The RAG knowledge pack lives in `docs/rag/`.

Publication and setup references:

- [Repository README](../README.md)
- [Environment configuration](./ENVIRONMENT.md)
- [Credential configuration](./CREDENTIAL_CONFIGURATION.md)
- [Publication readiness](./PUBLICATION_READINESS.md)
- [Backend test triage](./BACKEND_TEST_TRIAGE.md)
- [Schema drift triage](./SCHEMA_DRIFT_TRIAGE.md)
- [Troubleshooting](./TROUBLESHOOTING.md)

## Recommended reading order

1. [docs/rag/README.md](./rag/README.md)
2. [docs/rag/architecture.md](./rag/architecture.md)
3. [docs/rag/frontend.md](./rag/frontend.md)
4. [docs/rag/backend_apis.md](./rag/backend_apis.md)
5. [docs/rag/agents_llms_prompts.md](./rag/agents_llms_prompts.md)
6. [docs/rag/workflows.md](./rag/workflows.md)
7. [docs/rag/data_models.md](./rag/data_models.md)
8. [docs/rag/ops_security.md](./rag/ops_security.md)
9. [docs/rag/FEATURE_STATUS.md](./rag/FEATURE_STATUS.md)
10. [docs/rag/DEMO_FAQ.md](./rag/DEMO_FAQ.md)
11. [docs/rag/AGENT_CARDS.md](./rag/AGENT_CARDS.md)
12. [docs/rag/WORKFLOW_EXAMPLES.md](./rag/WORKFLOW_EXAMPLES.md)
13. [docs/rag/API_EXAMPLES.md](./rag/API_EXAMPLES.md)
14. [docs/rag/MAKE_RAG_CHATBOT.md](./rag/MAKE_RAG_CHATBOT.md)
15. [docs/rag/INDEXING_MANIFEST.md](./rag/INDEXING_MANIFEST.md)
16. [docs/rag/GOLDEN_QUESTIONS.md](./rag/GOLDEN_QUESTIONS.md)
17. [docs/rag/KNOWN_LIMITATIONS.md](./rag/KNOWN_LIMITATIONS.md)
18. [docs/rag/PROJECT_HIGHLIGHTS.md](./rag/PROJECT_HIGHLIGHTS.md)

## Additional architecture snapshots

These files describe the current codebase implementation outside the RAG knowledge pack:

1. [docs/current-architecture.md](./current-architecture.md)
2. [docs/data-flow.md](./data-flow.md)
3. [docs/entity-relationship.md](./entity-relationship.md)
4. [docs/service-map.md](./service-map.md)

## Current milestone note

M3 Learning Outcome Tracking, M4 Skill Graph Schema and Import Dashboard, and M5 Evidence-backed Skill Gap Engine are implemented in the current codebase and documented in the V2 snapshots above.

## Publication gate note

The current public snapshot was verified with fresh Alembic migration to `033_schema_contract_alignment`, `alembic check` with zero detected upgrade operations, backend pytest, frontend typecheck/lint/Vitest/build, and a synthetic Docker golden path using local Qdrant and dry-run external actions.

## Source-of-truth rule

If docs and source code disagree, the source code wins.
