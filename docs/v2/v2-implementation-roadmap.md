# CareerOS V2 Implementation Roadmap

Last verified from source code: 2026-06-20

This is a planning document only. It does not change production behavior.

The roadmap is ordered from safest, highest-leverage work to riskier platform changes.

## Milestone plan

| Milestone | Goal | Files likely touched | DB migration? | Backend work | Frontend work | Tests / verification | Rollback / done |
|---|---|---|---|---|---|---|---|
| M0 | Architecture documentation baseline | `docs/v2/*` | No | None | None | Docs review only | Safe to ship; no runtime impact |
| M1 | Event audit foundation | `services/runtime/*`, `services/orchestration/*`, `workers/*` | Possibly | Normalize event schemas and audit payloads | Optional diagnostics UI | Unit + integration tests on event emission | Keep existing event paths, add-only |
| M2 | Resource provenance ledger | `services/learning/*`, `integrations/*` | Likely yes | Persist source, verification, and scoring evidence more explicitly | Show evidence chips | Provider + persistence tests | Feature-flag the new evidence fields |
| M3 | Learning outcome tracking | `backend/src/models/learning.py`, `backend/src/services/learning/learning_outcome_service.py`, `backend/src/api/v1/endpoints/learning.py`, `frontend/src/components/learning/*`, `frontend/src/lib/learning-outcomes.ts` | Yes | Store open/start/progress/complete/abandon/feedback signals, aggregate sessions/outcomes, and emit CareerEvent rows | Add completion and progress UI | Workflow tests and UI smoke checks | Keep existing paths functional; return `insufficient_data` when signals are sparse |
| M4 | Skill graph schema and seed/import strategy | `models/*`, `services/strategy/*` | Yes | Add skill graph / relations / provenance | Basic graph inspection UI | Schema tests and import tests | Add-only schema evolution |
| M5 | Evidence-backed skill gap engine | `backend/src/services/skill_gap/*`, `backend/src/api/v1/endpoints/skill_gaps.py`, `frontend/src/components/learning/EvidenceBackedSkillGapPanel.tsx` | Yes | Compute gaps from evidence graph, learning outcomes, resume signals, project signals, and skill graph evidence | Explain gap drivers in UI | Compare analyzed runs against persisted findings and snapshots | Fallback to `insufficient_data` or legacy heuristics when evidence is sparse |
| M6 | Project validation engine | `services/learning/github_project_service.py`, `integrations/github/*` | Maybe | Validate project ideas against repo evidence and issue signals | Project validation panel | GitHub fixture tests | Keep public-search fallback |
| M7 | Learning path generator with feedback loops | `services/learning/*`, `services/strategy/*` | Yes | Generate paths from graph + outcomes | Add richer path detail and review actions | End-to-end path generation tests | Preserve current path generation as fallback |
| M8 | Dynamic roadmap generation from evidence graph | `services/strategy/roadmap_generation_service.py`, `api/v1/endpoints/roadmaps.py` | Likely yes | Make roadmaps evidence-aware and versioned | Roadmap evidence view | Roadmap regression tests | Read-only fallback roadmap generation |
| M9 | Personalization profile and preference memory | `models/outcome_intelligence.py`, `services/intelligence/*` | Yes | Persist user preferences and behavior signals | Preference explanation UI | Memory / preference tests | Use current defaults when profile is empty |
| M10 | Evidence-cited AI copilot | `services/rag/service.py`, `services/intelligence/*`, `frontend/src/components/rag/*` | Maybe | Strict retrieval, citations, and refusal behavior | Improve citations and follow-up questions | Golden-question tests, citation tests | Local fallback if relay/provider fails |
| M11 | Real analytics dashboard | `services/intelligence/intelligence_metrics.py`, `api/v1/endpoints/observability.py`, `frontend/src/components/*` | Maybe | Replace default values with stored metrics and time series | Build analytics panels from real data | Snapshot and calculation tests | Show `not_tracked` rather than fake zeros |
| M12 | Observability and provider health hardening | `observability/*`, `services/mcp/*`, `integrations/*` | No or maybe | Quota handling, circuit breakers, health aggregation | Surface provider health clearly | Quota / degraded-path tests | Fail open where safe, not silent |
| M13 | Production readiness and rollout controls | Deployment, worker, docs, env examples | No | Tighten config validation, feature flags, deployment checks | Minimal UI changes | Full smoke / deploy verification | Roll out behind flags and configs |

## Recommended first implementation phase

The best first implementation phase is **M1: Event audit foundation**.

Why M1 first:

