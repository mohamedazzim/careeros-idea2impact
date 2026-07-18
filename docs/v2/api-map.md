# CareerOS V2 API Map

Last verified from source code: 2026-06-19

This map lists the real router surfaces currently registered in [`backend/src/main.py`](../../backend/src/main.py). It is intentionally route-accurate so later V2 work does not accidentally create double-prefix bugs or stale endpoints.

## Router registration overview

| Router / file | Mounted prefix in `main.py` | Effective route family |
|---|---|---|
| `api/v1/endpoints/health.py` | `/api` | `/api/health/*` |
| `api/v1/endpoints/auth.py` | `/api/v1` | `/api/v1/auth/*` |
| `api/v1/endpoints/resumes/*` | `/api/v1/resumes` | Resume upload / retrieval / retry / lifecycle |
| `api/v1/endpoints/knowledge.py` | `/api/v1` | `/api/v1/knowledge/*` |
| `api/v1/endpoints/jobs.py` | `/api/v1` | `/api/v1/jobs/*` |
| `api/v1/endpoints/opportunities_api.py` | `/api/v1` | `/api/v1/opportunities/*` |
| `api/v1/endpoints/opportunity_alert.py` | `/api` | `/api/opportunity-alert` |
| `api/v1/endpoints/learning.py` | `/api/v1` | `/api/v1/learning/*` |
| `api/v1/endpoints/roadmaps.py` | `/api/v1` | `/api/v1/roadmaps/*` |
| `api/v1/endpoints/demo_rag.py` | `/api/v1` | `/api/v1/demo-rag/*` |
| `api/v1/endpoints/outcome_intelligence.py` | `/api` | `/api/outcomes/*`, `/api/conversations/*`, `/api/candidate-memory/*` |
| `api/v1/endpoints/autonomous_engagement.py` | `/api` | `/api/followups/*`, `/api/application-lifecycle/*`, `/api/career-progress`, `/api/opportunity-reranking` |
| `api/v1/endpoints/phase6.py` | `/api/v1` | `/api/v1/candidate-memory`, `/api/v1/opportunities/reranked`, `/api/v1/career-intelligence/*`, `/api/v1/learning-loop/*` |

