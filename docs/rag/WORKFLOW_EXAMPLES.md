# Workflow Examples

Last verified from source code: 2026-06-14

## 1) Resume upload and analysis

1. User opens the Knowledge Hub.
2. User uploads a PDF, DOCX, or text resume.
3. The backend extracts text and stores the document.
4. Analysis starts immediately and a `runId` is created.
5. The frontend can poll the document score or open the alignment report.

Source anchors:

- `frontend/src/app/knowledge/page.tsx`
- `frontend/src/components/KnowledgeHub.tsx`
- `backend/src/api/v1/endpoints/knowledge.py`

## 2) Job refresh and matching

1. User opens the Jobs page.
2. User triggers refresh.
3. Backend starts a refresh session and enqueues job ingestion.
4. Matching runs against the active indexed resume.
5. The Jobs page shows the ranked feed and the refresh status.

Source anchors:

- `frontend/src/app/jobs/page.tsx`
- `frontend/src/components/JobsIntelligenceView.tsx`
- `backend/src/api/v1/endpoints/jobs.py`

## 3) Opportunity scoring and prioritization

1. The opportunity pipeline loads candidate context.
2. The system pulls market context and active jobs.
3. `OpportunityScoringAgent` evaluates multiple dimensions.
4. `DeadlineUrgencyAgent` adds urgency.
5. `OpportunityPrioritizationAgent` computes the final priority.
6. Governance decides whether a notification or call is allowed.

Source anchors:

- `backend/src/agents/opportunity_scoring_agent.py`
- `backend/src/agents/opportunity_prioritization_agent.py`
- `backend/src/agents/deadline_urgency_agent.py`
- `backend/src/agents/notification_decision_agent.py`

## 4) Voice-call workflow

1. A strong opportunity is discovered.
2. Governance validates that the call threshold is met.
3. `ElevenLabsVoiceSynthesisAgent` prepares the voice payload.
4. `TwilioVoiceAgent` sends the call through MCP routing.
5. The communication record and outcome records are persisted.

Source anchors:

- `backend/src/services/opportunity/communication_orchestrator.py`
- `backend/src/services/opportunity/conversational_outbound_call_service.py`
- `backend/src/services/mcp/mcp_router.py`

## 5) Interview workflow

1. User opens the Interview page.
2. The browser requests microphone access.
3. The frontend starts a session with interview type and mode.
4. Voice or text responses are sent to the backend.
5. The interview graph asks follow-up questions, evaluates answers, and closes the session.

Source anchors:

- `frontend/src/app/interview/page.tsx`
- `backend/src/api/v1/endpoints/interview.py`
- `backend/src/graphs/interview_graph.py`

## 6) Outcome intelligence workflow

1. Conversation data is retrieved after an event or call.
2. The conversation is classified.
3. Candidate concerns are extracted.
4. Memory records are updated.
5. Results are persisted for later timeline and memory queries.

Source anchors:

- `backend/src/services/opportunity/outcome_intelligence.py`
- `backend/src/api/v1/endpoints/outcome_intelligence.py`
- `backend/src/services/opportunity/career_memory.py`

## 7) Mentor/HR RAG chatbot workflow

1. Ingest the `docs/rag/` markdown files into a dedicated Qdrant collection.
2. Chunk by heading and keep source anchors with each chunk.
3. Embed the chunks.
4. Retrieve the top-k closest chunks for the question.
5. Generate the answer from retrieved context only.
6. Return strict JSON with answer, citations, confidence, and follow-ups.

Source anchors:

- `backend/src/api/v1/endpoints/demo_rag.py`
- `backend/src/services/rag/service.py`
- `backend/src/services/vector_store/qdrant_service.py`
- `frontend/src/app/demo-rag/page.tsx`
