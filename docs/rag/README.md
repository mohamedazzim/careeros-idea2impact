# CareerOS RAG Documentation

Last verified from source code: 2026-06-14

This directory is the canonical RAG knowledge pack for the current CareerOS codebase snapshot.
It is written from live application code, not from prior audit reports.

## What this pack covers

- Product and architecture overview
- Frontend routes, shells, hooks, and UI behavior
- Backend routers, APIs, and service boundaries
- Agents, LLM providers, prompts, and governance
- End-to-end workflows and orchestration graphs
- Data models and persistence surfaces
- Security, observability, and deployment behavior
- Mentor/HR chatbot support content

## Quick facts

- Frontend pages: 27
- Backend ORM model classes: 67
- Core agents in `backend/src/agents`: 11
- LangGraph modules: 3
- Primary LLM: Gemini 2.5 Flash
- Fallback LLM: DeepSeek NIM via `FallbackProvider`
- Main auth token: `careeros_token`
- Main realtime transport: WebSocket
- Voice and telephony integrations: ElevenLabs and Twilio through MCP governance
- Docs RAG runtime: `backend/src/services/rag/service.py` + `backend/src/api/v1/endpoints/demo_rag.py`

## Reading order

| Order | File | Use |
| --- | --- | --- |
| 1 | [architecture.md](./architecture.md) | System overview |
| 2 | [frontend.md](./frontend.md) | Pages, hooks, shell, and UI flows |
| 3 | [backend_apis.md](./backend_apis.md) | REST and websocket surface |
| 4 | [agents_llms_prompts.md](./agents_llms_prompts.md) | Agents, LLMs, and prompts |
| 5 | [workflows.md](./workflows.md) | End-to-end runtime flows |
| 6 | [data_models.md](./data_models.md) | Persistence and model inventory |
| 7 | [ops_security.md](./ops_security.md) | Security and operations |
| 8 | [FEATURE_STATUS.md](./FEATURE_STATUS.md) | What is implemented today |
| 9 | [DEMO_FAQ.md](./DEMO_FAQ.md) | Mentor/HR-friendly answers |
| 10 | [AGENT_CARDS.md](./AGENT_CARDS.md) | One card per core agent |
| 11 | [WORKFLOW_EXAMPLES.md](./WORKFLOW_EXAMPLES.md) | Step-by-step workflow examples |
| 12 | [API_EXAMPLES.md](./API_EXAMPLES.md) | Request/response examples |
| 13 | [MAKE_RAG_CHATBOT.md](./MAKE_RAG_CHATBOT.md) | Make.com + Qdrant chatbot design |
| 14 | [INDEXING_MANIFEST.md](./INDEXING_MANIFEST.md) | Chunking and metadata plan |
| 15 | [GOLDEN_QUESTIONS.md](./GOLDEN_QUESTIONS.md) | RAG test questions |
| 16 | [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md) | Honest gaps and risks |
| 17 | [PROJECT_HIGHLIGHTS.md](./PROJECT_HIGHLIGHTS.md) | Reviewer-focused highlights |

## Source-of-truth rule

If this documentation and the source code disagree, the source code wins.
When the code changes, update the relevant RAG docs so retrieval stays accurate.
