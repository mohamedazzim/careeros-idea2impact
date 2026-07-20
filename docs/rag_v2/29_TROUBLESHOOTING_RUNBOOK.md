---
title: "Troubleshooting Runbook"
document_id: "29_troubleshooting_runbook"
domain: "ops"
feature: "troubleshooting"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - runbook
  - troubleshooting
---

# Troubleshooting Runbook

## Docs-RAG Returns Weak Or Uncited Answers

Check that `docs/rag_v2` is the active docs path, Qdrant is reachable, `careeros_rag_docs` exists, embeddings are 4096-dimensional, and the index endpoint has completed. Run retrieval validation over the v2 corpus before debugging external providers.

## Voice Call Does Not Start

Enable dry run and inspect the ConvAI payload. Confirm recipient number normalization, `ELEVENLABS_CONVAI_AGENT_ID`, `ELEVENLABS_CONVAI_PHONE_NUMBER_ID`, ConvAI provider access, and that the destination number is not the configured sender/test number. `PIPEDREAM_WEBHOOK_URL` is only a relay for the same ConvAI payload.

## Transcript Missing

Confirm provider response included a conversation ID, then run the transcript sync path. Inspect `ConversationSyncJob` for retry or permanent failure. Without a provider conversation ID, transcript correlation is not reliable.

## Jobs Are Sparse

Check TheirStack credentials, billing state, query preview behavior, fallback broad query, India/location filters, and tech role filters. Other provider labels should not be treated as real sync evidence unless code exists.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/services/rag/service.py`
- `backend/src/services/opportunity/conversational_outbound_call_service.py`
- `backend/src/services/opportunity/elevenlabs_transcript_sync.py`
- `backend/src/integrations/theirstack/sync_service.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
