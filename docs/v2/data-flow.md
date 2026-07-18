# CareerOS V2 Data Flow

Last verified from source code: 2026-06-20

This document describes the real data movement in the current codebase. It focuses on the paths that are already implemented.

## 1) Core request flow

```mermaid
flowchart LR
  U[User] --> FE[Next.js App Router UI]
  FE -->|Bearer token / auth cookie| API[FastAPI router]
  API --> SVC[Domain service]
  SVC --> DB[(PostgreSQL)]
  SVC --> REDIS[(Redis / ARQ / locks / cache)]
  SVC --> QDR[(Qdrant)]
  SVC --> EXT[External providers]
  EXT --> SVC
  SVC --> API
  API --> FE
```

This is the common pattern across job, learning, roadmap, opportunity, and docs-RAG features.

## 2) Learning-resource flow

```mermaid
flowchart TD
  J[Job matches / job gaps] --> LPS[learning_path_service]
  LPS --> LRS[learning_resource_service]
  LRS --> SEED[Seeded curated markdown resources]
  LRS --> GH[GitHub discovery]
  LRS --> YT[YouTube discovery]
  LRS --> WEB[Web search discovery]
  GH --> LRS
  YT --> LRS
  WEB --> LRS
  LRS --> DB[(learning_resources)]
  LRS --> HP[Provider health payload]
  DB --> LPS
  LPS --> LP[learning paths + items]
  LP --> FE[Learning UI panels]
```

Real behaviors in code:

- seeded resources are always available as fallback
- live discovery is optional and provider-dependent
- resources are ranked by trust, relevance, freshness, and verification time
- learning paths are stored in Postgres

## 2.1) Learning outcome tracking flow

```mermaid
flowchart LR
  UI[Learning resource controls] --> API[POST/PATCH /api/v1/learning/...]
  API --> OLS[learning_outcome_service]
  OLS --> SES[(learning_sessions)]
  OLS --> FDB[(resource_feedback)]
  OLS --> OUT[(resource_outcomes)]
  OLS --> ACT[(learning_activity_events)]
  OLS --> EVT[(career_events)]
  OUT --> UI2[Learning outcome panels]
```

Real behaviors in code:

- open/start/progress/complete/abandon/feedback actions are persisted
- session and feedback records feed the aggregate outcome row
- outcome calculations stay honest by returning `insufficient_data` when starts and feedback are both absent
- CareerEvent writes are best-effort and never block the learning action

## 2.2) Skill graph import flow

```mermaid
flowchart TD
  JOBS[Jobs / job matches] --> SG[skill_graph_service]
  LEARN[Learning resources / outcomes] --> SG
  RES[Resume evidence] --> SG
  ROAD[Roadmap tasks / goals] --> SG
  SG --> NODE[(skill_graph_nodes)]
  SG --> ALIAS[(skill_graph_aliases)]
  SG --> EDGE[(skill_graph_edges)]
  SG --> EVID[(skill_graph_evidence)]
  SG --> RUN[(skill_graph_import_runs)]
  SG --> STATE[(user_skill_states)]
  SG --> UI[Skill graph dashboard]
```

Real behaviors in code:

- skill graph nodes are evidence-backed rather than free-form
- aliases and edges are derived from the same normalized import pass
- import runs are persisted for auditability and dashboard inspection
- the frontend can trigger an authenticated import and then inspect the resulting graph

## 2.3) Evidence-backed skill gap flow

```mermaid
flowchart TD
  JOB[Job requirements] --> EVID[skill_gap_evidence_service]
  RES[Resume signals] --> EVID
  LEARN[Learning outcomes] --> EVID
  ROAD[Roadmap tasks / goals] --> EVID
  GRAPH[Skill graph evidence] --> EVID
  EVID --> ENG[skill_gap_engine]
  ENG --> RUN[(skill_gap_analysis_runs)]
  ENG --> FIND[(skill_gap_findings)]
  ENG --> FEV[(skill_gap_finding_evidence)]
  ENG --> SNAP[(user_skill_gap_snapshots)]
  RUN --> API[skill_gaps API]
  FIND --> API
  SNAP --> UI[EvidenceBackedSkillGapPanel]
```

Real behaviors in code:

