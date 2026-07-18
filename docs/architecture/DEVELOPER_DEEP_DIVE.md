# Developer Deep Dive — CareerOS

**Generated**: 2026-06-06  
**Purpose**: Complete developer understanding guide for maintenance, extension, and onboarding.  
**Verified Against**: Source code (canonical)

---

## 1. Feature Deep Dives

### 1.1 User Authentication

**What It Does**: Full JWT authentication system with registration, login, password reset, account lockout, RBAC, and token revocation.

**Why It Exists**: Foundation for all protected features. Every API endpoint and frontend page requires or optionally uses authentication.

**Entry Point**: `POST /api/v1/auth/register` or `POST /api/v1/auth/login`

**Backend Route**: `backend/src/api/v1/endpoints/auth.py`

**Services Used**:
- `services/security/auth.py` — `AuthService` (JWT encode/decode, password hashing, lockout)
- `services/security/audit.py` — `AuditService` (event logging)

**Libraries Used**: `python-jose` (JWT HS256), `passlib` (bcrypt/PBKDF2)

**Databases Used**: PostgreSQL `users` table

**Agent Usage**: None (pure backend logic)

**LangGraph Usage**: None

**External Integrations**: None

**End-to-End Flow**:
1. Frontend `useCareerOS.login(email, password)` → `POST /auth/login`
2. Backend: email lookup → lockout check → password verify → JWT generate
3. Response: `{access_token, refresh_token}` + Set-Cookie headers
4. Frontend: stores token in `localStorage`, uses for subsequent API calls
5. Middleware: checks `careeros_token` cookie on protected routes

**Failure Handling**: 401 (invalid credentials), 423 (account locked), 400 (weak password)

**Observability**: Audit log entries for all auth events

---

### 1.2 Resume Upload & RAG Analysis

**What It Does**: Upload resume (PDF/DOCX/TXT), parse content, mask PII, chunk text, generate embeddings, index to Qdrant, and run LLM-powered intelligence evaluation.

**Why It Exists**: Core feature — the entire platform revolves around understanding the user's resume through RAG.

**Entry Point**: `POST /api/v1/knowledge/upload` then `POST /api/v1/knowledge/{doc_id}/analyze`

**Backend Routes**: `backend/src/api/v1/endpoints/knowledge.py`

**Services Used**:
- `services/processing/pipeline.py` — `ProcessingPipeline.run()` (orchestrates full pipeline)
- `services/processing/parser.py` — `DocumentParser` (PDF via PyMuPDF, DOCX, TXT)
- `services/privacy/engine.py` — `PrivacyEngine` (GLiNER + regex PII)
- `services/processing/chunking.py` — `ChunkingService` (LangChain text splitter)
- `services/processing/normalization.py` — `NormalizationService` (LLM entity extraction)
- `services/processing/versioning.py` — `VersioningService` (DB persistence)
- `services/embedding/embedding_service.py` — `EmbeddingService` (NV-Embed-v1)
- `services/embedding/orchestrator.py` — `EmbeddingOrchestrator` (embed → Qdrant store)
- `services/vector_store/qdrant_service.py` — `QdrantService` (upsert vectors)
- `services/intelligence/resume_analysis.py` — `ResumeAnalysisService` (LLM evaluation)

**Libraries Used**: `PyMuPDF`, `python-docx`, `langchain.text_splitter`, NV-Embed-v1 API, Qdrant client

**Databases Used**: PostgreSQL (`knowledge_docs`, `resume_versions`, `resume_chunks`), Qdrant (`careeros_resumes`)

**Agent Usage**: None (pipeline-based, not agent-based)

**LangGraph Usage**: None (background task via `asyncio.create_task`)

**External Integrations**: NVIDIA NV-Embed-v1 API (embeddings), Gemini 2.5 Flash (evaluation)

**End-to-End Flow**:
1. Frontend uploads file → `POST /knowledge/upload` → doc created in DB with status "indexed"
2. Frontend clicks "Analyze" → `POST /knowledge/{id}/analyze` → background task launched
3. Pipeline: PII masking → chunking → normalization → versioning → embedding → Qdrant indexing → LLM evaluation
4. Frontend polls `GET /knowledge/{id}/score` every 2.5s until `completion_pct = 100`
5. Results stored in `analysis_results` JSONB column

