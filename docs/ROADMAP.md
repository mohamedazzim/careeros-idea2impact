# CareerOS Roadmap

Last verified from source code: 2026-06-18

This document aligns the roadmap with the current implementation, project memory, and repository intelligence. It is a status document, not a wishlist.

## Current Reality Snapshot

CareerOS already implements the roadmap workflow end to end:

- FastAPI route: `backend/src/api/v1/endpoints/roadmaps.py`
- Frontend page: `frontend/src/app/roadmap/page.tsx`
- Frontend view: `frontend/src/components/CareerRoadmapView.tsx`
- Persistence models: `backend/src/models/roadmap.py`
- Roadmap generation service: `backend/src/services/strategy/roadmap_generation_service.py`
- Route registration: `backend/src/main.py`
- API contract reference: FastAPI route handlers and schemas in `backend/src/api/v1/endpoints/roadmaps.py`

The current implementation is production-shaped, but it is not a perfect one-to-one match with older roadmap claims.

## Implemented and Working

| Area | Status | Evidence | Notes |
|---|---|---|---|
| Roadmap list and details | Implemented | `GET /api/v1/roadmaps`, `GET /api/v1/roadmaps/{roadmap_id}` in `backend/src/api/v1/endpoints/roadmaps.py` | Frontend hydrates list + details in `CareerRoadmapView` |
| Roadmap generation | Implemented | `POST /api/v1/roadmaps/generate` | Uses persisted job-match gaps, current job-market signals, preferences, and LLM fallback; deterministic fallback responses are explicitly labeled |
| Task toggle | Implemented | `PATCH /api/v1/roadmaps/tasks/{task_id}` | Updates task completion in PostgreSQL |
| Progress aggregation | Implemented | `GET /api/v1/roadmaps/progress` | Computes completion from persisted goals/tasks and returns honest telemetry flags (`not_tracked`, null timing fields, diagnostics) |
| Goal/task persistence | Implemented | `backend/src/models/roadmap.py` + repository layer | `roadmaps -> roadmap_goals -> roadmap_tasks` |
| Roadmap UI | Implemented | `frontend/src/app/roadmap/page.tsx`, `frontend/src/components/CareerRoadmapView.tsx` | Page shows goals, tasks, progress charts, and recommendations |
| Verified learning paths | Implemented | `GET /api/v1/learning/skill-gaps`, `GET /api/v1/learning/paths`, `GET /api/v1/learning/paths/{skill_slug}`, `POST /api/v1/learning/paths/refresh` | Resource-backed learning paths use real free URLs and render only for authenticated users |
| GitHub project discovery for missing skills | Implemented | `GET /api/v1/learning/github-projects`, `POST /api/v1/learning/github-projects/refresh` | Real GitHub repositories, templates, and beginner issues are surfaced for each missing skill; the service degrades honestly on rate limits |
| Auth gating | Implemented | `backend/src/api/deps.py`, `frontend/src/middleware.ts` | Roadmap APIs require JWT-authenticated access |
| Route registration | Implemented | `backend/src/main.py` | Router is included in the FastAPI app |

## Implemented but Needs Hardening

| Area | Status | Evidence | Notes |
|---|---|---|---|
| Roadmap generation fallback behavior | Implemented but needs hardening | `backend/src/api/v1/endpoints/roadmaps.py` uses deterministic fallback if provider output is weak and labels the fallback response explicitly | Good safety, but should keep validating generic outputs |
| Roadmap analytics fields | Implemented but needs hardening | `frontend/src/components/CareerRoadmapView.tsx` expects `observability.averageGenerationTimeMs` and similar fields | Timing telemetry is surfaced as `not_tracked` / `null`; diagnostics now distinguish fresh, stale, and partial roadmap evidence |
| User preference hydration | Implemented but needs hardening | `GET /api/v1/user/preferences` feeds roadmap defaults | Works, but roadmap quality depends on preference completeness |
| Progress refresh UX | Implemented but needs hardening | UI polls and hydrates after generate/regenerate | Good enough for demo, but still polling-heavy |
| Roadmap narrative generation | Implemented but needs hardening | `services/strategy/roadmap_generation_service.py` delegates to reasoning pipeline | Depends on LLM availability and prompt quality |

## Known Bugs / Broken Flows

| Area | Status | Evidence | Risk |
|---|---|---|---|
| Production worker presence | Broken in older docs, not roadmap-specific | Verify `docker-compose.prod.yml` and worker runtime logs before release | This affects background jobs generally, not the roadmap route itself |
| Some roadmap documentation claims 100% automatic recalculation | Needs verification | Current backend recalculates progress from stored tasks; it does not expose a separate always-on recalculation service | Do not describe it as autonomous unless verified in runtime |
| Older docs implied roadmap was purely LLM-generated | Partially outdated | Current implementation mixes persisted signals, deterministic fallback, and provider output | Keep describing it as hybrid |