1. It improves every downstream analytics and copilot system.
2. It does not require changing the user-visible product shape immediately.
3. It creates the provenance layer needed for evidence-backed scoring.
4. It reduces the risk of building new features on top of shaky, incomplete telemetry.

## Milestone ordering rationale

### Safest wins first

- M0, M1, and M2 are the best early steps because they improve truthfulness and traceability.

### Medium-risk platform work

- M3 through M8 add meaningful product value, but only after the event and provenance foundations are stronger.

### Highest leverage, but highest fidelity requirement

- M9 through M13 require the strongest evidence model, because anything that looks like prediction, recommendation, or analytics must be defensible.

## Milestone status notes

### M3 Learning Outcome Tracking — Implemented

M3 is implemented in the current codebase.

- Backend tables: `learning_sessions`, `resource_feedback`, `resource_outcomes`, `learning_activity_events`
- Backend service: `backend/src/services/learning/learning_outcome_service.py`
- Backend endpoints: open, start, progress, complete, abandon, feedback, outcomes, and activity routes under `backend/src/api/v1/endpoints/learning.py`
- Frontend controls: `frontend/src/components/learning/LearningOutcomeControls.tsx`
- Frontend wiring: `frontend/src/components/learning/LearningPathsPanel.tsx` and `frontend/src/components/learning/GapActionsPanel.tsx`
- CareerEvent integration: learning actions emit sanitized audit rows without blocking user flows
- Honest fallback: `status="insufficient_data"` when there are no starts and no feedback yet
- Aggregation inputs: started sessions, completed sessions, abandoned sessions, feedback count, average rating, completion rate, drop-off rate, recommendation rate, average completion percentage, and average duration
- Recommended next milestone: M4 Skill graph schema and seed/import strategy

### M4 Skill Graph Schema and Import Dashboard — Implemented

M4 is implemented in the current codebase.

- Backend models: `backend/src/models/skill_graph.py`
- Backend migration: `backend/alembic/versions/030_skill_graph_schema.py`
- Backend service: `backend/src/services/skill_graph/skill_graph_service.py`
- Backend endpoints: `/api/v1/skill-graph/health`, `/summary`, `/nodes`, `/nodes/{skill_slug}`, `/states`, `/import-runs`, `/import`
- Frontend view: `frontend/src/components/SkillGraphView.tsx`
- Frontend route: `/skill-graph`
- Canonical records: skill graph nodes, aliases, edges, evidence rows, import runs, and user skill states
- Import behavior: evidence-backed aggregation over jobs, learning resources, resumes, and roadmap signals
- CareerEvent integration: import runs emit `SkillGraphImportCompleted` audit rows
- Recommended next milestone: M6 project validation engine

### M5 Evidence-Backed Skill Gap Engine — Implemented

M5 is implemented in the current codebase.

- Backend models: `backend/src/models/skill_gap.py`
- Backend migration: `backend/alembic/versions/031_skill_gap_engine.py`
- Backend service: `backend/src/services/skill_gap/skill_gap_engine.py`
- Backend query helpers: `backend/src/services/skill_gap/skill_gap_query_service.py`
- Backend evidence helpers: `backend/src/services/skill_gap/skill_gap_evidence_service.py`
- Backend explanation helpers: `backend/src/services/skill_gap/skill_gap_explanation_service.py`
- Backend endpoints: `backend/src/api/v1/endpoints/skill_gaps.py`
- Frontend panel: `frontend/src/components/learning/EvidenceBackedSkillGapPanel.tsx`
- Imported evidence: jobs, resumes, learning sessions, learning outcomes, roadmap tasks, and skill graph signals
- Persisted records: analysis runs, findings, finding evidence, and user skill gap snapshots
- CareerEvent integration: completed analyses emit `SkillGapAnalysisCompleted` audit rows
- Honest fallback: analysis can return `insufficient_data` when evidence is thin
- Remaining gap: broader calibration, expanded source coverage, and longer-term validation
- Recommended next milestone: M6 project validation engine

## Definition of done for each milestone

Every milestone should satisfy these baseline conditions:

1. It must not fabricate data when evidence is missing.
2. It must preserve existing working features.
3. It must include tests or runtime verification.
4. It must expose clear rollback or fallback behavior.
5. It must be documented with source references.

## V2 sequencing note

Do not start implementation from the copilot or dashboard layers first. The correct order is:

1. audit and provenance
2. outcome capture
3. evidence-backed scoring
4. graph and learning loops
5. copilot and dashboards

That order keeps the V2 platform honest.