**Failure Handling**: Fallback scores (overall=78, ats=85, keyword=72, experience=80) if LLM fails. Mock embeddings if NVIDIA key absent.

**Observability**: Pipeline progress tracked in DB, LangSmith traces for LLM calls

---

### 1.3 Job Board Ingestion & Matching

**What It Does**: Ingests job listings from external sources, stores in PostgreSQL, embeds to Qdrant, and matches against user resumes.

**Why It Exists**: Provides the job opportunity data that drives the opportunity discovery and package generation features.

**Entry Point**: `POST /api/v1/jobs/refresh`

**Backend Routes**: `backend/src/api/v1/endpoints/jobs.py`

**Services Used**:
- `services/jobs.py` — `JobsService` (ingestion pipeline)
- `services/vector_store/qdrant_service.py` — `QdrantService` (job embedding)
- `services/embedding/embedding_service.py` — `EmbeddingService` (NV-Embed-v1)

**Libraries Used**: ARQ (Redis-backed task queue)

**Databases Used**: PostgreSQL (`jobs`, `job_matches`), Qdrant (`careeros_jobs`)

**Agent Usage**: None (worker-based pipeline)

**LangGraph Usage**: None

**External Integrations**: Job board APIs (configurable sources)

**End-to-End Flow**:
1. User clicks "Sync Jobs" → `POST /jobs/refresh` → ARQ job enqueued
2. Worker picks up `jobs_ingestion_pipeline` task
3. Pipeline: fetch jobs → parse → embed → upsert to Qdrant → compute match scores → store in DB
4. Frontend polls `GET /jobs` for results

**Failure Handling**: ARQ retry (3 attempts, 60s delay). Circuit breaker on embedding failures.

**Observability**: ARQ job status, structured logging

---

### 1.4 Opportunity Discovery

**What It Does**: 10-dimension weighted scoring pipeline that discovers, scores, prioritizes, and optionally notifies about high-match job opportunities.

**Why It Exists**: Demonstrates autonomous AI agent orchestration with governance, MCP tool calling, and explainability.

**Entry Point**: `POST /api/v1/opportunities/discover` or `POST /api/v1/orchestration/trigger`

**Backend Routes**: `backend/src/api/v1/endpoints/opportunities_api.py`, `backend/src/api/v1/endpoints/orchestration.py`

**Services Used**:
- `services/opportunity/opportunity_match_engine.py` — `OpportunityMatchEngine` (10-dimension scoring)
- `services/opportunity/market_signal_engine.py` — `MarketSignalEngine` (market signals)
- `services/opportunity/prioritization_engine.py` — `PrioritizationEngine` (ranking)
- `agents/opportunity_scoring_agent.py` — `OpportunityScoringAgent`
- `agents/opportunity_discovery_agent.py` — `OpportunityDiscoveryAgent`
- `agents/opportunity_prioritization_agent.py` — `OpportunityPrioritizationAgent`
- `agents/opportunity_alert_agent.py` — `OpportunityAlertAgent`
- `agents/notification_decision_agent.py` — `NotificationDecisionAgent`
- `agents/orchestration_governance_agent.py` — `OrchestrationGovernanceAgent`
- `agents/explainability_agent.py` — `ExplainabilityAgent`
- `agents/elevenlabs_voice_synthesis_agent.py` — `ElevenLabsVoiceSynthesisAgent`
- `agents/twilio_voice_agent.py` — `TwilioVoiceAgent`
- `services/mcp/mcp_router.py` — `MCPRouter` (tool dispatch)

**Libraries Used**: LangGraph (state machine), LangChain, MCP SDK

**Databases Used**: PostgreSQL (`orchestration_sessions`, `orchestration_events`, `autonomous_actions`, `governance_decisions`, `opportunity_scores`, `mcp_execution_logs`, `notification_history`, `job_matches`), Qdrant, Redis

