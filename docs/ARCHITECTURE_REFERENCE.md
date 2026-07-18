# CareerOS AI Enterprise — Architecture Reference

## System Architecture

```
                    ┌─────────────────────────────────────────┐
                    │           Next.js 14 Frontend           │
                    │    TypeScript + Tailwind + React 18     │
                    │  (LoginView, DashboardView,             │
                    │   InterviewCoachView,                   │
                    │   OpportunityCenterView)                │
                    └──────────────┬──────────────────────────┘
                                   │ REST + WebSocket
                    ┌──────────────▼──────────────────────────┐
                    │        NGINX Reverse Proxy (prod)        │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │         FastAPI Backend (:8000)          │
                    │   ┌──────────────────────────────────┐  │
                    │   │   Structured Exception Handlers   │  │
                    │   │   (Auth, Resource, Retrieval,     │  │
                    │   │    LLM, MCP, Orchestration)       │  │
                    │   ├──────────────────────────────────┤  │
                    │   │   7 API Routers                   │  │
                    │   │   /api/health                     │  │
                    │   │   /api/v1/auth                    │  │
                    │   │   /api/v1/knowledge               │  │
                    │   │   /api/v1/packages                │  │
                    │   │   /api/v1/resumes (upload/parse)  │  │
                    │   │   /api/v1/interview               │  │
                    │   │   /api/v1/orchestration           │  │
                    │   └──────────────────────────────────┘  │
                    └──────┬──────────┬──────────┬────────────┘
                           │          │          │
              ┌────────────▼──┐ ┌─────▼─────┐ ┌─▼───────────┐
              │  ARQ Worker   │ │  Redis 7  │ │  PostgreSQL  │
              │  (resume bg)  │ │  (cache,  │ │    15        │
              │               │ │   queue,  │ │   (tables,   │
              │               │ │   tokens) │ │  Alembic)   │
              └───────────────┘ └───────────┘ └─────────────┘
                           │
              ┌────────────▼──────────────────────────────────┐
              │            External AI Services                │
              │  NV-Embed-v1 (NVIDIA NIM) → 4096-dim vectors  │
              │  Rerank QA Mistral 4B (NVIDIA NIM)            │
              │  Claude Sonnet 4.6 (Anthropic)                │
              │  Gemini 2.5 Flash (Google) — fallback LLM     │
              │  Qdrant (vector database)                     │
              │  LangSmith (observability — disabled default) │
              │  Twilio MCP (voice calls)                     │
              │  ElevenLabs MCP (TTS)                         │
              └───────────────────────────────────────────────┘
```

## Request Flow

```
1. Frontend POST /api/v1/auth/register → AuthService.generate_token_pair() → JWT
2. Frontend stores token → subsequent requests with Authorization: Bearer {jwt}
3. middleware.py sets request_id + OpenTelemetry span
4. Endpoint handler:
   ├─ get_current_user() decodes JWT, validates expiration
   ├─ Domain exceptions → structured JSON responses
   └─ Normal flow → returns Pydantic models
```

## Resume Processing Flow (RAG Pipeline)

```
Upload → Parse (PyMuPDF/DOCX/ODT) → GLiNER PII Masking
→ Chunking (RecursiveCharacterTextSplitter)
→ NV-Embed-v1 (4096-dim vectors)
→ Qdrant Indexing (careeros_resumes collection)
→ Ready for retrieval
```

## Agent Pipeline (Opportunity Graph)

```
LangGraph StateGraph (12 nodes):
  START
  → retrieve_candidate_context     [Semantic Qdrant search]
  → retrieve_resume_context        [Enriches with chunk data]
  → retrieve_market_context        [MarketSignalEngine]
  → retrieve_deadline_context      [Deadline parsing]
  → evaluate_opportunity_fit       [OpportunityMatchEngine]
  → evaluate_urgency              [DeadlineUrgencyAgent]
  → generate_priority_score       [PrioritizationEngine]
  → governance_validation         [Governance checks]
  → notification_decision         [Multi-gate: confidence/fit/urgency]
  → voice_synthesis (conditional) [ElevenLabs MCP]
  → twilio_call_execution         [Twilio MCP]
  → trace_compilation             [Explainability agent]
  → END
```

## Retrieval Pipeline

```
Query Understanding → Routing → Dense (Qdrant) → BM25 Sparse
→ RRF Fusion → NVIDIA Reranker → Context Assembly → Citations
```

## MCP Flow

```
Notification decision → MCPRouter.dispatch("generate_audio")
→ MCPConnectionPool → spawns elevenlabs_server.py via stdio
→ returns audio reference

Voice synthesis → MCPRouter.dispatch("make_call")
→ MCPConnectionPool → spawns twilio_server.py via stdio
→ returns call_sid
```

