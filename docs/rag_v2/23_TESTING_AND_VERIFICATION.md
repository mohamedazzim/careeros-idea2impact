---
title: "Testing And Verification"
document_id: "23_testing_and_verification"
domain: "quality"
feature: "testing"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - tests
  - verification
---

# Testing And Verification

CareerOS has targeted backend tests for authentication, docs-RAG, job refresh, TheirStack sync, location and role filtering, opportunity matching, call safety, Twilio MCP behavior, packages, interview, orchestration, and governance.

## Recommended Validation Layers

- Run focused tests for any changed subsystem.
- Run docs validation after editing `docs/rag_v2`.
- Run retrieval validation to ensure golden questions map to relevant source documents.
- Run provider dry-runs for ElevenLabs/Pipedream before enabling live calls.
- Run startup validation in production-like configuration before deployment.

## Documentation Validation

The v2 corpus includes `retrieval_validation/test_queries.json`, `retrieval_validation/retrieval_results.json`, and `retrieval_validation/RETRIEVAL_VALIDATION_REPORT.md`. These are lexical smoke tests over generated docs, not a replacement for Qdrant/NV-Embed indexing tests.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/tests`
- `docs/rag_v2/retrieval_validation`
- `backend/src/services/rag/service.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