**Agent Usage**: 11 registered core agents, plus service-level collaborators such as outcome intelligence

**LangGraph Usage**: `opportunity_graph` (12 nodes) or `career_os_graph` (6 nodes)

**External Integrations**: ElevenLabs (TTS), Twilio (telephony), Gemini (LLM scoring), Qdrant (vector search)

**End-to-End Flow**:
1. Trigger via API → LangGraph graph invoked with initial state
2. Context retrieval (Qdrant semantic search for resume, jobs, market signals)
3. 10-dimension scoring per opportunity
4. Priority ranking
5. Governance validation (confidence threshold, session cap)
6. Notification decision (should_notify, channel, urgency)
7. If triggered: MCP voice synthesis → Twilio call
8. Explainability trace compiled
9. All steps persisted to DB and LangSmith traces

**Failure Handling**: Retry policy (3 attempts, exponential backoff), governance suppression, graceful degradation to trace-only

**Observability**: LangSmith traces, Prometheus metrics, structured logging, governance decisions

---

### 1.5 Interview System (Voice + Text)

**What It Does**: AI-powered interview with real-time voice or text interaction, per-question evaluation, adaptive difficulty, career memory tracking, and comprehensive reports.

**Why It Exists**: Demonstrates real-time AI interaction via WebSocket, VAD, and adaptive difficulty.

**Entry Point**: `POST /api/v1/interview/start`

**Backend Routes**: `backend/src/api/v1/endpoints/interview.py`

**Services Used**:
- `services/interview/interview_orchestrator.py` — `InterviewOrchestrator` (session lifecycle)
- `services/interview/interview_governance.py` — `InterviewGovernance` (safety)
- `services/interview/interview_concurrency_service.py` — `InterviewConcurrencyService` (limits)
- `services/interview/interview_memory_service.py` — `InterviewMemoryService` (career memory)
- `services/interview/weakness_pattern_service.py` — `WeaknessPatternService` (longitudinal tracking)
- `services/interview/adaptive_difficulty_service.py` — `AdaptiveDifficultyService`
- `services/interview/live_evaluation.py` — `LiveEvaluation`
- `services/interview/realtime_feedback_service.py` — `RealtimeFeedbackService`
- `services/interview/` (24 files total)

**Libraries Used**: LangGraph (interview_graph), WebSocket, Deepgram (STT), ElevenLabs (TTS)

**Databases Used**: PostgreSQL (`interview_sessions`, `interview_questions`, `interview_weakness_history`), Redis (`interview:` prefix)

**Agent Usage**: Interview-related agents within interview services

**LangGraph Usage**: `interview_graph` (6 nodes: welcome → ask → listen → evaluate → follow_up → closing)

**External Integrations**: Deepgram (real-time STT), ElevenLabs (TTS), Gemini (question generation + evaluation)

**End-to-End Flow**:
1. `POST /interview/start` → session created, first question generated
2. WebSocket connection established (JWT auth via query param)
3. User speaks/types → transcript received
4. Safety check via `InterviewGovernance.check_message()`
5. Response evaluated (score, confidence, strengths, weaknesses)
6. Difficulty adapted based on confidence progression
7. Next question generated (or follow-up if score < 70)
8. Repeat until max questions (20) or session timeout (3600s)
9. Closing: final scores computed, weakness history updated
10. Report available via `GET /interview/report/{session_uid}`

**Failure Handling**: Governance kill (emergency stop), orphan cleanup (15 min), concurrency limits (50 max), retry (2 per operation)

**Observability**: LangSmith traces, structured logging, interview-specific metrics

---

### 1.6 Application Package Generation

**What It Does**: Generates 4 tailored assets (resume, cover letter, outreach messages, interview guide) via LLM for a specific job opportunity.

**Why It Exists**: Converts resume + job match intelligence into actionable application materials.

**Entry Point**: `POST /api/v1/packages/generate`

**Backend Routes**: `backend/src/api/v1/endpoints/packages.py`

**Services Used**:
- `services/packages.py` — `PackageService` (generation orchestration)
- LLM provider (Gemini 2.5 Flash → DeepSeek fallback)

