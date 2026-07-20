---
title: "System Architecture"
document_id: "06_system_architecture"
domain: "architecture"
feature: "system architecture"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - architecture
  - diagram
---

# System Architecture

CareerOS uses a browser frontend, FastAPI API layer, PostgreSQL database, Redis cache/queue, Qdrant vector store, external LLM/embedding providers, job providers, and optional communication providers.

```mermaid
flowchart LR
  U["Authenticated candidate"] --> FE["Next.js frontend"]
  FE --> API["FastAPI backend /api/v1"]
  API --> PG["PostgreSQL via SQLAlchemy"]
  API --> Redis["Redis cache, locks, ARQ queues"]
  API --> Q["Qdrant vector collections"]
  API --> LLM["Gemini primary + DeepSeek fallback"]
  API --> Emb["NVIDIA NV-Embed embeddings"]
  API --> Jobs["TheirStack jobs API"]
  API --> Voice["ElevenLabs ConvAI voice agent"]
  Voice --> External["External ConvAI phone-number configuration"]
```

## Persistence Boundaries

PostgreSQL stores users, knowledge documents, resume chunks, jobs, matches, packages, interview sessions, orchestration sessions, communications, voice sessions, transcripts, learning records, and audit/governance records. Qdrant stores vectors and payload metadata for resumes, jobs, knowledge, and docs-RAG chunks. Redis stores caches, locks, streams, backpressure state, and worker queue data.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/main.py`
- `backend/src/core/config.py`
- `docker-compose.yml`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
