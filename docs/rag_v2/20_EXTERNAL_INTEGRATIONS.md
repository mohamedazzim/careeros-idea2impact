---
title: "External Integrations"
document_id: "20_external_integrations"
domain: "integrations"
feature: "external providers"
audience:
  - user
  - developer
  - operator
implementation_status: "PARTIALLY_IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - integrations
  - twilio
  - qdrant
---

# External Integrations

CareerOS integrates with infrastructure providers, AI providers, job-data providers, and communication providers. This file states what is code-backed versus externally configured.

## Integration Inventory

- Qdrant: implemented for resume, job, knowledge, and docs-RAG collections.
- NVIDIA NV-Embed: implemented through `EmbeddingService` and `NVEmbedService`.
- Gemini and DeepSeek/NVIDIA: implemented through the LLM factory.
- TheirStack: implemented as the verified real job provider.
- ElevenLabs ConvAI: the only supported CareerOS opportunity voice-agent path; implemented for outbound opportunity calls and transcript polling.
- Twilio: wrappers and MCP service exist, but Twilio is not the CareerOS voice-agent path. Telephony wiring is external to the ElevenLabs ConvAI phone-number setup.
- Pipedream: implemented as webhook adapter and possible relay for the ConvAI payload, not as a separate voice-agent implementation.
- Make.com: implemented as optional docs-RAG relay only.
- Redis, Celery, PostgreSQL, and Alembic: used by backend runtime, workers, and migrations.

## Twilio Boundary

`twilio_adapter.py`, `twilio_mcp_service.py`, `mcp_router.py`, and `twilio_server.py` implement Twilio-facing adapter surfaces. Comments and tests indicate the opportunity voice-call path is conversational-agent mode with provider `elevenlabs_convai`, not direct Twilio REST call initiation by the opportunity alert path. RAG answers about voice should cite ConvAI docs first and treat Twilio as external/supporting plumbing only.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/services/vector_store/qdrant_service.py`
- `backend/src/services/embedding/embedding_service.py`
- `backend/src/services/llm/factory.py`
- `backend/src/integrations/theirstack/sync_service.py`
- `backend/src/services/mcp/twilio_adapter.py`
- `backend/src/services/mcp/twilio_mcp_service.py`
- `backend/src/mcp_servers/twilio_server.py`
- `backend/src/core/config.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
