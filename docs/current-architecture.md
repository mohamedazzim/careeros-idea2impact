# CareerOS Current Architecture Snapshot

Last verified from source code: 2026-06-19

## Scope

This document describes the current implemented CareerOS architecture as it exists in source code today. It does not describe the aspirational phase list from the request unless a capability is actually implemented.

Source of truth:

- backend source code
- frontend source code
- retained public architecture and operations documentation

## 1. Top-level platform shape

CareerOS is a full-stack career intelligence platform with these major runtime layers:

- **Frontend**: Next.js App Router + React + TypeScript
- **Backend**: FastAPI + SQLAlchemy async + Pydantic
- **Async jobs**: ARQ worker on Redis
- **Primary DB**: PostgreSQL
- **Cache / queue / event transport**: Redis
- **Vector retrieval**: Qdrant
- **Observability**: structured logs, Prometheus, LangSmith integration, tracing middleware
- **AI/LLM**: Gemini primary with fallback provider behavior in the backend

## 2. Current domain areas

The implemented product currently centers on these user-facing domains:

| Domain | What it does today | Key source paths |
|---|---|---|
| Auth / session management | Login, register, JWT cookie auth, role checks | `backend/src/api/v1/endpoints/auth.py`, `backend/src/api/deps.py`, `frontend/src/middleware.ts`, `frontend/src/hooks/useCareerOS.ts` |
| Resume / knowledge ingestion | Upload, parse, analyze, vectorize, score | `backend/src/api/v1/endpoints/knowledge.py`, `backend/src/services/resume/*`, `backend/src/services/vector_store/*` |
| Jobs intelligence | Job refresh, stats, matching, filters | `backend/src/api/v1/endpoints/jobs.py`, `backend/src/services/jobs.py`, `frontend/src/components/JobsIntelligenceView.tsx` |
| Learning resources | Seeded + live learning discovery, verified learning paths | `backend/src/services/learning/*`, `backend/src/integrations/learning/*`, `frontend/src/components/learning/*` |
| GitHub projects | Public repo and issue discovery for missing skills | `backend/src/integrations/github/repo_discovery.py`, `backend/src/services/learning/github_project_service.py` |
| Skill graph | Evidence-backed skill nodes, aliases, edges, import runs, and user states | `backend/src/models/skill_graph.py`, `backend/src/services/skill_graph/skill_graph_service.py`, `frontend/src/components/SkillGraphView.tsx` |
| Roadmaps | Roadmap generation, tasks, progress, telemetry | `backend/src/api/v1/endpoints/roadmaps.py`, `frontend/src/components/CareerRoadmapView.tsx` |
| Opportunity intelligence | Discovery, scoring, notifications, outcome tracking | `backend/src/services/opportunity/*`, `backend/src/api/v1/endpoints/opportunities_api.py` |
| Outcome intelligence | Post-call outcomes, funnel metrics, reranking | `backend/src/services/opportunity/outcome_intelligence.py`, `backend/src/api/v1/endpoints/outcome_intelligence.py` |
| Orchestration | LangGraph / event / governance runtime | `backend/src/api/v1/endpoints/orchestration.py`, `backend/src/runtime/*`, `backend/src/services/orchestration/*` |
| Interview surfaces | Voice interview and text coach | `backend/src/api/v1/endpoints/interview.py`, `frontend/src/components/InterviewCoachView.tsx` |
| Approvals / HITL | Approval queue and execution | `backend/src/api/v1/endpoints/approvals.py`, `frontend/src/components/HumanApprovalCenterView.tsx` |
| Observability / ops | Health, metrics, traces, circuits | `backend/src/api/v1/endpoints/observability.py`, `backend/src/api/v1/endpoints/troubleshoot.py`, `frontend/src/components/OpsCenterView.tsx` |

## 3. Backend bootstrap and router wiring

`backend/src/main.py` wires the app together:

- builds the FastAPI app
- applies CORS and security middleware
- initializes Qdrant collections at startup
- registers routers under `/api` and `/api/v1`
- closes ARQ and MCP resources on shutdown

Current router registration includes:

- auth
- knowledge
- jobs
- interview
- packages
- readiness
- agents
- mcp
- observability
- approvals
- roadmaps
- evaluation
- preferences
- troubleshoot
- rerank
- opportunities
- opportunity alert
- demo RAG
- learning
- outcome intelligence
- autonomous engagement
- phase 6
- health

## 4. Learning and GitHub discovery architecture

The current learning stack is real and explainable:

- skill gaps are derived from job matches and job extraction
- skills are normalized before any discovery query
- learning resources are seeded first, then optionally enriched with live providers
- providers include YouTube, web search, Coursera, and Udemy, depending on config
- GitHub project discovery uses the public GitHub Search API for repositories and issues

This architecture is intentionally heuristic-driven:

- trust score
- relevance score
- freshness score
- verification status
- price/free status

Those signals are stored and re-sorted later. They are not fabricated dashboards.

## 5. Opportunity intelligence architecture

The opportunity system currently includes:

- job discovery and scoring
- notification selection
- voice session creation
- outcome persistence
- follow-up task planning
- reranking based on memory/outcome signals

Current persistence spans both the `models/jobs.py` and `models/outcome_intelligence.py` domains.

## 6. Event and replay architecture

The runtime uses a Redis-backed event bus for orchestration events:

- publish to Redis streams
- pub/sub fanout
- replay from streams
- dead-letter handling

This is implemented in `backend/src/runtime/events/event_bus.py` and consumed by orchestration workers.

## 7. What the current architecture does not yet implement

These are requested future-phase ideas, not current code:

- resource scoring history tables
- an explicit user-owned GitHub repo ingestion path
- a dedicated manual curation workflow for learning resources
- outcome-derived analytics beyond current persistence and metrics

The current codebase does already implement:

- learning session progress / completion / feedback tracking
- a skill graph schema with evidence-backed nodes, aliases, edges, import runs, and user states

## 8. Practical reading order for the current codebase

If you want to understand the current architecture in code order, read:

1. `backend/src/main.py`
2. `backend/src/api/v1/endpoints/learning.py`
3. `backend/src/services/learning/learning_resource_service.py`
4. `backend/src/services/learning/learning_path_service.py`
5. `backend/src/integrations/github/repo_discovery.py`
6. `backend/src/services/learning/github_project_service.py`
7. `backend/src/services/opportunity/outcome_intelligence.py`
8. `backend/src/services/intelligence/career_coach_service.py`
9. `backend/src/runtime/events/event_bus.py`
10. `frontend/src/components/learning/*`