**Libraries Used**: LLM API (direct HTTP calls via provider)

**Databases Used**: PostgreSQL (`generated_packages`, `package_versions`)

**Agent Usage**: None (LLM prompt-based generation)

**LangGraph Usage**: None (background task via `asyncio.create_task`)

**External Integrations**: Gemini 2.5 Flash (content generation)

**End-to-End Flow**:
1. User selects job → `POST /packages/generate {job_id}`
2. Package created with status "generating"
3. Background task generates 4 assets via LLM prompts:
   - Tailored Resume (Markdown: Summary, Skills, Experience, Education)
   - Cover Letter (3-4 paragraphs)
   - Outreach Messages (LinkedIn recruiter + Hiring manager email)
   - Interview Guide (5 technical + 3 behavioral questions)
4. Package status updated to "ready"
5. Frontend polls or refreshes to show results

**Failure Handling**: Status set to "failed" on error. Regeneration available via `POST /packages/{id}/regenerate`.

**Observability**: Structured logging, package status tracking

---

### 1.7 Career Roadmaps

**What It Does**: Generates career development roadmaps with goals, tasks, progress tracking, and velocity analytics.

**Why It Exists**: Provides long-term career planning beyond immediate job applications.

**Entry Point**: `POST /api/v1/roadmaps/generate`

**Backend Routes**: `backend/src/api/v1/endpoints/roadmaps.py`

**Services Used**:
- `services/strategy/roadmap_generation_service.py` — `RoadmapGenerationService`
- LLM provider for goal/task generation

**Databases Used**: PostgreSQL (`roadmaps`, `roadmap_goals`, `roadmap_tasks`)

**Agent Usage**: None (LLM-based generation)

**LangGraph Usage**: None

**External Integrations**: Gemini 2.5 Flash

**End-to-End Flow**:
1. User specifies target role → `POST /roadmaps/generate`
2. LLM generates 3 goals with 3 tasks each
3. Roadmap stored in DB with progress tracking
4. User toggles task completion → `PATCH /roadmaps/tasks/{task_id}`
5. Progress calculated as completed/total * 100

---

### 1.8 HITL Approval Center

**What It Does**: Human-in-the-loop review system for AI-generated content. Manages draft → approve/reject → execute lifecycle with comments and notifications.

**Why It Exists**: Provides governance control over AI-generated outreach messages and application content.

**Entry Point**: `GET /api/v1/approvals`

**Backend Routes**: `backend/src/api/v1/endpoints/approvals.py`

**Services Used**: Approval CRUD, notification, execution services

**Databases Used**: PostgreSQL (`approvals`, `approval_items`, `approval_comments`, `approval_notifications`)

**Agent Usage**: None (manual review workflow)

**LangGraph Usage**: None

**End-to-End Flow**:
1. AI generates content → approval created with status "pending"
2. User reviews in Approval Center
3. Actions: approve, reject (with reason), edit, execute
4. Execution marks as "delivered" with result
5. Notifications sent on status changes

---

### 1.9 Evaluation Platform

**What It Does**: Benchmarks for retrieval quality, reranker performance, prompt effectiveness, agent behavior, and hallucination detection.

**Why It Exists**: Provides quality assurance for AI pipeline outputs.

**Entry Point**: `POST /api/v1/eval/benchmark`

**Backend Routes**: `backend/src/api/v1/endpoints/evaluation.py`

**Services Used**:
- `services/evaluation/evaluation_engine.py` — `EvaluationEngine` (multi-metric)
- `services/intelligence/hallucination_guard.py` — `HallucinationGuard` (ML + heuristic)

**Databases Used**: PostgreSQL (`evaluation_runs`, `hallucination_audits`)

**Agent Usage**: None (evaluation engine)

**LangGraph Usage**: None

**End-to-End Flow**:
1. User triggers benchmark → `POST /eval/benchmark`
2. Evaluation engine runs 4 metrics: hallucination, grounding, relevance, retrieval quality
3. Results stored in `evaluation_runs`
4. Hallucination detection: ML guard (primary) + keyword heuristic (fallback)
5. Frontend polls progress via `GET /eval/runs/{id}/progress`

