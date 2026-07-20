---
title: "Backend Architecture"
document_id: "08_backend_architecture"
domain: "backend"
feature: "backend architecture"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - backend
  - fastapi
---

# Backend Architecture

The CareerOS backend is a FastAPI service with route modules in `backend/src/api/v1/endpoints`, persistence repositories in `backend/src/db/repositories`, SQLAlchemy models in `backend/src/models`, domain services in `backend/src/services`, provider integrations in `backend/src/integrations`, background workers in `backend/src/workers`, and graph/agent modules in `backend/src/graphs` and `backend/src/agents`.

## Registered API Surface

The evidence scan found 213 route decorators. Most route modules are registered by `backend/src/main.py`. The full route table is in `09_API_REFERENCE.md`.

## Service Layers

- Auth/security: `backend/src/services/security/*`.
- Resume/knowledge processing: `backend/src/api/v1/endpoints/knowledge.py`, `backend/src/services/processing/*`, `backend/src/services/intelligence/resume_analysis_service.py`.
- Vector retrieval: `backend/src/services/vector_store/qdrant_service.py`, `backend/src/services/retrieval/*`.
- RAG chatbot: `backend/src/services/rag/service.py`.
- Jobs and matching: `backend/src/services/job_refresh.py`, `backend/src/integrations/theirstack/*`, `backend/src/services/opportunity/job_intelligence_service.py`.
- Voice: `backend/src/services/opportunity/conversational_outbound_call_service.py`, `backend/src/services/opportunity/voice_opportunity_agent.py`.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/api/v1/endpoints`
- `backend/src/services`
- `backend/src/models`
- `backend/src/main.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
