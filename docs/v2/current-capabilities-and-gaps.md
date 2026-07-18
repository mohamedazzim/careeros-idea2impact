# CareerOS V2 Current Capabilities and Gaps

Last verified from source code: 2026-06-20

This document summarizes what the current codebase really can do today, what it only approximates, and where `insufficient_data` or fallback behavior is the honest answer.

## Capability matrix

| Area | What is real today | Real data source | Fallback / insufficient-data behavior | Main gap |
|---|---|---|---|---|
| Resume upload and retrieval | Resume storage, versioning, chunking, and retrieval are implemented | `resumes`, `resume_versions`, `resume_chunks`, Qdrant | Masking and processing fall back to safer pipeline steps | Stronger evidence linkage across resume claims and downstream scores |
| Job refresh and matching | Jobs are ingested, refreshed, ranked, and displayed | TheirStack / job refresh pipeline, `jobs`, `job_matches` | Stale jobs and quota/provider failures are handled with diagnostics | More explainable matching formulas and calibration history |
| Opportunity alerting | Delivery pipeline exists with duplicate suppression and provider health checks | `communication_requests`, `voice_sessions`, `notification_history` | Blocked if missing config, duplicate, or dry-run | Better normalized provider payloads and richer audit trail |
| Conversational outbound calls | ConvAI-style conversation-agent delivery is supported in code | Opportunity context, voice provider wrappers | Rejected when config is missing or collision is detected | Still needs more runtime proof and richer transcript confidence |
| Outcome intelligence | Conversation, lifecycle, memory, and funnel metrics exist | Outcome tables, communication records, application events | If not enough events exist, metrics can be sparse or zero-like | Needs more long-lived event collection for trustworthy analytics |
| Learning resource discovery | Seeded curated resources plus live GitHub / YouTube / web discovery | `learning_resources`, provider discovery, caches | Falls back to verified curated resources when live search fails | No real completion/outcome feedback loop yet |
| Learning path generation | Skill-gaps are converted into learning paths and items | Job gaps, resources, `user_skill_learning_paths`, `learning_path_items` | Path generation can mark resources as not available when needed | Needs completion telemetry and evidence-cited recommendations |
| Learning outcome tracking | Open/start/progress/complete/abandon/feedback writes learning sessions, resource feedback, resource outcomes, and activity events | `learning_sessions`, `resource_feedback`, `resource_outcomes`, `learning_activity_events`, `career_events` | Returns `insufficient_data` when starts and feedback are both absent | Needs longer-lived activity volume for stronger outcome analytics |
| Skill graph schema and import dashboard | Evidence-backed skill graph nodes, aliases, edges, evidence rows, import runs, and user states are implemented | `skill_graph_nodes`, `skill_graph_aliases`, `skill_graph_edges`, `skill_graph_evidence`, `skill_graph_import_runs`, `user_skill_states` | Import dashboard can show empty or partial graph data until enough signals are collected | Needs richer evidence volume for downstream gap reasoning |
| Evidence-backed skill gap engine | Analysis runs, findings, evidence rows, and snapshots are implemented | `skill_gap_analysis_runs`, `skill_gap_findings`, `skill_gap_finding_evidence`, `user_skill_gap_snapshots` | Returns `insufficient_data` or legacy heuristics when evidence is thin | Needs broader calibration and source coverage across longer histories |
| GitHub project discovery | Template/starter/project search is implemented | GitHub Search API, Redis cache | Anonymous public search fallback if token is absent | Quality signals are heuristic, not authoritative |
| Docs-RAG chatbot | Docs can be indexed and queried through a FastAPI endpoint | `docs/rag/*.md`, Qdrant, optional Make relay, local LLM fallback | Falls back to local generation if relay is unavailable | Still limited to what exists in docs/RAG corpus |
| Roadmap progress | Roadmap tasks and progress are stored and displayed | `roadmaps`, `roadmap_goals`, `roadmap_tasks` | Missing telemetry is now labeled, not silently faked | Needs better analytics and more rigorous progress evidence |
| Observability | Metrics, logs, and tracing exist | Structured logs, LangSmith, OpenTelemetry-style middleware | LangSmith quotas can degrade gracefully | Still not a substitute for full product analytics |
| Governance and safety | Auth, rate limiting, prompt-injection and PII guards, MCP governance are present | Auth/session helpers, security modules, governance modules | Risk decisions can suppress or block actions | Needs stronger end-to-end evidence for some autonomous flows |

