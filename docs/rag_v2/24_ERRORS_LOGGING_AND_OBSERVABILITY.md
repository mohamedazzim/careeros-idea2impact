---
title: "Errors Logging And Observability"
document_id: "24_errors_logging_and_observability"
domain: "ops"
feature: "errors logging observability"
audience:
  - user
  - developer
  - operator
implementation_status: "PARTIALLY_IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - logging
  - errors
  - observability
---

# Errors, Logging, And Observability

The backend uses structured logging patterns, explicit provider status fields, diagnostics routes, and database rows for long-running workflow state. Opportunity, voice, job refresh, and transcript sync paths each persist operational state in addition to returning API responses.

## Important Observable States

- Job refresh creates orchestration sessions and diagnostics.
- Communication requests persist provider, status, metadata, attempts, and failure reasons.
- Voice initiation reports dry-run, payload validation, bridge errors, and upstream HTTP errors.
- Transcript sync records retry and permanent failure states.
- Docs-RAG health reports vector store and collection status.

## Gaps

The repository does not show a single centralized tracing backend or full distributed trace wiring. External provider dashboards are required to complete call and webhook observability.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/services/job_refresh.py`
- `backend/src/services/opportunity/communication_orchestrator.py`
- `backend/src/services/opportunity/conversational_outbound_call_service.py`
- `backend/src/services/opportunity/elevenlabs_transcript_sync.py`
- `backend/src/api/v1/endpoints/demo_rag.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