---

### 1.10 Readiness Scoring

**What It Does**: Multi-dimension dynamic scoring across 6 career readiness dimensions.

**Why It Exists**: Provides a single holistic score synthesizing all subsystem outputs.

**Entry Point**: `GET /api/v1/readiness/score`

**Backend Routes**: `backend/src/api/v1/endpoints/readiness.py`

**Services Used**:
- `services/readiness/readiness_engine.py` — `ReadinessEngine`
- `services/strategy/` (16 strategy services)

**Databases Used**: All subsystem tables (resumes, jobs, interviews, opportunities, roadmaps)

**Agent Usage**: Strategy services act as specialized agents

**LangGraph Usage**: None

**6 Dimensions**: Resume Quality, Skill Readiness, Interview Performance, Market Alignment, Opportunity Discovery, Career Progress

---

### 1.11 Rerank Monitoring

**What It Does**: Monitors and visualizes the enterprise reranker's health, performance, and fallback behavior.

**Why It Exists**: Provides operational visibility into retrieval quality.

**Entry Point**: `POST /api/v1/rerank` (execute) or `GET /api/v1/rerank/stats`

**Backend Routes**: `backend/src/api/v1/endpoints/rerank.py`

**Services Used**:
- `services/reranking/rerank_pipeline.py` — `RerankPipeline`
- `services/retrieval/reranker_service.py` — `RerankerService`

**Databases Used**: PostgreSQL (`rerank_runs`), Redis (rerank cache, 30min TTL)

**Agent Usage**: None

**LangGraph Usage**: None

---

### 1.12 Operations Center

**What It Does**: System health dashboard with health checks, circuit breaker inspection, audit logs, and DR simulation.

**Why It Exists**: Provides operational control for admin users.

**Entry Point**: `GET /api/v1/troubleshoot/circuits`

**Backend Routes**: `backend/src/api/v1/endpoints/troubleshoot.py`, `backend/src/api/health.py`

**Services Used**:
- `services/security/auth.py` (circuit breaker state)
- `services/security/audit.py` (audit logs)
- Health check services (DB, Redis, Qdrant, Storage)

**Databases Used**: PostgreSQL (`circuit_states`, `audit_logs`, `pending_jobs`)

**Agent Usage**: None

**LangGraph Usage**: None

---

## 2. Frontend Page-by-Page Reference

### `/` — Landing Page
- **Route**: `frontend/src/app/page.tsx`
- **Components**: Redirects to `/login` or `/dashboard` based on auth state
- **API calls**: None (client-side redirect)
- **Purpose**: Entry point, auto-redirects

### `/login` — Authentication
- **Route**: `frontend/src/app/login/page.tsx`
- **Components**: `LoginView` (login/register tabs with demo autofill)
- **API calls**: `POST /auth/login`, `POST /auth/register`
- **Backend**: `auth.py` router
- **Purpose**: User authentication

### `/forgot-password` — Password Reset Request
- **Route**: `frontend/src/app/forgot-password/page.tsx`
- **API calls**: `POST /auth/forgot-password`
- **Purpose**: Initiate password reset (token returned in debug mode)

### `/reset-password` — Password Reset
- **Route**: `frontend/src/app/reset-password/page.tsx`
- **API calls**: `POST /auth/reset-password`
- **Purpose**: Complete password reset with token

### `/dashboard` — RAG Analysis Dashboard
- **Route**: `frontend/src/app/dashboard/page.tsx`
- **Hook**: `useCareerOS()`
- **Components**: `DashboardView` (resume-JD match, strengths/gaps, trace)
- **API calls**: `GET /knowledge`, `GET /knowledge/{id}`, `POST /knowledge/{id}/analyze`, `GET /knowledge/{id}/score`
- **Backend**: `knowledge.py` router
- **Databases**: PostgreSQL (`knowledge_docs`), Qdrant (`careeros_resumes`)
- **Purpose**: View resume analysis results, trigger RAG pipeline

