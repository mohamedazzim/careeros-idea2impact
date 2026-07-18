# CareerOS V2 Current Architecture

Last verified from source code: 2026-06-19

This document describes the current, real CareerOS implementation as of this repo snapshot. It is intentionally conservative: if a behavior is not directly backed by code, it is labeled as a gap or a fallback.

## Executive Summary

CareerOS is already a multi-domain platform built around:

- A FastAPI backend with async SQLAlchemy and domain routers.
- A Next.js App Router frontend with shared shell, route pages, and reusable panels.
- PostgreSQL for durable state, Redis for cache/queues/locks, and Qdrant for vector retrieval.
- External provider integrations for TheirStack, GitHub, YouTube, web search, Twilio, ElevenLabs, and LLM providers behind a fallback layer.
- A growing outcome-intelligence layer that stores conversations, voice sessions, application events, roadmap state, and learning artifacts.

The current architecture is not a blank slate. It already contains:

- Job discovery and refresh.
- Opportunity delivery and voice-call orchestration.
- Learning resource discovery and skill-path generation.
- Roadmap generation and progress aggregation.
- Docs-RAG question answering over `docs/rag/`.
- Observability, governance, and provider health surfaces.

The V2 work is mainly about making the existing system more evidence-driven, more explainable, and less dependent on default or heuristic values.

## Backend Architecture

### App bootstrap

The FastAPI application lives in [`backend/src/main.py`](../../backend/src/main.py).

Key characteristics:

- Async-first FastAPI app.
- Routers mounted under both `/api` and `/api/v1`.
- Structured logging and observability middleware.
- CORS, security headers, and rate-limit handling.
- Startup health checks for core runtime dependencies.
- Qdrant collection initialization at startup.
- ARQ pool shutdown on application exit.

### Router layout

The current router surface is broad and domain-oriented:

- Auth and session management.
- Resume upload, retrieval, retry, lifecycle, and shared endpoints.
- Knowledge Hub upload, analysis, scoring, and alignment reporting.
- Jobs refresh, stats, alerts, applications, provider health, and phase-2 dashboard views.
- Opportunities discovery, timeline, outcome recording, and lifecycle runs.
- Learning skill gaps, learning paths, gap actions, and GitHub projects.
- Roadmaps generation, regeneration, task updates, and progress aggregation.
- Outcome intelligence and autonomous engagement views.
- Docs RAG endpoints for mentor/HR questions.

### Core backend service layers

The main service boundaries visible in code are:

| Layer | Examples | What it does |
|---|---|---|
| Foundation | `services/llm/`, `services/embedding/`, `services/vector_store/`, `services/security/`, `services/mcp/` | Provider abstraction, embeddings, Qdrant, auth, redaction, MCP governance |
| Retrieval | `services/retrieval/`, `services/context/` | Hybrid retrieval, ranking, context assembly, deduplication |
| Resume intelligence | `services/resume/processing/*`, `services/intelligence/resume_analysis_service.py` | Parse, chunk, embed, index, and analyze resumes |
| Jobs and opportunity | `services/jobs.py`, `services/job_refresh.py`, `services/opportunity/*` | Job ingestion, matching, alerting, voice delivery, outcome capture |
| Learning | `services/learning/*`, `integrations/learning/*`, `integrations/github/*`, `integrations/youtube/*` | Resource discovery, skill paths, GitHub project discovery, trust scoring |
| Strategy and roadmap | `services/strategy/*`, `api/v1/endpoints/roadmaps.py` | Roadmap generation, priority logic, milestone planning, progress reporting |
| Outcome intelligence | `services/intelligence/career_coach_service.py`, `services/opportunity/outcome_intelligence.py` | Candidate memory, goals, recommendations, funnel/outcome aggregation |
| RAG | `services/rag/service.py`, `api/v1/endpoints/demo_rag.py` | Markdown-doc indexing, retrieval, answer generation, optional Make relay |
| Runtime/eventing | `runtime/events/event_bus.py`, `runtime/workers/*`, `workers/*` | Redis streams/pubsub, orchestration dispatch, worker processing |

### Data stores

| Store | Real purpose in current code |
|---|---|
| PostgreSQL | Users, resumes, jobs, matches, learning resources, roadmaps, communications, outcomes, orchestration, knowledge docs, interview state, reports |
| Redis | Cache, locks, queues, worker coordination, provider throttling, session-like runtime state |
| Qdrant | Resume/job/knowledge vectors and docs-RAG vectors |

### LLM and embedding flow

Current code uses:

- `FallbackProvider` for LLM access.
- Gemini 2.5 Flash as primary provider.
- DeepSeek as fallback provider.
- Embedding services for resume and docs-RAG vectorization.