## Current fake / fallback / insufficient-data areas

| Area | Honest current label | Why |
|---|---|---|
| Roadmap telemetry | `not_tracked` when no real telemetry exists | The UI should not pretend default `0` values are real diagnostics |
| Learning discovery | `seeded_fallback` or provider-specific status | Seeded resources are verified, but they are still fallback content |
| Web / YouTube / GitHub trust | App-derived trust score | The platform does not get a universal external guarantee from those providers |
| GitHub project quality | Heuristic ranking | Stars and template signals are useful, but not proof of outcome quality |
| Outcome analytics | Sparse / partial until enough events accumulate | Many metrics depend on actual downstream behavior |
| Docs-RAG answers | `needs_verification` when context is weak or unavailable | The bot must not invent missing repository facts |
| Voice/call intelligence | Partial until transcript and turn data are present | A provider start event is not the same as a verified conversation |
| Personalization | Limited | It can use memory and preferences, but not a full long-horizon behavioral model yet |

## Real strengths already in the code

1. The platform has real persistence for jobs, resumes, learning, roadmap, and communication state.
2. The platform already uses provider health and fallback behavior rather than blind single-provider dependence.
3. The platform already stores many audit-style records that can become a real evidence graph in V2.
4. The platform already exposes a broad UI surface, so V2 can be layered on top instead of rebuilt from scratch.

## Key missing ingredients for V2

### 1. A single evidence graph

Today, evidence lives in many tables and services. V2 should unify:

- resume evidence
- job evidence
- learning evidence
- communication evidence
- roadmap evidence
- outcome evidence
- skill graph evidence

### 2. Stable lifecycle metrics

Many analytics surfaces depend on event volume. V2 needs:

- explicit event schemas
- consistent provenance fields
- enough historical data to stop using zero-like defaults as a stand-in for real telemetry

### 3. Implemented learning outcome tracking

M3 is now implemented end to end. The code records:

- resource open/start/progress/complete/abandon actions
- feedback submissions
- aggregate outcome rows for each resource
- activity events that can be replayed or audited later

The aggregate outcome service computes these stored fields:

- `started_count`
- `completion_count`
- `abandoned_count`
- `feedback_count`
- `average_rating`
- `completion_rate = completion_count / started_count`
- `drop_off_rate = abandoned_count / started_count`
- `recommendation_rate = recommend_count / feedback_count`
- `average_completion_percentage`
- `average_duration_seconds`

If `started_count == 0` and `feedback_count == 0`, the service returns `status="insufficient_data"` and the explanation says there is not enough learning activity yet.

The remaining gap is not feature absence. It is time and volume:

- more recorded sessions
- more feedback history
- more longitudinal outcomes tied to later career results

### 4. Implemented skill graph foundation

M4 is now implemented end to end. The code records:

- canonical skill nodes
- aliases and normalized aliases
- skill relationships / edges
- evidence rows per skill
- import run history
- per-user skill state snapshots

The current gap is downstream usage:

- more evidence sources
- stronger calibration of edge weights
- broader validation of evidence-backed skill gap analysis across long-lived user histories
- better UI for exploring the graph at scale

### 5. Stronger explainability for scores

Current scores are useful, but V2 should expose:

- formula
- evidence items
- confidence
- missing inputs
- versioning

### 6. A more durable copilot memory

The current memory stack is promising but incomplete. V2 should build a stable candidate/career memory graph from stored activity rather than from transient prompts.

## What can already be trusted

These parts of the codebase are already grounded in real stored data:

- uploaded resumes and versions
- job refresh results
- learning resource seeds and live discovery results
- roadmap task completion
- communication request and voice session records
- orchestration session and event records

Those are good inputs for V2.

## What should still return `insufficient_data`

Use `insufficient_data` rather than a fabricated answer when:

- there are no matching lifecycle events for an analytics question
- there is no learning completion signal yet
- a score cannot be tied to evidence
- the RAG corpus does not contain the requested answer
- a provider lookup fails and there is no verified fallback answer

That rule is central to V2 quality.
