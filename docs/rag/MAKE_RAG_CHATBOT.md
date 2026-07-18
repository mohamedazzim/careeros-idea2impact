# Make.com + Qdrant RAG Chatbot

Last verified from source code: 2026-06-14

This document is the implementation contract for the CareerOS mentor/HR docs chatbot.
The backend now owns the docs indexer, retrieval, answer generation, and admin index route.
Make.com is optional orchestration/gateway wiring.

## Runtime flow

1. Frontend sends a question to the FastAPI chatbot endpoint.
2. Backend validates the question and rejects obvious secret-seeking or injection attempts.
3. Backend optionally relays to Make.com when `RAG_USE_MAKE=true` and `MAKE_RAG_WEBHOOK_URL` is configured.
4. Backend retrieves top-k chunks from the dedicated Qdrant docs collection.
5. Backend generates a JSON answer from retrieved context only.
6. Frontend renders the answer, citations, confidence, and follow-up questions.

## FastAPI endpoints

### `POST /api/v1/demo-rag/chat`

Request:

```json
{
  "session_id": "mentor-demo-session",
  "question": "Which agents are implemented?",
  "viewer_role": "mentor",
  "top_k": 6
}
```

Response:

```json
{
  "status": "ok",
  "answer": "CareerOS has 11 core agents documented in the codebase.",
  "confidence": 0.91,
  "citations": [
    {
      "doc_name": "README.md",
      "section_title": "Quick facts",
      "source_path": "docs/rag/README.md",
      "score": 0.93
    }
  ],
  "follow_up_questions": [
    "Do you want the responsibilities for each agent?",
    "Should I show the files that define them?"
  ],
  "needs_verification": false
}
```

### `POST /api/v1/demo-rag/index`

Admin-only route.

Query parameters:

- `recreate` - optional boolean, defaults to `false`

Behavior:

- Loads all `docs/rag/*.md` files.
- Splits content by headings.
- Creates stable chunk IDs.
- Embeds each chunk.
- Upserts into Qdrant collection `careeros_rag_docs`.

Example result:

```json
{
  "status": "ok",
  "files_indexed": 17,
  "chunks_indexed": 84,
  "successful_upserts": 84,
  "failed_chunks": 0,
  "collection": "careeros_rag_docs",
  "source_path": "docs/rag"
}
```

### `GET /api/v1/demo-rag/health`

Returns docs-RAG runtime status, file count, collection readiness, and configured model names.

### `GET /api/v1/demo-rag/golden-questions`

Returns the golden question corpus used for RAG smoke testing.

## Make webhook input

When Make relaying is enabled, the backend sends the normalized request payload:

```json
{
  "session_id": "mentor-demo-session",
  "question": "Which agents are implemented?",
  "viewer_role": "mentor",
  "top_k": 6,
  "source": "careeros-demo-rag"
}
```

## Make webhook output

Make should return the same normalized response contract as the backend.
If a field is missing, the backend normalizes it before returning it to the frontend.

## Qdrant collection

Dedicated docs collection:

- `careeros_rag_docs`

This collection stores docs-RAG chunks only.
It must not be mixed with candidate memory, resume memory, or job vectors.

## Chunk metadata

The indexer stores these payload fields in Qdrant:

- `chunk_id`
- `doc_name`
- `section_title`
- `source_path`
- `chunk_index`
- `updated_at`
- `content_hash`
- `text`
- `source`

## Retrieval rules

- Validate the question before retrieval.
- Reject empty, too-long, prompt-injection, and secret-seeking questions.
- Embed the question with the docs embedding model.
- Search `careeros_rag_docs` with top-k retrieval and a score threshold.
- If no strong context is found, return `NO_RELEVANT_CONTEXT`.
- Answer only from retrieved context.
- Include citations with exact file paths.
- If the source is unclear, set `needs_verification=true`.

## Answer format

The backend returns strict JSON:

```json
{
  "status": "ok",
  "answer": "...",
  "confidence": 0.0,
  "citations": [
    {
      "doc_name": "...",
      "section_title": "...",
      "source_path": "...",
      "score": 0.0
    }
  ],
  "follow_up_questions": [],
  "needs_verification": false
}
```

## Error response format

```json
{
  "status": "error",
  "answer": "",
  "confidence": 0.0,
  "citations": [],
  "follow_up_questions": [],
  "needs_verification": true,
  "error": {
    "code": "UPSTREAM_TIMEOUT",
    "message": "The Make.com webhook did not respond in time."
  }
}
```

## Security rules

- Do not expose secrets, tokens, or user PII.
- Keep the docs collection separate from candidate/job memory.
- Make.com should not become the policy boundary for sensitive requests.
- The backend should remain the source of truth for validation and fallback behavior.
- Do not answer from stale audit notes when the source code disagrees.

## Manual steps still needed in Make.com

- Build the webhook scenario if you want external orchestration.
- Add any routing, logging, or notification steps.
- Keep the response contract unchanged.
- Confirm the secret header name if you do not use `X-API-Key`.

## Source anchors

- `backend/src/api/v1/endpoints/demo_rag.py`
- `backend/src/services/rag/service.py`
- `backend/src/services/vector_store/qdrant_service.py`
- `backend/src/core/config.py`
- `frontend/src/app/demo-rag/page.tsx`
- `docs/rag/*`