### `/knowledge` — Knowledge Hub
- **Route**: `frontend/src/app/knowledge/page.tsx`
- **Hook**: `useCareerOS()`
- **Components**: `KnowledgeHub` (drag-drop upload, paste text, PII modal)
- **API calls**: `POST /knowledge/upload`, `GET /knowledge`, `DELETE /knowledge/{id}`
- **Backend**: `knowledge.py` router
- **Databases**: PostgreSQL (`knowledge_docs`)
- **Purpose**: Upload and manage resume documents

### `/jobs` — Job Intelligence
- **Route**: `frontend/src/app/jobs/page.tsx`
- **Hook**: `useCareerOS()`
- **Components**: `JobsIntelligenceView` (job board list, filtering, sync)
- **API calls**: `GET /jobs`, `GET /jobs/stats`, `POST /jobs/refresh`
- **Backend**: `jobs.py` router
- **Databases**: PostgreSQL (`jobs`, `job_matches`), Qdrant (`careeros_jobs`)
- **Purpose**: Browse and sync job listings

### `/opportunities` — Opportunity Discovery
- **Route**: `frontend/src/app/opportunities/page.tsx`
- **Components**: `OpportunityCenterView` (discovery pipeline, dimension scores)
- **API calls**: `POST /opportunities/discover`, `GET /opportunities/list`
- **Backend**: `opportunities_api.py` router
- **Databases**: PostgreSQL (`job_matches`, `opportunity_scores`)
- **Purpose**: Discover and score matching opportunities

### `/packages` — Application Packages
- **Route**: `frontend/src/app/packages/page.tsx`
- **Components**: `ApplicationPackagesView` (package list, content tabs, download)
- **API calls**: `GET /packages`, `POST /packages/generate`, `DELETE /packages/{id}`, `GET /packages/{id}/download`
- **Backend**: `packages.py` router
- **Databases**: PostgreSQL (`generated_packages`, `package_versions`)
- **Purpose**: Generate and download tailored application materials

### `/interview` — Voice Interview
- **Route**: `frontend/src/app/interview/page.tsx`
- **Components**: `AudioPermissionGate`, `InterviewControlBar`, `LiveTranscript`, `VoiceVisualizer`
- **Hooks**: `useInterviewWebSocket`, `useMicrophone`, `useVoiceActivityDetection`
- **API calls**: `POST /interview/start`, WebSocket audio/text
- **Backend**: `interview.py` router, `realtime.py` WebSocket
- **Databases**: PostgreSQL (`interview_sessions`, `interview_questions`), Redis (`interview:`)
- **Purpose**: Real-time voice interview with AI

### `/coach` — Text Interview Coach
- **Route**: `frontend/src/app/coach/page.tsx`
- **Components**: `CareerCoachDashboard`, `InterviewCoachView`
- **API calls**: `POST /interview/start`, `POST /interview/respond`, `GET /interview/report/{id}`, `GET /interview/history`, `GET /interview/memory`
- **Backend**: `interview.py` router
- **Databases**: PostgreSQL (`interview_sessions`, `interview_questions`, `interview_weakness_history`)
- **Purpose**: Text-based interview practice with career memory

### `/roadmap` — Career Roadmap
- **Route**: `frontend/src/app/roadmap/page.tsx`
- **Components**: `CareerRoadmapView` (goals, tasks, progress analytics)
- **API calls**: `GET /roadmaps`, `POST /roadmaps/generate`, `PATCH /roadmaps/tasks/{id}`, `GET /roadmaps/progress`
- **Backend**: `roadmaps.py` router
- **Databases**: PostgreSQL (`roadmaps`, `roadmap_goals`, `roadmap_tasks`)
- **Purpose**: Career development planning

### `/approvals` — HITL Approval Center
- **Route**: `frontend/src/app/approvals/page.tsx`
- **Components**: `HumanApprovalCenterView` (queue, approve/reject/execute, comments)
- **API calls**: `GET /approvals`, `POST /approvals/{id}/approve`, `POST /approvals/{id}/reject`, `POST /approvals/{id}/execute`, `POST /approvals/{id}/comment`
- **Backend**: `approvals.py` router
- **Databases**: PostgreSQL (`approvals`, `approval_items`, `approval_comments`, `approval_notifications`)
- **Purpose**: Review and manage AI-generated content

