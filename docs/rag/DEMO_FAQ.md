# Demo FAQ

Last verified from source code: 2026-06-14

## What is CareerOS?

CareerOS is an AI-powered career operations platform.
It helps a user upload a resume, analyze job fit, generate application assets, run interview practice, track opportunities, and trigger governed outbound engagement when the fit is strong enough.

Source anchors:

- `backend/src/main.py`
- `frontend/src/app/layout.tsx`
- `frontend/src/components/AppShell.tsx`
- `frontend/src/hooks/useCareerOS.ts`

## What features are implemented?

The current codebase includes auth, resume and knowledge upload, job refresh and match scoring, opportunity discovery, generated application packages, live interview practice, approvals, orchestration traces, ops health, rerank monitoring, readiness reporting, and the docs RAG chatbot runtime.

Source anchors:

- `docs/rag/FEATURE_STATUS.md`
- `backend/src/api/v1/endpoints/*`
- `frontend/src/app/*`
- `backend/src/services/rag/service.py`

## Which agents are used?

The core agent layer has 11 agents:

- `OpportunityDiscoveryAgent`
- `OpportunityScoringAgent`
- `OpportunityPrioritizationAgent`
- `DeadlineUrgencyAgent`
- `NotificationDecisionAgent`
- `ElevenLabsVoiceSynthesisAgent`
- `TwilioVoiceAgent`
- `OrchestrationGovernanceAgent`
- `ExplainabilityAgent`
- `AgentObservability`
- `OpportunityAlertAgent`

## How does job matching work?

1. A resume or knowledge file is uploaded and indexed.
2. The jobs pipeline refreshes provider data.
3. The matching engine compares resume context with job context.
4. Scores are assigned for skill overlap, seniority fit, freshness, and related signals.
5. The Jobs page and Opportunities page show ranked results.

Source anchors:

- `backend/src/api/v1/endpoints/jobs.py`
- `backend/src/api/v1/endpoints/opportunities_api.py`
- `backend/src/services/opportunity/job_intelligence_service.py`

## How does the RAG pipeline work?

1. The docs pack in `docs/rag/` is indexed into `careeros_rag_docs`.
2. The backend splits markdown by heading and assigns stable chunk IDs.
3. Each chunk gets embedding vectors and metadata like source path and section title.
4. The chat endpoint retrieves top-k chunks for a question.
5. The answer is generated from retrieved context only and returns citations.

Source anchors:

- `backend/src/services/rag/service.py`
- `backend/src/services/vector_store/qdrant_service.py`
- `backend/src/api/v1/endpoints/demo_rag.py`

## How does the voice-call workflow work?

1. An opportunity is discovered or scored.
2. Governance decides whether an outbound action is allowed.
3. ElevenLabs prepares the voice payload.
4. Twilio places the call through the MCP router.
5. Communication and outcome records are persisted.

## What skills does this project demonstrate?

- Full-stack engineering
- FastAPI service design
- Next.js App Router UI work
- Async Python and SQLAlchemy
- Workflow orchestration with LangGraph
- Retrieval and ranking systems
- Voice and telephony integration
- Governance and audit logging
- Observability and health checks

## What can be tested in the demo?

- Login and logout
- Resume upload and knowledge analysis
- Job refresh and ranked matches
- Opportunity intelligence and alerts
- Interview start and websocket flow
- Approval review and execution
- Ops health and troubleshoot views
- Orchestration history and governance traces
- MCP test flow for provider connectivity
- Demo RAG chat, indexing, health, and golden questions

## What are the current limitations?

- Make.com is still optional orchestration wiring; the backend can answer directly when it is not configured.
- Some external features depend on provider credentials.
- Voice workflows need browser mic permissions and runtime provider access.
- Roadmap and coach flows should be verified against the latest source before a live demo.
- The docs chatbot should still be verified in the exact deployment environment before external release.
