---
title: "RAG And Mentor Chatbot"
document_id: "12_rag_and_mentor_chatbot"
domain: "rag"
feature: "mentor chatbot"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - rag
  - qdrant
  - mentor
---

# RAG And Mentor Chatbot

The CareerOS mentor/docs RAG chatbot is implemented by `backend/src/services/rag/service.py` and exposed through `backend/src/api/v1/endpoints/demo_rag.py`. It indexes Markdown documentation from `docs/rag_v2`, embeds chunks with NVIDIA NV-Embed, stores vectors in Qdrant collection `careeros_rag_docs`, retrieves top chunks for a question, optionally relays to Make.com, and otherwise generates a cited answer with Gemini primary and DeepSeek fallback.

## Indexing Flow

```mermaid
flowchart TD
  A["POST /api/v1/demo-rag/index"] --> B["DemoRagService.index_docs"]
  B --> C["Discover markdown under docs/rag_v2"]
  C --> D["Parse headings into RagChunk records"]
  D --> E["Split long sections at 2800 chars"]
  E --> F["EmbeddingService.generate_embeddings input_type=passage"]
  F --> G["QdrantService.upsert_points collection=careeros_rag_docs"]
```

## Retrieval And Answer Generation Flow

```mermaid
sequenceDiagram
  participant FE as Frontend chatbot
  participant API as POST /api/v1/demo-rag/chat
  participant RAG as DemoRagService
  participant EMB as NVIDIA NV-Embed
  participant Q as Qdrant careos_rag_docs
  participant Make as Optional Make.com webhook
  participant LLM as Gemini/DeepSeek
  FE->>API: session_id, question, viewer_role, top_k
  API->>RAG: chat(request)
  RAG->>RAG: validate question and reject secret seeking
  RAG->>EMB: embed_query(question)
  RAG->>Q: search score_threshold=0.25 limit=top_k
  alt RAG_USE_MAKE and MAKE_RAG_WEBHOOK_URL
    RAG->>Make: request plus retrieved chunks
    Make-->>RAG: optional answer JSON
  else local answer
    RAG->>LLM: structured JSON answer with numbered citations
  end
  RAG-->>API: answer, confidence, citations
  API-->>FE: DemoRagChatResponse
```

## Active Configuration

| Setting | Value or behavior | Evidence |
| --- | --- | --- |
| Collection | `careeros_rag_docs` | `backend/src/core/config.py::QDRANT_RAG_DOCS_COLLECTION` |
| Embedding model label | `nvidia/nv-embed-v1` | `backend/src/core/config.py::RAG_EMBEDDING_MODEL` |
| Embedding dimensions | 4096 | `backend/src/services/vector_store/qdrant_service.py::DIMENSIONS` |
| LLM model label | `gemini-2.5-flash` | `backend/src/core/config.py::RAG_LLM_MODEL` |
| Score threshold | 0.25 | `backend/src/services/rag/service.py::DEFAULT_SCORE_THRESHOLD` |
| Top K default | 6 | `backend/src/services/rag/service.py::DEFAULT_TOP_K` |
| Max context chars | 12000 | `backend/src/services/rag/service.py::MAX_CONTEXT_CHARS` |
| Make relay | Optional; falls back to local RAG on failure | `backend/src/services/rag/service.py::_relay_to_make` |

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/services/rag/service.py`
- `backend/src/api/v1/endpoints/demo_rag.py`
- `backend/src/services/vector_store/qdrant_service.py`
- `backend/src/services/embedding/embedding_service.py`
- `frontend/src/lib/demo-rag.ts`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
