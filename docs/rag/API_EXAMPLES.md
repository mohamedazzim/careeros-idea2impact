# API Examples

Last verified from source code: 2026-06-14

Warning: these examples are simplified for documentation.
Verify them before live API testing, especially if your deployment uses custom auth or proxy headers.

## Auth login

Request shape:

```json
{
  "email": "user@example.com",
  "password": "StrongPassword123!"
}
```

Example response:

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "expires_in": 900
}
```

Source anchors:

- `backend/src/api/v1/endpoints/auth.py`
- `backend/src/services/security/auth.py`

## Knowledge upload

Request shape:

```json
{
  "filename": "resume.pdf",
  "content": "Plain text resume content",
  "doc_type": "resume"
}
```

Example response:

```json
{
  "runId": "c6c0e8f7-0fd7-4fa6-9b39-1f2b75f4e7d1",
  "message": "Document registered and analysis pipeline initiated"
}
```

## Knowledge analyze

Request shape:

```json
{
  "job_description": "Backend engineer role with FastAPI and PostgreSQL"
}
```

Example response:

```json
{
  "runId": "4e5e1c67-1be2-4f0f-bd55-b52b3f5e8c2d",
  "status": "started"
}
```

## Jobs refresh

Request shape:

```json
{
  "resume_id": "resume_123",
  "target_role": "Backend Engineer",
  "target_location": "Remote",
  "salary_preference": "20-30 LPA"
}
```

Example response:

```json
{
  "session_uid": "5d7c69d7-69cf-4ee2-9e4c-7c4e4f4f7b11",
  "session_id": 42,
  "status": "queued",
  "message": "Job matching enqueued. Poll GET /jobs/refresh/42 for progress.",
  "started_at": "2026-06-13T12:00:00Z"
}
```

## Opportunity discovery

Request shape:

```json
{
  "candidate_context": {
    "role": "Backend Engineer",
    "location": "Remote"
  }
}
```

Example response:

```json
{
  "run_id": "0bb4a1bc-1dbe-4f70-9e2d-4d1e7c69a6f1",
  "opportunities": [
    {
      "id": "123",
      "title": "Backend Engineer",
      "company": "Acme Labs",
      "overall_score": 87.4
    }
  ],
  "resume_status": "matched_against_active_resume",
  "market_signals_count": 18,
  "pipeline_elapsed_ms": 842.31
}
```

## Interview start

Request shape:

```json
{
  "interview_type": "technical",
  "mode": "voice",
  "resume_context": {
    "title": "Backend Engineer Resume"
  }
}
```

Example response:

```json
{
  "session_uid": "interview-123",
  "interview_type": "technical",
  "mode": "voice",
  "first_question": "Tell me about your recent backend work.",
  "total_questions": 6,
  "status": "started"
}
```

## Orchestration trigger

Request shape:

```json
{
  "candidate_context": {
    "role": "Backend Engineer"
  },
  "opportunities": [],
  "phone_number": "+15555550123",
  "auto_execute": true
}
```

Example response:

```json
{
  "session_uid": "6f8adfe4-1e5f-4aa8-9cf4-0f9cf6b3a7f5",
  "status": "active",
  "current_node": "initialized",
  "completion_pct": 0.0
}
```

## Approval approve and reject

Approve:

```bash
curl -X POST http://localhost:8000/api/v1/approvals/approval_123/approve \
  -H "Authorization: Bearer <access_token>"
```

Reject:

```bash
curl -X POST "http://localhost:8000/api/v1/approvals/approval_123/reject?reason=not%20now" \
  -H "Authorization: Bearer <access_token>"
```

Example responses:

```json
{ "status": "approved", "approval_uid": "approval_123" }
```

```json
{ "status": "rejected", "approval_uid": "approval_123", "reason": "not now" }
```

## Health check

```bash
curl http://localhost:8000/api/health/live
```

Example response:

```json
{
  "status": "ok",
  "timestamp": "<utc timestamp>",
  "service": "CareerOS",
  "environment": "<environment>"
}
```

## Demo RAG chat

Request shape:

```json
{
  "session_id": "mentor-demo-session",
  "question": "Which agents are implemented?",
  "viewer_role": "mentor",
  "top_k": 6
}
```

Example response:

```json
{
  "status": "ok",
  "answer": "CareerOS currently has 11 core agents in the registry.",
  "confidence": 0.92,
  "citations": [
    {
      "doc_name": "README.md",
      "section_title": "Quick facts",
      "source_path": "docs/rag/README.md",
      "score": 0.93
    }
  ],
  "follow_up_questions": [
    "Do you want the agent responsibilities as well?"
  ],
  "needs_verification": false
}
```

Source anchors:

- `backend/src/api/v1/endpoints/demo_rag.py`
- `backend/src/services/rag/service.py`
- `frontend/src/app/demo-rag/page.tsx`
- `docs/rag/MAKE_RAG_CHATBOT.md`

## Demo RAG index

Request:

```bash
curl -X POST "http://localhost:8000/api/v1/demo-rag/index?recreate=false" \
  -H "Authorization: Bearer <access_token>"
```

Example response:

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

## Demo RAG health

```bash
curl http://localhost:8000/api/v1/demo-rag/health
```

Example response:

```json
{
  "status": "ok",
  "collection": "careeros_rag_docs",
  "docs_path": "docs/rag",
  "files_found": 17,
  "chunks_known": 84,
  "qdrant_ready": true,
  "qdrant_collection_ready": true,
  "embedding_model": "nvidia/nv-embed-v1",
  "llm_model": "gemini-2.5-flash",
  "make_enabled": false,
  "last_indexed_at": "2026-06-14T00:00:00+00:00"
}
```

## Demo RAG golden questions

```bash
curl http://localhost:8000/api/v1/demo-rag/golden-questions
```

Example response:

```json
{
  "status": "ok",
  "collection": "careeros_rag_docs",
  "questions": [
    {
      "question": "What is CareerOS?",
      "expected_source_file": "docs/rag/architecture.md",
      "expected_answer_type": "Overview",
      "must_mention": ["career operations platform"],
      "should_not_mention": ["fake features"]
    }
  ]
}
```