## Deployment Flow

```
docker-compose up
  → PostgreSQL (health: pg_isready)
  → Redis (health: redis-cli ping)
  → Qdrant (health: /readyz)
  → Backend (uvicorn, :8000, lifespan validates config)
  → Worker (ARQ, processes resume jobs from Redis)
  → Frontend (Next.js standalone, :3000)
```

## Folder Structure

```
careeros-complete/
├── frontend/                    # Next.js 14 TypeScript
│   ├── src/
│   │   ├── components/          # 30 React components
│   │   │   ├── DashboardView.tsx
│   │   │   ├── LoginView.tsx
│   │   │   ├── InterviewCoachView.tsx
│   │   │   ├── OpportunityCenterView.tsx
│   │   │   └── ...
│   │   ├── hooks/               # useCareerOS, useMicrophone, useWebSocket
│   │   └── lib/                 # resilience.ts (retry/loading/error)
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   └── Dockerfile
├── backend/
│   ├── src/
│   │   ├── main.py              # FastAPI app, lifespan, 7 routers
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings
│   │   │   └── exceptions/     # 35+ structured exceptions
│   │   ├── api/
│   │   │   ├── health.py        # /ready, /live, /deep, /dependencies
│   │   │   └── v1/endpoints/
│   │   │       ├── auth.py      # register, login, /me
│   │   │       ├── resumes/     # upload, status, retrieval
│   │   │       ├── interview.py
│   │   │       ├── orchestration.py
│   │   │       ├── realtime.py
│   │   │       ├── knowledge.py
│   │   │       └── packages.py
│   │   ├── agents/              # 4 agents (discovery, scoring, urgency, notification)
│   │   ├── graphs/              # LangGraph opportunity graph
│   │   ├── services/            # 60+ service files
│   │   │   ├── resume/          # Upload, parse, PII, chunk, embed, index
│   │   │   ├── retrieval/       # Hybrid, BM25, RRF, reranker, context
│   │   │   ├── embedding/       # NV-Embed-v1 service
│   │   │   ├── intelligence/    # ClaudeService, GeminiProvider
│   │   │   ├── vector_store/    # Qdrant service
│   │   │   ├── mcp/             # Router, Twilio, ElevenLabs
│   │   │   ├── interview/        # 5 interview types
│   │   │   ├── orchestration/   # Graph nodes, retrieval
│   │   │   └── security/        # JWT auth, audit, rate limit
│   │   ├── observability/       # Middleware, logging, tracing, metrics
│   │   │   ├── middleware.py
│   │   │   ├── logger.py
│   │   │   ├── context.py
│   │   │   ├── tracing.py (OpenTelemetry)
│   │   │   ├── metrics.py (Prometheus)
│   │   │   ├── enterprise_logging.py (DomainLoggers)
│   │   │   ├── agent_reliability.py (retry/circuit/timeout)
│   │   │   ├── mcp_reliability.py (MCP retry/circuit)
│   │   │   └── langsmith/       # Tracing, decorators, feedback
│   │   ├── workers/             # ARQ worker for resume processing
│   │   ├── db/                  # PostgreSQL, Redis, Qdrant clients
│   │   ├── models/              # SQLAlchemy models (13 tables)
│   │   └── schemas/             # Pydantic schemas
│   ├── tests/                   # 48 test files
│   ├── alembic/                 # 3 migrations
│   └── Dockerfile
├── nginx/                       # Production reverse proxy config
├── docker-compose.yml           # Dev: 6 services
├── docker-compose.prod.yml      # Prod: 7 services + nginx
└── PHASE11_COMPILATION_AUDIT.md # Latest compilation audit
```

## Key Architecture Decisions

1. **NV-Embed-v1** is the sole embedding model (4096-dim). Single NVIDIA API key powers both embeddings and reranker.
2. **Claude Sonnet 4.6** is primary LLM with **Gemini 2.5 Flash** as automatic fallback (when ANTHROPIC_API_KEY absent).
3. **Qdrant** stores 3 collections: resumes, jobs, knowledge. All retrieval goes through Qdrant.
4. **LangGraph Opportunity Graph** orchestrates 12-node agent pipeline with conditional routing to MCP voice notification.
5. **ARQ** (Redis-based) handles async resume processing jobs.
6. **Structured exceptions** cover all domains with correlation IDs for every error.
7. **OpenTelemetry** traces every request. **Prometheus** metrics for all subsystems.
8. **Domain loggers** provide structured JSON with request_id, trace_id, user_id on every log line.
