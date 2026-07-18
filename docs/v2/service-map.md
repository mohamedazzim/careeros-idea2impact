# CareerOS V2 Service Map

Last verified from source code: 2026-06-20

This document maps the current service modules to the business capabilities they power.

## Backend service layers

### Foundation services

| Service | Purpose | Key dependencies | Notes |
|---|---|---|---|
| `services/llm/fallback_provider.py` | Unified LLM access with fallback behavior | Gemini provider, DeepSeek provider | Critical guardrail: no direct provider bypass in normal flows |
| `services/embedding/embedding_service.py` | Embedding generation and batching | Model-specific embedding backends | Used by resume and docs-RAG indexing |
| `services/vector_store/qdrant_service.py` | Collection lifecycle, schema, upsert, query | Qdrant client | Shared vector store abstraction |
| `services/security/auth.py` | Auth and token helpers | JWT, password hashing, cookies | Must remain untouched in V2 planning |
| `services/security/ai_security.py` | PII redaction and prompt-injection guards | Regex / GLiNER helpers | Used before logging and before RAG interactions |
| `services/mcp/mcp_router.py` | Governance gateway for MCP calls | Twilio / ElevenLabs services | Enforces routing and guardrails |

### Retrieval and context

| Service | Purpose | What it consumes | What it produces |
|---|---|---|---|
| `services/retrieval/hybrid_retrieval_service.py` | Combined retrieval over sparse + semantic signals | Queries, vectors, payloads | Ranked context candidates |
| `services/retrieval/context_builder.py` | Build model-ready context blocks | Retrieval hits, query metadata | Structured context text |
| `services/context/context_assembly_service.py` | Assemble Claude-ready context | Resume/job/knowledge evidence | Prompt context payload |
| `services/context/context_compression_service.py` | Reduce context size | Long multi-source context | Shorter prompt-safe context |

### Resume and document intelligence

| Service | Purpose | Real data source |
|---|---|---|
| `services/resume/upload_service.py` | Upload and persist resume artifacts | `resumes`, storage backend |
| `services/resume/processing/*` | Parse, normalize, chunk, OCR, mask, and embed resumes | `resumes`, `resume_versions`, `resume_chunks` |
| `services/resume/retrieval_service.py` | Retrieve resume content | DB and Qdrant |
| `services/intelligence/resume_analysis_service.py` | Resume scoring and explanation | Resume chunks, role signals, evidence |
| `services/knowledge` endpoint/service path | Knowledge Hub upload and analysis | `knowledge_docs` |

### Jobs, matches, and opportunity intelligence

| Service | Purpose | Real data source |
|---|---|---|
| `services/jobs.py` | Job list, refresh, stats, provider health | `jobs`, `job_matches`, provider data |
| `services/job_refresh.py` | Ingest and reconcile job refreshes | TheirStack / local DB |
| `services/job_refresh_diagnostics.py` | Explain refresh results | Job refresh payloads, stale detection |
| `services/opportunity/opportunity_match_engine.py` | Opportunity scoring and matching | Jobs, resumes, preferences, signals |
| `services/opportunity/alert_action_service.py` | Trigger delivery decisions | Match results, governance, communication requests |
| `services/opportunity/communication_orchestrator.py` | Deliver alert actions and enforce duplicate suppression | `communication_requests`, locks, provider adapters |
| `services/opportunity/conversational_outbound_call_service.py` | Build conversational outbound call payloads | Opportunity context, dynamic variables |
| `services/opportunity/voice_providers.py` | Provider-specific voice delivery wrappers | Twilio / ElevenLabs |
| `services/opportunity/elevenlabs_transcript_sync.py` | Sync provider transcripts | Voice session state, provider payloads |
| `services/opportunity/outcome_intelligence.py` | Aggregate outcomes and funnel metrics | Communications, sessions, outcomes tables |
| `services/opportunity/career_memory.py` | Create memory records from activity | Job and opportunity events |
| `services/opportunity/career_progress_agent.py` | Build progress summaries | Stored lifecycle and outcome data |

### Learning intelligence

| Service | Purpose | Real data source |
|---|---|---|
| `services/learning/learning_resource_service.py` | Load seed resources, augment with live discovery, rank by trust | `learning_resources`, provider discovery |
| `services/learning/learning_path_service.py` | Build learning paths from skill gaps | `JobMatch`, `Job`, `learning_resources` |
| `services/learning/gap_action_service.py` | Turn skill gaps into action plans and project ideas | Learning resources, provider health |
| `services/learning/learning_outcome_service.py` | Track opens, progress, completion, abandonment, feedback, and outcome aggregates | `learning_sessions`, `resource_feedback`, `resource_outcomes`, `learning_activity_events`, `career_events` |
| `services/learning/github_project_service.py` | Discover GitHub project ideas from skill gaps | GitHub search, cache, skill gaps |
| `services/learning/skill_normalizer.py` | Normalize skill names | Query and provider input |

### Skill graph and import strategy

| Service | Purpose | Real data source |
|---|---|---|
| `services/skill_graph/skill_graph_service.py` | Aggregate the canonical skill graph from evidence-backed user and system signals | Jobs, learning resources, resumes, roadmaps, import runs |
| `api/v1/endpoints/skill_graph.py` | Authenticated skill graph inspection and import API | Skill graph tables and import service |

### Skill gap analysis