## Health and readiness

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/api/health/live` | Liveness probe | Mounted from `src.api.health` |
| GET | `/api/health/ready` | Readiness probe | Mounted from `src.api.health` |

## Authentication and user session

| Method | Path family | Purpose | Notes |
|---|---|---|---|
| POST / GET / PATCH | `/api/v1/auth/*` | Login, refresh, logout, password reset, session actions | Exact auth contract is in `backend/src/api/v1/endpoints/auth.py` |

## Resume APIs

| Method | Path family | Purpose | Source |
|---|---|---|---|
| POST | `/api/v1/resumes/upload` | Upload resume | `resumes/upload.py` |
| GET | `/api/v1/resumes/status/*` | Resume status | `resumes/status.py` |
| GET / POST | `/api/v1/resumes/retrieval/*` | Retrieval and lookup | `resumes/retrieval.py` |
| POST | `/api/v1/resumes/retry/*` | Retry processing | `resumes/retry.py` |
| GET | `/api/v1/resumes/lifecycle/*` | Lifecycle views | `resumes/lifecycle.py` |

## Knowledge Hub APIs

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/knowledge/upload` | Upload knowledge docs |
| GET | `/api/v1/knowledge` | List docs |
| GET | `/api/v1/knowledge/{doc_id}` | Fetch one doc |
| DELETE | `/api/v1/knowledge/{doc_id}` | Delete one doc |
| POST | `/api/v1/knowledge/{doc_id}/analyze` | Analyze uploaded content |
| GET | `/api/v1/knowledge/{doc_id}/score` | Document score |
| GET | `/api/v1/knowledge/alignment-report/{run_id}` | Alignment report |

## Jobs APIs

| Method | Path | Purpose | Backing service |
|---|---|---|---|
| GET | `/api/v1/jobs` | List jobs | `services/jobs.py` |
| GET | `/api/v1/jobs/stats` | Job statistics | `services/jobs.py` |
| GET | `/api/v1/jobs/alert-stats` | Delivery / alert stats | `services/jobs.py` |
| GET | `/api/v1/jobs/alerts` | Alert records | `services/jobs.py` |
| GET | `/api/v1/jobs/applications` | Application view | `services/jobs.py` |
| POST | `/api/v1/jobs/refresh` | Refresh jobs | `services/job_refresh.py` and `services/jobs.py` |
| GET | `/api/v1/jobs/refresh/{session_id}` | Refresh status | refresh session store |
| GET | `/api/v1/jobs/{job_id}` | Single job | `services/jobs.py` |
| POST | `/api/v1/jobs/{job_id}/application` | Update application state | `services/jobs.py` |
| GET | `/api/v1/jobs/{job_id}/application` | Read application state | `services/jobs.py` |
| GET | `/api/v1/jobs/providers/*` | Provider health / reconciliation | provider adapters |

## Opportunity APIs

| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/api/v1/opportunities/discover` | Run discovery pipeline | Persists matches |
| GET | `/api/v1/opportunities/list` | List persisted matches | Current opportunity feed |
| GET | `/api/v1/opportunities/rc3/intelligence` | Opportunity intelligence | Timeline / summary view |
| GET | `/api/v1/opportunities/rc3/timeline/{job_id}` | Opportunity timeline | Per-job chronology |
| POST | `/api/v1/opportunities/rc3/outcomes` | Record outcomes | Outcome capture |
| POST | `/api/v1/opportunities/rc3/lifecycle/run` | Run lifecycle agent | Lifecycle orchestration |
| POST | `/api/v1/opportunities/alert` | Trigger alert delivery | Governed by alert_action_service |
| GET | `/api/v1/opportunities/skill-gap/{job_id}` | Persist skill-gap analysis | Bridges to learning |

## Skill Gap APIs

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/api/v1/skill-gaps/health` | Health check | Public |
| POST | `/api/v1/skill-gaps/analyze` | Run evidence-backed skill gap analysis | Persists analysis run, findings, evidence, and snapshot |
| GET | `/api/v1/skill-gaps/runs` | List analysis runs | Authenticated |
| GET | `/api/v1/skill-gaps/runs/{run_uid}` | Fetch a single analysis run | Authenticated |
| GET | `/api/v1/skill-gaps/jobs/{job_id}` | Get job-scoped gap summary | Authenticated |
| GET | `/api/v1/skill-gaps/snapshot` | Fetch latest user snapshot | Authenticated |
| GET | `/api/v1/skill-gaps/findings` | List skill gap findings | Authenticated |
| GET | `/api/v1/skill-gaps/skills/{skill_slug}/evidence` | Inspect skill evidence | Authenticated |

## Learning APIs

| Method | Path | Purpose | Backing service |
|---|---|---|---|
| GET | `/api/v1/learning/skill-gaps` | Current skill gaps | `learning_path_service` |
| GET | `/api/v1/learning/paths` | List learning paths | `learning_path_service` |
| GET | `/api/v1/learning/paths/{skill_slug}` | Path detail | `learning_path_service` |
| POST | `/api/v1/learning/paths/refresh` | Refresh learning paths | `learning_path_service` |
| GET | `/api/v1/learning/gap-actions` | Gap actions | `gap_action_service` |
| POST | `/api/v1/learning/gap-actions/refresh` | Refresh gap actions | `gap_action_service` |
| GET | `/api/v1/learning/github-projects` | GitHub project ideas | `github_project_service` |
| POST | `/api/v1/learning/github-projects/refresh` | Refresh project ideas | `github_project_service` |

## Roadmap APIs

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/api/v1/roadmaps` | List roadmaps | Current roadmap catalog |
| GET | `/api/v1/roadmaps/{roadmap_id}` | Read roadmap detail | Includes goals/tasks |
| POST | `/api/v1/roadmaps/generate` | Generate roadmap | Evidence-driven roadmap builder |
| POST | `/api/v1/roadmaps/regenerate` | Regenerate roadmap | Uses existing roadmap state |
| GET | `/api/v1/roadmaps/progress` | Aggregated progress | Distinguishes stored progress from missing telemetry |
| PATCH | `/api/v1/roadmaps/tasks/{task_id}` | Update task state | Task completion tracking |

## Docs-RAG APIs

| Method | Path | Purpose | Auth |
|---|---|---|---|
| POST | `/api/v1/demo-rag/chat` | Chat over `docs/rag/` | Authenticated user required by frontend flow |
| POST | `/api/v1/demo-rag/index` | Index docs into Qdrant | Authenticated user required |
| GET | `/api/v1/demo-rag/health` | Service health | Open |
| GET | `/api/v1/demo-rag/golden-questions` | Test question set | Open |

Current docs-RAG behavior:

- uses `docs/rag/` markdown as source of truth
- indexes into `careeros_rag_docs`
- can optionally relay to Make when configured
- falls back to local generation when relay is unavailable

## Outcome intelligence and autonomous engagement APIs

### Outcome intelligence mounted under `/api`

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/outcomes` | Aggregate outcome overview |
| GET | `/api/outcomes/{candidate_id}` | Candidate outcome detail |
| GET | `/api/conversations/{conversation_id}` | Conversation detail |
| POST | `/api/conversations/process` | Process a conversation |
| GET | `/api/candidate-memory/{candidate_id}` | Candidate memory |
| GET | `/api/candidate-concerns/{candidate_id}` | Candidate concerns |

### Autonomous engagement mounted under `/api`

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/followups` | Follow-up tasks |
| POST | `/api/followups/{task_id}/execute` | Execute a follow-up |
| GET | `/api/application-lifecycle` | Application lifecycle overview |
| GET | `/api/application-lifecycle/{job_id}` | Lifecycle detail |
| GET | `/api/career-progress` | Career progress summary |
| GET | `/api/opportunity-reranking` | Reranking overview |

### Phase 6 career intelligence mounted under `/api/v1`

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/candidate-memory` | Candidate memory overview |
| GET | `/api/v1/candidate-memory/history` | Candidate memory history |
| GET | `/api/v1/opportunities/reranked` | Reranked opportunities |
| GET | `/api/v1/opportunities/reranked/{job_id}` | Single reranked opportunity |
| POST | `/api/v1/application-lifecycle/update` | Update lifecycle state |
| GET | `/api/v1/application-lifecycle/history` | Lifecycle history |
| GET | `/api/v1/application-lifecycle/current/{job_id}` | Current lifecycle view |
| GET | `/api/v1/career-intelligence` | Career intelligence snapshot |
| GET | `/api/v1/career-intelligence/weekly-summary` | Weekly summary |
| GET | `/api/v1/career-coach` | Coach overview |
| GET | `/api/v1/career-coach/plans` | Coach plans |
| GET | `/api/v1/career-coach/goals` | Coach goals |
| GET | `/api/v1/career-coach/recommendations` | Coach recommendations |
| POST | `/api/v1/learning-loop/run` | Learning loop run |
| GET | `/api/v1/learning-loop/history` | Learning loop history |

## Observability, packages, readiness, evaluation, and MCP

| Area | Path family | Notes |
|---|---|---|
| Observability | `/api/v1/observability/*` | Metrics, latency, overview, and LLM views |
| Packages | `/api/v1/packages/*` | Package catalog / versioning views |
| Readiness | `/api/v1/readiness/*` | Score, timeline, explain, report, downloads |
| Evaluation | `/api/v1/evaluation/*` | Evaluation flows |
| Preferences | `/api/v1/preferences/*` | User preferences |
| Troubleshoot | `/api/v1/troubleshoot/*` | Diagnostics |
| MCP | `/api/v1/mcp/test` | MCP governance / tracing test endpoint |
| Rerank | `/api/v1/rerank/*` | Ranking tooling |

## API map takeaways for V2

1. The backend already exposes the major surfaces needed for a V2 platform.
2. Route prefixing is a real risk: some routers live under `/api`, others under `/api/v1`.
3. V2 planning should use these current paths as the stable contract unless code deliberately changes them.
