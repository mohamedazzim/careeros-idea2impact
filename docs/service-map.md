# CareerOS Service Map

Last verified from source code: 2026-06-19

## 1. Main backend services

| Service/module | Responsibility | Depends on | Output / side effect |
|---|---|---|---|
| `src/services/jobs.py` | Job refresh, matching, stats | DB, Qdrant, providers | Jobs, matches, refresh metrics |
| `src/services/resume/*` | Resume parsing and extraction | Storage, PII, embedding, Qdrant | Parsed resume data and chunks |
| `src/services/learning/learning_resource_service.py` | Seed + live learning resources | Providers, DB | Verified resources and provider health |
| `src/services/learning/learning_path_service.py` | Skill-gap aggregation and learning paths | JobMatch, LearningResource | Ordered learning paths and progress data |
| `src/services/learning/gap_action_service.py` | Gap actions and proof actions | Learning path service, resources | Project ideas, resume proof, interview proof |
| `src/services/learning/github_project_service.py` | GitHub project discovery wrapper | GitHub provider, cache, DB | Repo/issue suggestions per skill |
| `src/services/skill_graph/skill_graph_service.py` | Skill graph import and inspection | Jobs, learning resources, resumes, roadmaps | Evidence-backed skill nodes, aliases, edges, and user states |
| `src/integrations/github/repo_discovery.py` | GitHub API search adapter | GitHub Search API | Repo and issue candidates |
| `src/integrations/learning/discovery.py` | Web/Coursera/Udemy/YouTube discovery providers | Bing/Tavily/SerpAPI, YouTube API | Verified learning candidates |
| `src/integrations/youtube/client.py` | YouTube Data API client | YouTube API | Video candidates |
| `src/services/opportunity/outcome_intelligence.py` | Conversion funnel metrics | CommunicationRequest, VoiceSession, timeline events | Outcome metrics and events |
| `src/services/opportunity/voice_opportunity_agent.py` | Voice call orchestration | Models, providers, conversation state | Voice actions and transcripts |
| `src/services/opportunity/conversational_outbound_call_service.py` | ConvAI outbound call initiation | ElevenLabs / bridge config | Live conversational call start |
| `src/services/opportunity/twilio_reconciliation.py` | Twilio / call reconciliation | DB, provider state | Reconciled call rows |
| `src/services/intelligence/career_coach_service.py` | Aggregate career intelligence and coaching | Outcome intelligence tables, career memory | Coaching plans, goals, recommendations |
| `src/services/orchestration/*` | LangGraph runtime and coordination | Redis, checkpoints, agents | Session state and graph execution |
| `src/runtime/events/event_bus.py` | Redis event bus | Redis | Publish, replay, dead-letter |
| `src/runtime/recovery/*` | Replay and checkpoint recovery | Event bus, checkpoint storage | Replay output |
| `src/observability/langsmith/*` | Tracing and circuit breaking | LangSmith config | Fail-open tracing behavior |
| `src/services/mcp/mcp_router.py` | Tool governance and dispatch | MCP servers, governance agent | Audited tool execution |
| `src/services/security/auth.py` | JWT auth and token lifecycle | DB, cookies | Access/refresh token behavior |

## 2. Frontend service and hook map

| Frontend module | Responsibility | Depends on | Output |
|---|---|---|---|
| `src/hooks/useCareerOS.ts` | Main authenticated data-fetching hook | REST API, auth cookie | Application state |
| `src/hooks/useWebSocket.ts` | WebSocket connection management | Realtime router, auth token | Interview/trace streams |
| `src/lib/resilience.ts` | Resilient fetch with retries | Fetch API | Backoff-based requests |
| `src/lib/rbac.ts` | Route and nav gating | Role claims | Visible menu and page access |
| `src/components/learning/LearningPathsPanel.tsx` | Learning path UI | `/api/v1/learning/*` | Skill path cards |
| `src/components/learning/GapActionsPanel.tsx` | Proof-action UI | `/api/v1/learning/gap-actions` | Project/proof cards |
| `src/components/learning/GitHubProjectsPanel.tsx` | GitHub project UI | `/api/v1/learning/github-projects` | Repo and issue cards |
| `src/components/JobsIntelligenceView.tsx` | Jobs UI | `/api/v1/jobs` | Job lists and diagnostics |
| `src/components/CareerRoadmapView.tsx` | Roadmap UI | `/api/v1/roadmaps` | Roadmap goals, tasks, telemetry |
| `src/components/SkillGraphView.tsx` | Skill graph inspection dashboard | `/api/v1/skill-graph/*` | Canonical skill nodes, edges, evidence, and import runs |

## 3. Request lifecycle by domain

### Authenticated REST request

1. Browser sends request with cookie-based auth.
2. FastAPI dependency decodes the JWT and loads user context.
3. Router validates input with Pydantic.
4. Service executes business logic.
5. Service may touch PostgreSQL, Redis, Qdrant, or external providers.
6. Response is normalized for the frontend types.

### Learning-path request

1. Frontend sends skill list or `job_id`.
2. API resolves the user's skill gaps.
3. Learning service finds or discovers resources.
4. Resources are stored, ordered, and returned.
5. Frontend renders per-skill cards and provider health.

### GitHub discovery request

1. Frontend passes the requested skills/job context.
2. Backend resolves the same skill gap aggregate.
3. GitHub provider searches public repos/issues.
4. Results are ranked and cached.
5. Frontend renders repo cards and issue cards.

### Opportunity/outcome request

1. Opportunity flow creates a communication or voice record.
2. Voice session and transcript data are persisted.
3. Outcome service calculates conversion/funnel metrics.
4. Coach and dashboard services read the stored metrics.

## 4. Service dependency notes

- `learning_path_service` depends on `learning_resource_service`.
- `gap_action_service` depends on both `learning_path_service` and `learning_resource_service`.
- `github_project_service` depends on `learning_path_service` and `repo_discovery`.
- `career_coach_service` depends on `outcome_intelligence` and `career memory`.
- `skill_graph_service` depends on jobs, learning, roadmap, and resume evidence sources.
- `event_bus` is shared by orchestration runtime and replay utilities.
- `main.py` is the composition root that wires routers and startup validation.

## 5. What is missing from the requested design

The requested architecture mentions some components that are not yet present as dedicated services:

- `resource_score_history`
- richer skill graph traversal / recommendation scoring
- explicit user-owned GitHub ingestion service
- manual resource curation workflow
- a full explainable resource-scoring pipeline with persisted breakdown rows

Those should be treated as future service additions, not as current service responsibilities.
