---
title: "Workflow Automation And Make.com"
document_id: "19_workflow_automation_and_make_com"
domain: "automation"
feature: "make pipedream workflows"
audience:
  - user
  - developer
  - operator
implementation_status: "PARTIALLY_IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - make
  - pipedream
  - automation
---

# Workflow Automation And Make.com

The codebase contains Make.com for docs-RAG answer relay and Pipedream for non-voice opportunity communication/webhook plumbing. The CareerOS voice agent should be documented as ElevenLabs ConvAI only. A Make.com voice-call workflow was not found, and Pipedream should not be described as a separate voice-agent implementation.

## Make.com Docs-RAG Relay

`DemoRagService._relay_to_make` sends the user question, retrieved chunks, top-k, viewer role, and session ID to `MAKE_RAG_WEBHOOK_URL` when `RAG_USE_MAKE` is enabled. If `MAKE_RAG_API_KEY` is present, it is sent as an `X-API-Key` header. If the relay fails or returns no usable answer, CareerOS falls back to local LLM answer generation.

## Pipedream Communication Bridge

`PipedreamAdapter` supports webhook delivery for opportunity communication. The voice path deliberately skips generic webhook delivery in `CommunicationOrchestrator` because voice calls use ElevenLabs ConvAI. `ElevenLabsConversationalOutboundCallService` can use `PIPEDREAM_WEBHOOK_URL` only as a relay for the ConvAI outbound-call payload.

## External Workflow Status

The repository does not contain exported Make.com or Pipedream scenario definitions. Provider-side routing, authentication, retries, and ElevenLabs ConvAI phone-number wiring are external and must be verified in those services.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/services/rag/service.py`
- `backend/src/services/opportunity/pipedream_adapter.py`
- `backend/src/services/opportunity/communication_orchestrator.py`
- `backend/src/services/opportunity/conversational_outbound_call_service.py`
- `backend/src/core/config.py`
- `docs/rag_legacy/MAKE_RAG_CHATBOT.md`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