## Provider / External Service Blockers

| Blocker | Impact | Status | Notes |
|---|---|---|---|
| LLM provider outage or rate limit | Roadmap generation may fall back to deterministic plan | Mitigated | Generation still returns a usable roadmap |
| Missing or stale user preferences | Roadmap relevance drops | Operational risk | The roadmap will still render, but quality can be lower |
| Missing current job-match evidence | Roadmap becomes less personalized | Operational risk | Uses fallback guidance when match data is sparse |

## Deployment Readiness

| Area | Status | Evidence | Notes |
|---|---|---|---|
| Local backend route availability | Ready | Route exists in `backend/src/main.py` and `backend/src/api/v1/endpoints/roadmaps.py` | Visible in OpenAPI when app is running |
| Local frontend page availability | Ready | `frontend/src/app/roadmap/page.tsx` | Route works in app shell |
| Database persistence | Ready | `backend/src/models/roadmap.py` and repository layer | Uses PostgreSQL tables already in the schema |
| Demo usability | Ready | `frontend/src/components/CareerRoadmapView.tsx` | UI can demonstrate generation, progress, and tasks |
| Production hardening | Partial | Current docs and runtime evidence show some metrics remain stubbed/defaulted | Use caution when presenting analytics as fully instrumented |

## Next Feature Priorities

1. Make roadmap timing and refresh telemetry real instead of defaulted.
2. Tighten roadmap fallback validation so generic model output is easier to detect.
3. Add a clearer activity timeline for roadmap creation and progress changes.
4. Reduce polling where possible and preserve live state more efficiently.
5. Add tests for roadmap generation fallback and progress aggregation.
6. Expand the verified learning-resource catalog beyond the current seeded free sources.

## Backlog

| Item | Status | Next Action | Priority |
|---|---|---|---|
| Roadmap generation telemetry | Partial | Persist real generation and refresh timing | Medium |
| Roadmap quality tests | Not started | Add request/response tests around generation and progress | Medium |
| Roadmap UI resilience | Partial | Add stronger empty/error states for weak data | Low |
| Roadmap analytics refinement | Partial | Persist roadmap timing telemetry instead of relying on `not_tracked` placeholders | Medium |

## Deprecated / Replaced Plans

| Old claim | Current truth |
|---|---|
| Roadmap is only a simple checklist generator | It is a persisted roadmap system with goals, tasks, progress, and UI |
| Roadmap is pure LLM output | It is hybrid: persisted evidence + preference signals + LLM + deterministic fallback |
| Roadmap progress is magically recalculated elsewhere | Progress is aggregated from stored tasks and roadmap records |

## Gap Table

| Area | Roadmap Claim | Actual Implementation | Gap | Next Action | Priority |
|---|---|---|---|---|---|
| Generation | “Personalized time-phased roadmap” | Yes, via `POST /api/v1/roadmaps/generate` using preferences, job-match signals, and provider fallback | None for core flow | Keep runtime tests around fallback behavior | High |
| Progress tracking | “Automatic progress tracking & recalculating as milestones conclude” | Progress is aggregated from stored goals/tasks and refreshed by the UI | No separate background recalc service | Clarify docs; add event-driven refresh only if needed | Medium |
| Analytics | “Velocity analytics” | UI renders analytics; several values default to zero when not computed | Metrics are present but not fully instrumented | Persist real timing and refresh counts | Medium |
| Roadmap variety | “Multiple roadmap types” | Supported: `AI_ENGINEER`, `SKILL_DEVELOPMENT`, `INTERVIEW_PREP`, `JOB_SEARCH` | No broader taxonomy yet | Keep types explicit in docs/UI | Low |
| Evidence grounding | “Built from target profiling” | Uses job matches, market signals, and preferences | Strong, but depends on data freshness | Ensure docs mention the hybrid evidence model | High |

## Before Adding New Features

- [ ] CI green
- [ ] Docker local healthy
- [ ] Auth works
- [ ] Jobs refresh works
- [ ] Provider errors surfaced clearly
- [ ] Duplicate call suppression safe
- [ ] Conversational call mode fixed
- [ ] Existing docs match implementation

## Evidence Anchors

- Backend router: `backend/src/api/v1/endpoints/roadmaps.py`
- Frontend page: `frontend/src/app/roadmap/page.tsx`
- Frontend view: `frontend/src/components/CareerRoadmapView.tsx`
- Roadmap model: `backend/src/models/roadmap.py`
- Roadmap service: `backend/src/services/strategy/roadmap_generation_service.py`
- Route registration: `backend/src/main.py`
- API contract: `backend/src/api/v1/endpoints/roadmaps.py`