| Service | Purpose | Real data source |
|---|---|---|
| `services/skill_gap/skill_gap_engine.py` | Evidence-backed skill gap analysis runs, findings, and snapshots | Jobs, resumes, learning outcomes, roadmap tasks, skill graph evidence |
| `services/skill_gap/skill_gap_query_service.py` | Read-only retrieval for past runs, findings, evidence, and snapshots | Skill gap tables |
| `services/skill_gap/skill_gap_evidence_service.py` | Collect evidence for required and missing skills | Job requirements, user skills, learning signals, provenance |
| `services/skill_gap/skill_gap_explanation_service.py` | Human-readable gap explanations and next actions | Requirement type, evidence payloads, missing evidence |
| `api/v1/endpoints/skill_gaps.py` | Authenticated skill gap API | Skill gap tables and analysis service |

### Strategy and roadmap

| Service | Purpose | Real data source |
|---|---|---|
| `services/strategy/roadmap_generation_service.py` | Generate roadmap objects and tasks | Resume, jobs, skill gaps, evidence |
| `services/strategy/learning_path_service.py` | Produce skill learning paths | Skill gaps + resources |
| `services/strategy/milestone_planning_service.py` | Break work into milestones | Evidence and capability inputs |
| `services/strategy/recruiter_visibility_service.py` | Explain recruiter-facing presentation | Resume, project, and job signals |
| `services/intelligence/career_coach_service.py` | Build coach plans, goals, recommendations | Career memory, lifecycle, progress metrics |

### RAG and docs intelligence

| Service | Purpose | Current behavior |
|---|---|---|
| `services/rag/service.py` | Index and answer questions from `docs/rag/` | Chunk docs, embed, store in `careeros_rag_docs`, retrieve and answer |
| `api/v1/endpoints/demo_rag.py` | Public API for docs-RAG | Chat, index, health, golden questions |
| `services/vector_store/qdrant_service.py` | Qdrant collection support for RAG | Enforces payload schema and collection setup |

### Observability and control-plane services

| Service | Purpose | Real data source |
|---|---|---|
| `services/intelligence/intelligence_metrics.py` | Metrics and scoring telemetry | Runtime events and cached counters |
| `services/intelligence/intelligence_observability.py` | Observation hooks | Service execution traces |
| `observability/langsmith/*` | Tracing and circuit breaker | LangSmith env + runtime state |
| `observability/middleware.py` | Request-level observability | FastAPI requests |
| `runtime/events/event_bus.py` | Redis streams, replay, dead letters | Redis |
| `runtime/workers/orchestration_dispatcher.py` | Deduped dispatch for orchestration tasks | Redis locks / keys |

## Frontend service / component map

### App and shell

| Frontend module | Purpose |
|---|---|
| `frontend/src/app/layout.tsx` | Root shell, global chatbot, suspense, error boundary |
| `frontend/src/components/AppShell.tsx` | App framing and nav |
| `frontend/src/components/Navigation.tsx` | Main navigation and logout/session controls |
| `frontend/src/components/ErrorBoundary.tsx` | Frontend error containment |

### Data fetching and auth helpers

| Frontend module | Purpose |
|---|---|
| `frontend/src/hooks/useCareerOS.ts` | Main authenticated app hook |
| `frontend/src/hooks/useRBAC.ts` | Role-aware UI gating |
| `frontend/src/hooks/useWebSocket.ts` | Live streaming / interview socket integration |
| `frontend/src/lib/resilience.ts` | Retry-safe fetch helpers |
| `frontend/src/lib/auth-session.ts` | Auth token / cookie helpers |
| `frontend/src/lib/demo-rag.ts` | Docs-RAG chat client and session helper |

### Domain views

| Frontend module | Purpose |
|---|---|
| `frontend/src/components/DashboardView.tsx` | Summary dashboard |
| `frontend/src/components/JobsIntelligenceView.tsx` | Job analysis and refresh diagnostics |
| `frontend/src/components/CareerRoadmapView.tsx` | Roadmap and progress UI |
| `frontend/src/components/CareerCoachDashboard.tsx` | Coach / recommendation UI |
| `frontend/src/components/OpportunityCenterView.tsx` | Opportunity pipeline view |
| `frontend/src/components/CommandCenterView.tsx` | Command / operations surface |
| `frontend/src/components/KnowledgeHub.tsx` | Knowledge documents UI |
| `frontend/src/components/InterviewCoachView.tsx` | Interview coaching and streaming UX |
| `frontend/src/components/RerankMonitoringDashboard.tsx` | Ranking observability |
| `frontend/src/components/SkillGraphView.tsx` | Skill graph inspection and import dashboard |
| `frontend/src/components/rag/*` | Floating docs-RAG chatbot |
| `frontend/src/components/learning/*` | Learning path, GitHub project, and gap action panels |

## Dependency map

### Key backend dependencies

1. Most domain services depend on Postgres and one or more model files.
2. Retrieval services depend on Qdrant plus embeddings.
3. Learning services depend on provider health, web search configuration, GitHub and YouTube integrations, and seeded fallback resources.
4. Opportunity delivery depends on governance, duplicate suppression, Twilio/ElevenLabs wrappers, and transcript sync.
5. Analytics services depend on stored events and outcome tables.

### Key frontend dependencies

1. Most views depend on auth state from `careeros_token`.
2. Shared shell and navigation are mounted globally.
3. Docs-RAG chatbot is mounted globally in the root layout.
4. Interview UX depends on websocket and audio helpers.

## Service-map takeaways for V2

- The codebase already has most of the services needed for a production-grade Career Intelligence platform.
- The main missing piece is not another blank layer; it is better evidence, better event history, and more honest fallback/insufficient-data semantics.
- The next V2 services should extend these modules rather than replace them.