- analysis uses stored evidence rather than guessed scores
- missing inputs degrade to `insufficient_data` or legacy heuristics rather than fabricated certainty
- runs, findings, and snapshots are persisted for later comparison and review
- the frontend can ask the API for a job-scoped gap summary and render evidence chips

## 3) GitHub project discovery flow

```mermaid
flowchart LR
  GAP[Skill gaps] --> GPS[github_project_service]
  GPS --> DISC[GitHub repo/issue search]
  DISC --> REPO[Repositories]
  DISC --> ISSUE[Issues]
  REPO --> SCORE[Template / stars / archived scoring]
  ISSUE --> SCORE
  SCORE --> DB[(Learning / project records)]
  DB --> FE[GitHub Projects panel]
```

Current ranking signals are code-backed:

- stars
- template / starter / boilerplate wording
- archived penalty
- issue labels such as `good first issue` and `help wanted`

## 4) Docs-RAG flow

```mermaid
flowchart TD
  MD[docs/rag/*.md] --> CHUNK[Markdown chunking]
  CHUNK --> EMB[Embedding service]
  EMB --> QDR[(Qdrant careeros_rag_docs)]
  FE[Frontend chatbot] --> API[/POST /api/v1/demo-rag/chat/]
  API --> RET[Retrieval]
  RET --> QDR
  RET --> MAKE[Optional Make webhook relay]
  MAKE -->|if configured| ANSWER[Answer normalization]
  RET --> LLM[Local LLM generation via fallback provider]
  ANSWER --> FE
  LLM --> FE
```

Real behavior:

- docs are discovered from `docs/rag/`
- chunk ids are stable and content-hash based
- embeddings are stored in `careeros_rag_docs`
- Make relay is optional; local generation is the fallback path

## 5) Job refresh and matching flow

```mermaid
flowchart LR
  WEB[TheirStack / job sync provider] --> REFRESH[job_refresh]
  REFRESH --> MATCH[job matching / scoring]
  MATCH --> JOBS[(jobs)]
  MATCH --> JM[(job_matches)]
  MATCH --> SAL[(salary_intelligence)]
  MATCH --> FE[Jobs UI]
  MATCH --> ALERT[Opportunity alert pipeline]
```

Current implementation includes:

- provider quota / failure handling
- stale / already-seen job detection
- refresh diagnostics
- job stats and provider health views

## 6) Opportunity / voice flow

```mermaid
flowchart TD
  MATCHED[Persisted opportunity] --> ACTION[alert_action_service]
  ACTION --> GOV[orchestration governance]
  GOV --> ORCH[communication_orchestrator]
  ORCH --> VOICE[voice providers]
  VOICE --> TW[Twilio / ElevenLabs]
  ORCH --> CR[(communication_requests)]
  ORCH --> VS[(voice_sessions)]
  TW --> TRANS[transcript sync]
  TRANS --> VC[(voice_conversations)]
  TRANS --> VO[(voice_outcomes)]
  VO --> OI[outcome intelligence]
  CR --> OI
  VS --> OI
```

The current codebase stores communication state and later aggregates outcomes from those stored records.

## 7) Roadmap/progress flow

```mermaid
flowchart LR
  TASKS[(roadmap_tasks)] --> PROG[roadmaps progress API]
  GOALS[(roadmap_goals)] --> PROG
  ROADMAPS[(roadmaps)] --> PROG
  PROG --> UI[Roadmap page]
  PROG --> DIAG[Telemetry / diagnostics]
```

Important current behavior:

- progress is derived from stored task completion
- missing analytics fields are no longer treated as real telemetry
- diagnostics can say `not_tracked`

## 8) Event and worker flow

```mermaid
flowchart LR
  API[FastAPI] --> BUS[Redis streams / pubsub event bus]
  BUS --> WORKER[ARQ / background workers]
  WORKER --> DB[(PostgreSQL)]
  WORKER --> QDR[(Qdrant)]
  WORKER --> DLQ[Dead-letter / replay handling]
```

The event layer is important for future V2 work because it provides a foundation for auditability and replay.

## 10) Current data quality posture

The system already distinguishes between:

- real stored data
- seeded fallback data
- provider-unavailable states
- insufficient or missing evidence

That is a good base for V2, because it avoids the most dangerous anti-pattern: pretending a heuristic or empty field is a verified outcome.
