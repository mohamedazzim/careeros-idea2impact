# Golden Questions

Last verified from source code: 2026-06-14

| Question | Expected source file | Expected answer type | Must mention | Should not mention |
| --- | --- | --- | --- | --- |
| What is CareerOS? | `docs/rag/architecture.md` | Overview | Full-stack career operations platform | Fake features |
| How many core agents are used? | `backend/src/agents/__init__.py` | Count | 11 core agents | Unsupported extra agents |
| Which agent scores opportunities? | `backend/src/agents/opportunity_scoring_agent.py` | Fact | `OpportunityScoringAgent` | `Needs verification` unless unclear |
| How does job matching work? | `backend/src/api/v1/endpoints/jobs.py` | Workflow | Refresh, match score, active resume | Direct database writes |
| What does the Knowledge Hub do? | `backend/src/api/v1/endpoints/knowledge.py` | Feature summary | Upload, analyze, score | Vector collection names not in code |
| Which pages exist in the frontend? | `docs/rag/frontend.md` | Route list | Dashboard, Jobs, Knowledge, Interview | Made-up routes |
| How does the interview flow work? | `backend/src/api/v1/endpoints/interview.py` | Workflow | Start, respond, pause, resume | Old API shapes |
| How does orchestration work? | `backend/src/api/v1/endpoints/orchestration.py` | Workflow | Trigger, history, governance, traces | In-memory sessions |
| What is the primary LLM? | `backend/src/core/config.py` | Fact | Gemini 2.5 Flash | Other providers as primary |
| What is the fallback LLM? | `backend/src/core/config.py` | Fact | DeepSeek NIM | Gemini as fallback |
| What is the auth token name? | `frontend/src/lib/auth-session.ts` | Fact | `careeros_token` | LocalStorage-only claims |
| What does the jobs refresh endpoint return? | `backend/src/api/v1/endpoints/jobs.py` | API response | `session_uid`, `session_id`, `status`, `message` | Placeholder response bodies |
| What does the knowledge analyze endpoint return? | `backend/src/api/v1/endpoints/knowledge.py` | API response | `runId`, `status` | Unmentioned fields |
| What is the voice-call workflow? | `backend/src/services/opportunity/conversational_outbound_call_service.py` | Workflow | ElevenLabs, Twilio, MCP router | One-way only speech claims |
| Which files describe MCP governance? | `backend/src/services/mcp/mcp_router.py` | File list | Governance, audit logging, routing | Direct provider calls |
| What does the approval flow support? | `backend/src/api/v1/endpoints/approvals.py` | Feature summary | approve, reject, execute, comment, edit | Unsupported bulk actions |
| What does the ops page show? | `frontend/src/components/OpsCenterView.tsx` | UI summary | health, circuits, audit, pending | Nonexistent dashboards |
| What is the readiness page for? | `backend/src/api/v1/endpoints/readiness.py` | Feature summary | score, timeline, explain, report | Fake ML pipeline claims |
| What is the RAG chatbot runtime contract? | `docs/rag/MAKE_RAG_CHATBOT.md` | Contract | `POST /api/v1/demo-rag/chat`, `POST /api/v1/demo-rag/index`, `GET /api/v1/demo-rag/health` | Unsupported route names |
| What Qdrant collection should docs use? | `docs/rag/MAKE_RAG_CHATBOT.md` | Fact | `careeros_rag_docs` | Candidate/job collections |
| What are the main data stores? | `docs/rag/data_models.md` | Fact | PostgreSQL, Redis, Qdrant | MongoDB |
| Which model classes store opportunity outcomes? | `backend/src/models/outcome_intelligence.py` | Fact | `OpportunityCallOutcome`, `LearningLoopRun` | Unconfirmed class names |
| Which model stores orchestration sessions? | `backend/src/models/orchestration.py` | Fact | `OrchestrationSession` | In-memory dicts |
| How do reports work? | `backend/src/api/v1/endpoints/readiness.py` | Workflow | report, reports, download | Unimplemented exports |
| Which endpoints are in the opportunities API? | `backend/src/api/v1/endpoints/opportunities_api.py` | API list | discover, list, rc3, alert, skill-gap | Old alias names |
| What is the route for the live interview page? | `frontend/src/app/interview/page.tsx` | Route answer | `/interview` | Hidden route guesses |
| What should the chatbot do if uncertain? | `docs/rag/KNOWN_LIMITATIONS.md` | Policy | Say `Needs verification` | Hallucinate |
| What skills does the project demonstrate? | `docs/rag/PROJECT_HIGHLIGHTS.md` | Summary | AI, backend, frontend, orchestration | Overclaiming production readiness |
| What are the main limitations? | `docs/rag/KNOWN_LIMITATIONS.md` | Limitations list | external dependencies, verification gaps | Secret values |
| Which files power the outbound call workflow? | `backend/src/services/opportunity/communication_orchestrator.py` | File list | ElevenLabs, Twilio, MCP | Direct Twilio SDK calls only |
| What does `careeros_rag_docs` mean? | `docs/rag/MAKE_RAG_CHATBOT.md` | Design answer | Dedicated docs collection | Current production truth |
| What should a good RAG answer cite? | `docs/rag/MAKE_RAG_CHATBOT.md` | Policy | exact file paths, endpoints | Uncited guesses |
| Which frontend page is best for job matches? | `frontend/src/app/jobs/page.tsx` | UI answer | Jobs page, ranked matches | Random dashboards |
| Which page is best for mentor/HR demos? | `docs/rag/DEMO_FAQ.md` | Recommendation | demo FAQ and feature status | Internal-only jargon |
