---
title: "Indexing Manifest"
document_id: "31_indexing_manifest"
domain: "retrieval"
feature: "indexing"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - indexing
  - manifest
---

# Indexing Manifest

The canonical RAG source corpus is `docs/rag_v2`. Each Markdown file has front matter, a stable document ID, implementation status, verified source files, and code-grounded limitations.

## Chunking Guidance

Use heading-aware Markdown chunking. Preserve front matter metadata, document title, section heading, implementation status, and source file references in payload metadata. Use Qdrant collection `careeros_rag_docs` with 4096-dimensional cosine vectors.

## Retrieval Guidance

Prefer answers with cited source documents. Voice questions should retrieve `32_ELEVENLABS_MAKE_TWILIO_OPPORTUNITY_CALL.md` first for the end-to-end ElevenLabs, Make.com, Twilio, threshold, dynamic-variable, and bilingual workflow. Use `14_ELEVENLABS_VOICE_AGENT.md` for code-level ConvAI behavior and `15_VOICE_AGENT_DATA_FLOW.md` for transcript/storage details. Cite `19_WORKFLOW_AUTOMATION_AND_MAKE_COM.md` or `20_EXTERNAL_INTEGRATIONS.md` when the user specifically asks about Make.com, Pipedream, Twilio, or external-provider boundaries.

## Updating The Live RAG Index

The service now resolves its corpus root to `docs/rag_v2`. To make the chatbot cite these new docs:

1. Restart the backend so `RAG_DIR_NAME = "rag_v2"` is loaded.
2. Recreate/reindex the docs collection with `POST /api/v1/demo-rag/index` using an authenticated user token and `{"recreate": true}`.
3. Or run the repository helper from `backend`: `poetry run python scripts/verify_demo_rag_index.py --reindex`.
4. Ask a voice question and confirm citations include `docs/rag_v2/14_ELEVENLABS_VOICE_AGENT.md` or `docs/rag_v2/15_VOICE_AGENT_DATA_FLOW.md`.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/services/rag/service.py`
- `backend/src/services/vector_store/qdrant_service.py`
- `docs/rag_v2/source_traceability.json`
- `docs/rag_v2/indexing_manifest.json`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
