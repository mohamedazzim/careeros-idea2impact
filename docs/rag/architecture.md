# CareerOS Architecture Overview

Last verified from source code: 2026-06-14

## Purpose

CareerOS is a job-search and career-operations platform.
It combines resume intelligence, job matching, interview coaching, opportunity discovery, workflow orchestration, and outbound engagement.

## High-level stack

| Layer | Tech |
| --- | --- |
| Frontend | Next.js App Router, React 18, TypeScript |
| Backend | FastAPI, async SQLAlchemy, Pydantic |
| Storage | PostgreSQL, Redis, Qdrant |
| Workflow | LangGraph, background jobs, orchestration services |
| LLMs | Gemini 2.5 Flash primary, DeepSeek NIM fallback |
| Voice / SMS | ElevenLabs, Twilio, MCP router |

## Main runtime shape

1. The frontend authenticates with `careeros_token`.
2. The shell decides which routes are public and which are protected.
3. Data fetching flows through `useCareerOS()` and related helpers.
4. The backend exposes routers for jobs, knowledge, packages, approvals, interview, orchestration, readiness, MCP, observability, and more.
5. Workflow graphs coordinate resume, opportunity, interview, and outcome intelligence flows.
6. Results are persisted to relational tables and, where needed, Qdrant vector collections.

## Major frontend domains

- Dashboard
- Jobs
- Knowledge
- Packages
- Coach
- Interview
- Opportunities
- Command Center
- Approvals
- Ops
- Orchestration
- Rerank
- Preferences
- Roadmap
- Account
- Login and password recovery

## Major backend domains

- Auth and account management
- Jobs and job matching
- Knowledge upload, analysis, and scoring
- Packages and generated application assets
- Interview sessions and voice streams
- Readiness and alignment reports
- Opportunity discovery, scoring, alerting, and outbound action
- Orchestration and governance
- Approvals and human-in-the-loop execution
- Troubleshooting and circuit control
- Observability and metrics
- Reranking, phase 6 intelligence, and learning loops

## Source anchors

- `backend/src/main.py`
- `backend/src/core/config.py`
- `backend/src/services/llm/factory.py`
- `backend/src/services/mcp/mcp_router.py`
- `frontend/src/app/layout.tsx`
- `frontend/src/components/AppShell.tsx`
- `frontend/src/components/Navigation.tsx`
- `frontend/src/hooks/useCareerOS.ts`
- `frontend/src/hooks/useWebSocket.ts`
