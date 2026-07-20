---
title: "Agents Prompts And LLM Workflows"
document_id: "13_agents_prompts_and_llm_workflows"
domain: "ai"
feature: "agents prompts llm"
audience:
  - user
  - developer
  - operator
implementation_status: "PARTIALLY_IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - agents
  - llm
  - prompts
---

# Agents, Prompts, And LLM Workflows

CareerOS has deterministic services, LLM-backed services, graph-like orchestration services, and provider-specific agents. The active LLM factory uses Gemini 2.5 Flash as the primary provider when `GEMINI_API_KEY` is configured and DeepSeek NIM through NVIDIA as fallback. If Gemini is absent, DeepSeek becomes primary but requires `NVIDIA_API_KEY`.

## Implemented Agent Families

- Opportunity alert and notification decision agents: `backend/src/agents/opportunity_alert_agent.py`, `backend/src/agents/notification_decision_agent.py`.
- Voice-related agents: the supported opportunity voice path is ElevenLabs ConvAI through `backend/src/services/opportunity/conversational_outbound_call_service.py` and `backend/src/services/opportunity/voice_opportunity_agent.py`; older synthesis/Twilio agent files are not the primary opportunity voice-agent path.
- Interview services and graph: `backend/src/services/interview/*`, `backend/src/graphs/interview_graph.py`.
- Outcome intelligence graph: `backend/src/graphs/outcome_intelligence_graph.py`.
- Governance and MCP routing: `backend/src/services/mcp/mcp_router.py`, `backend/src/services/mcp/mcp_governance.py`.

## LLM Usage

Application packages use `get_reasoning_provider()` and structured output schema `PackageContent`. Docs-RAG answer generation uses `get_llm_provider()` and `RagLLMOutput`. Outcome intelligence can classify transcripts through an LLM-backed classifier with deterministic fallback. Several interview and roadmap services use the shared LLM provider patterns.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/services/llm/factory.py`
- `backend/src/api/v1/endpoints/packages.py`
- `backend/src/services/rag/service.py`
- `backend/src/agents`
- `backend/src/graphs`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