### `/evaluation` — Evaluation Platform
- **Route**: `frontend/src/app/evaluation/page.tsx`
- **Components**: `EvaluationView` (benchmarks, hallucination playground)
- **API calls**: `GET /eval/runs`, `POST /eval/benchmark`, `POST /eval/hallucination/detect`, `GET /eval/runs/{id}/progress`
- **Backend**: `evaluation.py` router
- **Databases**: PostgreSQL (`evaluation_runs`, `hallucination_audits`)
- **Purpose**: Quality assurance for AI outputs

### `/orchestration` — Orchestration Dashboard
- **Route**: `frontend/src/app/orchestration/page.tsx`
- **API calls**: `POST /orchestration/trigger`, `GET /orchestration/history`, `GET /orchestration/status/{id}`, `GET /orchestration/health`
- **Backend**: `orchestration.py` router
- **Databases**: PostgreSQL (`orchestration_sessions`, `orchestration_events`)
- **Purpose**: Manage and monitor LangGraph orchestration

### `/orchestration/live` — Live Pipeline
- **Route**: `frontend/src/app/orchestration/live/page.tsx`
- **API calls**: `GET /orchestration/history` (polled every 5s)
- **Purpose**: Real-time pipeline visualization

### `/orchestration/history` — Session History
- **Route**: `frontend/src/app/orchestration/history/page.tsx`
- **API calls**: `GET /orchestration/history?limit=100`
- **Purpose**: Browse orchestration session history

### `/orchestration/governance` — Governance
- **Route**: `frontend/src/app/orchestration/governance/page.tsx`
- **API calls**: `GET /orchestration/governance/decisions`, `GET /orchestration/governance/stats`
- **Purpose**: View governance rules and decision history

### `/orchestration/traces` — Explainability Traces
- **Route**: `frontend/src/app/orchestration/traces/page.tsx`
- **API calls**: `GET /orchestration/traces`
- **Purpose**: View explainability traces for AI decisions

### `/ops` — Operations Center
- **Route**: `frontend/src/app/ops/page.tsx`
- **Components**: `OpsCenterView` (health, circuits, DR simulation)
- **API calls**: `GET /health/detailed`, `GET /troubleshoot/circuits`, `GET /troubleshoot/audit`
- **Backend**: `troubleshoot.py`, `health.py` routers
- **Databases**: PostgreSQL (`circuit_states`, `audit_logs`, `pending_jobs`)
- **Purpose**: System health and operations

### `/command-center` — Command Center
- **Route**: `frontend/src/app/command-center/page.tsx`
- **Components**: `CommandCenterView` (readiness score, agent activity, demo mode)
- **API calls**: `GET /readiness/score`, `GET /readiness/timeline`, `GET /readiness/explain`, `GET /agents/status`
- **Backend**: `readiness.py`, `agents.py` routers
- **Purpose**: Holistic career readiness overview

### `/preferences` — User Preferences
- **Route**: `frontend/src/app/preferences/page.tsx`
- **Hook**: `useCareerOS()`
- **Components**: `PreferencesPanel` (alert thresholds, quiet hours, theme)
- **API calls**: `GET /user/preferences`, `PUT /user/preferences`
- **Backend**: `preferences.py` router
- **Databases**: PostgreSQL (`user_preferences`)
- **Purpose**: User settings management

### `/rerank` — Reranker Monitoring
- **Route**: `frontend/src/app/rerank/page.tsx`
- **Components**: `RerankMonitoringDashboard` (health, stats, history)
- **API calls**: `POST /rerank`, `GET /rerank/health`, `GET /rerank/stats`, `GET /rerank/history`
- **Backend**: `rerank.py` router
- **Databases**: PostgreSQL (`rerank_runs`)
- **Purpose**: Monitor reranker performance
