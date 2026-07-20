---
title: "Known Limitations And Technical Debt"
document_id: "25_known_limitations_and_technical_debt"
domain: "quality"
feature: "limitations"
audience:
  - user
  - developer
  - operator
implementation_status: "PARTIALLY_IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - limitations
  - debt
---

# Known Limitations And Technical Debt

This list records code-evidenced limitations that should stay visible to RAG users.

- External provider dashboards were not available for inspection.
- The active docs-RAG service previously indexed `docs/rag`; v2 is now the canonical corpus and the service path points to `docs/rag_v2`.
- Make.com is implemented only for docs-RAG relay; no Make.com voice workflow definition was found.
- Pipedream voice bridge behavior depends on external workflow configuration.
- Current outbound voice call prompt override is not injected by the active call path.
- No inbound ElevenLabs callback route was found; transcripts are retrieved by polling or explicit process requests.
- Direct Twilio wrappers exist, but the active opportunity conversational call path is ElevenLabs ConvAI.
- Resume upload background analysis is in-process and should move to durable queueing for production reliability.
- Matching is deterministic and heuristic rather than trained or independently calibrated.
- Some provider names and UI health displays describe configured/provider-dependent capabilities rather than verified real sync.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/services/rag/service.py`
- `backend/src/services/opportunity/conversational_outbound_call_service.py`
- `backend/src/services/opportunity/voice_opportunity_agent.py`
- `backend/src/services/opportunity/conversation_retrieval_agent.py`
- `backend/src/integrations/theirstack/sync_service.py`
- `backend/src/api/v1/endpoints/knowledge.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