The architecture is already provider-agnostic at the service layer, but many outputs are still heuristic or defaulted when evidence is missing.

### Governance and observability

Current observability and safety pieces include:

- LangSmith tracing with circuit-breaker behavior.
- OpenTelemetry-style observability middleware.
- Structured JSON logging.
- PII redaction utilities.
- Prompt-injection detection helpers.
- MCP governance for Twilio and ElevenLabs calls.
- Rate limiting and auth enforcement.

## Frontend Architecture

The frontend is a Next.js App Router application in [`frontend/src/app`](../../frontend/src/app).

### UI shell

The root layout [`frontend/src/app/layout.tsx`](../../frontend/src/app/layout.tsx) mounts:

- `AppShell`
- global `FloatingRagChatbot`
- page-level suspense loading
- error boundary

### Shared frontend patterns

The frontend uses:

- `useCareerOS()` for main app state and authenticated data fetching.
- `useRBAC()` for role-aware UI behavior.
- `useWebSocket()` for live interview / streaming experiences.
- `resilientFetch()` for retry-safe network behavior.
- `auth-session.ts` helpers for token and cookie handling.

### Current route surface

The app already has dedicated pages for:

- Dashboard
- Jobs
- Job library
- Opportunities
- Roadmap
- Coach
- Command center
- Approvals
- Interview
- Knowledge
- Packages
- Evaluation
- Preferences
- Rerank monitoring
- Orchestration history / live / traces / governance
- Demo RAG

### Frontend component map

Important reusable components include:

- `JobsIntelligenceView`
- `CareerRoadmapView`
- `CareerCoachDashboard`
- `OpportunityCenterView`
- `CommandCenterView`
- `InterviewCoachView`
- `KnowledgeHub`
- `RerankMonitoringDashboard`
- `FloatingRagChatbot` and its subcomponents
- learning panels for paths, GitHub projects, and gap actions

## Current External Providers

### Job and opportunity data

- TheirStack for job discovery / sync.
- Internal matching and ranking logic over jobs and resumes.

### Learning resource discovery

- GitHub Search API for repositories and issues.
- YouTube Data API for channel/video discovery.
- Bing, Tavily, or SerpAPI for web search, depending on configuration.
- Seeded curated learning resources as verified fallback.

### Voice / outbound communication

- Twilio for voice/SMS delivery and health checks.
- ElevenLabs for conversational voice-agent support.
- MCP governance layer sits between backend and provider calls.

### Knowledge and copilot UX

- Docs-RAG indexes `docs/rag/*.md` into Qdrant.
- Optional Make webhook relay can answer from retrieved docs before falling back to local generation.

## Current High-Value Flows

### Learning resource flow

The current learning stack is already evidence-aware:

1. Skill gaps are derived from jobs and matches.
2. Seeded learning resources are loaded from trusted markdown seed data.
3. Live discovery can augment the seed set.
4. Resources are ranked by trust, relevance, freshness, and verification time.
5. Learning paths and gap actions are generated from the selected resources.

### GitHub project flow

GitHub project discovery uses public search plus optional auth:

- Repository search for templates/starter projects/examples.
- Issue search for `good first issue` / `help wanted`.
- Ranking based on stars, template signals, and archived penalties.

This is useful for finding real project ideas, but it does not prove repository quality or outcome success by itself.

### Roadmap/progress flow

Roadmaps are stored and rendered from durable task data. Progress is currently aggregated from stored tasks and related data rather than from a separate autonomous recalculation service.

The current API and UI now distinguish:

- real stored task completion
- missing telemetry
- `not_tracked` diagnostics

### Opportunity / voice flow

Opportunity delivery uses:

- alert decision services
- communication orchestration
- duplicate suppression and delivery locks
- voice provider wrappers
- transcript sync and outcome capture

The current model is already closer to a governed delivery system than a simple notification sender.

## Current Gaps

The architecture is functional, but the V2 target still needs:

- Better evidence provenance for scores and recommendations.
- More real activity tracking before analytics can be trusted.
- More explicit `insufficient_data` responses when evidence is missing.
- Stronger distinction between live provider data and seeded fallback data.
- Clearer trust semantics for curated web / YouTube / GitHub discovery.
- More durable outcome tracking before personalization can be called predictive.

## What This Architecture Already Supports

The current codebase can already support a V2 platform that is:

- evidence-backed
- explainable
- multi-modal
- integration-heavy
- workflow-aware
- operable with live provider health

The main work for V2 is not invention from scratch. It is tightening the provenance, fidelity, and analytics layers around capabilities that already exist.
