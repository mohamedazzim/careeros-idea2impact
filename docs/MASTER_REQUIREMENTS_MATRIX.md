# CareerOS AI - Master Requirements Matrix

This matrix is an implementation tracking document, not a compliance certificate.
It is aligned with the current FastAPI + Next.js codebase and with [docs/ROADMAP.md](ROADMAP.md).

Last verified from source code: 2026-06-18

---

## Current Validation Summary

Overall status:

- Core platform: partially implemented and actively hardening
- Roadmap workflow: implemented, with telemetry and test gaps
- Verified learning paths: implemented, authenticated, and backed by real free resource URLs
- Job ingestion: implemented, with provider quota and degradation issues
- Conversational call flow: implemented but needs hardening before it should be described as fully reliable
- CI/deployment: verify current GitHub Actions before claiming readiness

---

## Technical Cross-Reference Matrix

| Req ID | Category | Description | Current Backend File(s) | Current Frontend File(s) | API Route(s) | DB Model / Table(s) | Tests / Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| REQ-01 | Foundation | Standard registered credentials upload and validation | `backend/src/api/v1/endpoints/auth.py`, `backend/src/api/deps.py`, `backend/src/services/security/auth.py` | `frontend/src/components/LoginView.tsx`, `frontend/src/app/login/page.tsx` | `POST /api/v1/auth/register`, `POST /api/v1/auth/login` | `users` | Auth coverage exists in backend test suites; runtime auth flows are core platform behavior | IMPLEMENTED |
| REQ-02 | Profile | PDF, DOCX, TXT, MD document ingest and parsing under 10MB limit | `backend/src/api/v1/endpoints/knowledge.py`, `backend/src/services/processing/*`, `backend/src/services/privacy/*`, `backend/src/services/embedding/*`, `backend/src/services/vector_store/qdrant_service.py` | `frontend/src/components/KnowledgeHub.tsx`, `frontend/src/app/knowledge/page.tsx` | `POST /api/v1/knowledge/upload`, `GET /api/v1/knowledge`, `GET /api/v1/knowledge/{doc_id}` | `knowledge_docs`, `resume_versions`, `resume_chunks` | `backend/tests/test_parser.py`, `backend/tests/test_processing_pipeline.py`, `backend/tests/test_masking_pipeline.py`, `backend/tests/test_vector_store.py` | IMPLEMENTED_NEEDS_HARDENING |
| REQ-03 | Profile | Pre-emptive personal identifiers masking | `backend/src/services/privacy/engine.py`, `backend/src/services/processing/pipeline.py` | `frontend/src/components/KnowledgeHub.tsx` | Masking occurs inside upload / processing pipeline | `knowledge_docs` payloads, masking audit data | `backend/tests/test_privacy_engine.py`, `backend/tests/test_masking_pipeline.py` | IMPLEMENTED |
| REQ-04 | Profile | Multi-tenant segregation validation checks | `backend/src/api/deps.py`, `backend/src/db/repositories/*`, `backend/src/services/security/*` | `frontend/src/middleware.ts`, role-gated pages | Authenticated APIs across the platform | `users`, `knowledge_docs`, `jobs`, `roadmaps`, and other user-scoped tables | Auth/RBAC behavior is covered across backend test suites | IMPLEMENTED |
| REQ-05 | RAG Platform | Chunk ingested text and embed it for vector search | `backend/src/services/processing/chunking.py`, `backend/src/services/embedding/orchestrator.py`, `backend/src/services/vector_store/qdrant_service.py` | `frontend/src/components/KnowledgeHub.tsx`, `frontend/src/components/DashboardView.tsx` | `POST /api/v1/knowledge/upload`, `POST /api/v1/knowledge/{doc_id}/analyze` | `knowledge_docs`, `resume_versions`, `resume_chunks` | `backend/tests/test_chunking_pipeline.py`, `backend/tests/test_embedding_preparation.py`, `backend/tests/test_nvembed.py`, `backend/tests/test_vector_store.py` | IMPLEMENTED_NEEDS_HARDENING |
| REQ-06 | Job Intelli | Pull and normalize active job feeds from external ATS boards | `backend/src/api/v1/endpoints/jobs.py`, `backend/src/services/jobs.py`, `backend/src/services/opportunity/job_intelligence_service.py` | `frontend/src/components/JobsIntelligenceView.tsx`, `frontend/src/app/jobs/page.tsx` | `POST /api/v1/jobs/refresh`, `GET /api/v1/jobs`, `GET /api/v1/jobs/stats` | `jobs`, `job_matches` | `backend/tests/test_job_api_filtering.py`, `backend/tests/test_theirstack_client.py`, `backend/tests/test_theirstack_slots.py` | IMPLEMENTED_NEEDS_HARDENING |
| REQ-07 | Job Intelli | Compare candidate profile skills vs job roles semantic indices | `backend/src/api/v1/endpoints/jobs.py`, `backend/src/services/opportunity/opportunity_discovery_agent.py`, `backend/src/services/opportunity/job_intelligence_service.py` | `frontend/src/components/JobsIntelligenceView.tsx`, `frontend/src/components/OpportunityCenterView.tsx` | `POST /api/v1/jobs/refresh`, `POST /api/v1/opportunities/discover`, `GET /api/v1/opportunities/list` | `jobs`, `job_matches`, `opportunity_scores` | `backend/tests/test_agent_scoring.py`, `backend/tests/test_opportunity_match_engine.py` | IMPLEMENTED |
| REQ-08 | Packaging | Construct optimized resume and cover letter based on selected job match | `backend/src/api/v1/endpoints/packages.py`, `backend/src/services/packages.py` | `frontend/src/components/ApplicationPackagesView.tsx`, `frontend/src/app/packages/page.tsx` | `POST /api/v1/packages/generate`, `GET /api/v1/packages`, `GET /api/v1/packages/{pkg_id}/download` | `generated_packages`, `package_versions` | `backend/tests/test_package_schema.py` | IMPLEMENTED |
| REQ-09 | Outbound | Generate outreach templates and outbound interview coaching guides | `backend/src/api/v1/endpoints/packages.py`, `backend/src/services/packages.py` | `frontend/src/components/ApplicationPackagesView.tsx` | `POST /api/v1/packages/generate` | `generated_packages`, `package_versions` | Package generation is covered indirectly by package tests; outbound-specific content should be verified in runtime demos | IMPLEMENTED_NEEDS_HARDENING |
| REQ-10 | HITL Center | Mandatory pending draft review gate for AI outreach content | `backend/src/api/v1/endpoints/approvals.py`, `backend/src/db/repositories/domain_repositories.py` | `frontend/src/components/HumanApprovalCenterView.tsx`, `frontend/src/app/approvals/page.tsx` | `GET /api/v1/approvals`, `POST /api/v1/approvals/{approval_id}/approve`, `POST /api/v1/approvals/{approval_id}/reject`, `POST /api/v1/approvals/{approval_id}/execute` | `approvals`, `approval_items`, `approval_comments`, `approval_notifications` | `backend/tests/test_phase3a_core.py`, approval flows are covered by broader platform tests | IMPLEMENTED |
| REQ-11 | HITL Center | Side-by-side diff modifications, review log, and comments thread | `backend/src/api/v1/endpoints/approvals.py` | `frontend/src/components/HumanApprovalCenterView.tsx` | `POST /api/v1/approvals/{approval_id}/comment`, `POST /api/v1/approvals/{approval_id}/edit` | `approvals`, `approval_comments` | UI exists; comment and edit behavior should be verified in demo coverage | IMPLEMENTED_NEEDS_HARDENING |
| REQ-12 | Coach | Launch live conversational interview sessions with transcript history | `backend/src/api/v1/endpoints/interview.py`, `backend/src/api/v1/endpoints/realtime.py`, `backend/src/services/interview/*` | `frontend/src/components/InterviewCoachView.tsx`, `frontend/src/app/coach/page.tsx`, `frontend/src/app/interview/page.tsx` | `POST /api/v1/interview/start`, `POST /api/v1/interview/respond`, WebSocket routes under `/api/v1/realtime/*` | `interview_sessions`, `interview_questions`, `interview_weakness_history` | `backend/tests/test_interview_session.py`, `backend/tests/test_interview_memory.py`, `backend/tests/test_interview_evaluation.py`, `backend/tests/test_interview_governance.py` | IMPLEMENTED |
| REQ-13 | Coach | Retrieve historical feedback and analyze candidate traits over time | `backend/src/api/v1/endpoints/interview.py`, `backend/src/services/interview/weakness_pattern_service.py` | `frontend/src/components/InterviewCoachView.tsx` | `GET /api/v1/interview/history`, `GET /api/v1/interview/memory`, `GET /api/v1/interview/report/{session_uid}` | `interview_sessions`, `interview_questions`, `interview_weakness_history` | `backend/tests/test_interview_weakness_patterns.py`, `backend/tests/test_interview_memory.py` | IMPLEMENTED |
| REQ-14 | MCP Agents | LinkedIn post previews, scheduling logs, and status checks | `backend/src/api/v1/endpoints/mcp.py`, `backend/src/services/mcp/mcp_router.py`, `backend/src/services/mcp/mcp_observability.py` | `frontend/src/components/CommandCenterView.tsx` and related ops surfaces | `POST /api/v1/mcp/test` | `mcp_execution_logs` | `backend/tests/test_mcp.py`, `backend/tests/test_mcp_router.py` | PARTIAL |
| REQ-15 | MCP Agents | Initiate outbound dialer and voice call simulations | `backend/src/services/opportunity/communication_orchestrator.py`, `backend/src/services/opportunity/conversational_outbound_call_service.py`, `backend/src/services/mcp/mcp_router.py` | No dedicated frontend control; surfaced indirectly in opportunity / ops flows | Internal delivery path via conversational call orchestration | `communication_requests` and opportunity/outcome tracking tables | `backend/tests/test_call_safety.py`, `backend/tests/test_call_alert_threshold.py`, `backend/tests/test_phase8_voice_runtime.py` | IMPLEMENTED_NEEDS_HARDENING |
| REQ-16 | Roadmap | Sequential multi-stage education steps constructed via target profiling | `backend/src/api/v1/endpoints/roadmaps.py`, `backend/src/services/strategy/roadmap_generation_service.py`, `backend/src/models/roadmap.py` | `frontend/src/components/CareerRoadmapView.tsx`, `frontend/src/app/roadmap/page.tsx` | `GET /api/v1/roadmaps`, `GET /api/v1/roadmaps/{roadmap_id}`, `POST /api/v1/roadmaps/generate`, `POST /api/v1/roadmaps/regenerate`, `PATCH /api/v1/roadmaps/tasks/{task_id}`, `GET /api/v1/roadmaps/progress` | `roadmaps`, `roadmap_goals`, `roadmap_tasks` | `backend/tests/test_phase3a_core.py`, roadmap behavior is verified through runtime and API tests; deterministic fallback labels and telemetry honesty are now covered in `backend/tests/test_roadmaps_telemetry.py` | IMPLEMENTED_NEEDS_HARDENING |
| REQ-17 | Roadmap | Progress tracking and milestone refresh from stored roadmap tasks | `backend/src/api/v1/endpoints/roadmaps.py`, `backend/src/models/roadmap.py` | `frontend/src/components/CareerRoadmapView.tsx` | `GET /api/v1/roadmaps/progress`, `PATCH /api/v1/roadmaps/tasks/{task_id}` | `roadmaps`, `roadmap_goals`, `roadmap_tasks` | `backend/tests/test_phase3a_core.py`, `backend/tests/test_roadmaps_telemetry.py`, `backend/tests/test_job_api_filtering.py` (indirectly adjacent) | IMPLEMENTED_NEEDS_HARDENING |
| REQ-17A | Learning | GitHub project/repo discovery for missing skills | `backend/src/api/v1/endpoints/learning.py`, `backend/src/services/learning/github_project_service.py`, `backend/src/integrations/github/repo_discovery.py` | `frontend/src/components/learning/GitHubProjectsPanel.tsx`, `frontend/src/components/JobsIntelligenceView.tsx` | `GET /api/v1/learning/github-projects`, `POST /api/v1/learning/github-projects/refresh` | none | `backend/tests/test_learning_github_projects.py`, `backend/tests/test_learning_paths.py` (skill normalization) | IMPLEMENTED_NEEDS_HARDENING |
| REQ-18 | Evaluation | Retrieval metrics calculation and reranker comparison | `backend/src/api/v1/endpoints/evaluation.py`, `backend/src/services/evaluation/*`, `backend/src/services/reranking/*` | `frontend/src/components/EvaluationView.tsx`, `frontend/src/app/evaluation/page.tsx` | `POST /api/v1/eval/benchmark`, `GET /api/v1/eval/runs`, `GET /api/v1/eval/runs/{run_id}/progress` | `evaluation_runs`, `hallucination_audits`, `rerank_runs` | `backend/tests/test_evaluation.py`, `backend/tests/test_retrieval.py`, `backend/tests/test_vector_store.py` | IMPLEMENTED |
| REQ-19 | Evaluation | Fact-check diagnostics comparator and hallucination checks | `backend/src/api/v1/endpoints/evaluation.py`, `backend/src/services/intelligence/hallucination_guard.py` | `frontend/src/components/EvaluationView.tsx` | `POST /api/v1/eval/hallucination/detect` | `evaluation_runs`, `hallucination_audits` | `backend/tests/test_evaluation.py` | IMPLEMENTED_NEEDS_HARDENING |
| REQ-20 | Operational | Circuit health monitoring, simulated outages, graceful queues | `backend/src/api/health.py`, `backend/src/api/v1/endpoints/troubleshoot.py`, `backend/src/observability/*`, `backend/src/workers/*` | `frontend/src/components/OpsCenterView.tsx`, `frontend/src/app/ops/page.tsx` | `GET /api/health/live`, `GET /api/health/ready`, `GET /api/health/deep`, `GET /api/health/detailed`, `GET /api/v1/troubleshoot/circuits` | `circuit_states`, `audit_logs`, `pending_jobs` | `backend/tests/test_health.py`, `backend/tests/test_arq_worker.py`, `backend/tests/verify_routes.py` | IMPLEMENTED_NEEDS_HARDENING |

---

## Requirement Gap Summary

| Area | Current Status | Main Gap | Next Action |
|---|---|---|---|
| Conversational outbound call flow | Implemented but not fully hardened | Two-way agent behavior, listen/stop timing, and early-ending call behavior still need runtime confirmation | Keep validating the ElevenLabs conversational path and its end-to-end call lifecycle |
| Duplicate call suppression | Needs hardening | Concurrency / duplicate execution risk remains in outbound orchestration and provider retries | Verify guardrails in `backend/src/services/mcp/mcp_governance.py` and the communication orchestrator |
| TheirStack provider handling | Implemented with provider risk | 402 / quota / slot-exhaustion behavior needs explicit runtime verification across all slots | Confirm graceful fallback and quota surfacing in job ingestion tests |
| LangSmith tracing quota | Needs verification | Tracing can be enabled, but quota / 429 handling is not proven as a stable production invariant | Confirm degraded behavior when LangSmith rate limits or is unavailable |
| Roadmap analytics | Implemented but needs hardening | Timing metrics are now labeled `not_tracked` instead of defaulting to zero | Persist real generation / refresh telemetry before claiming strong observability |
| Roadmap fallback and progress tests | Implemented and hardened | Generation fallback, stale detection, partial evidence, and null telemetry are now covered in `backend/tests/test_roadmaps_telemetry.py` | Extend only if the API contract changes again |

---

## Deprecated / Stale Claims Removed

| Old claim style | Current truth |
|---|---|
| `100.0% Fully Met` | This is not a final compliance certificate |
| `server.ts`, `server/db.ts`, `server/jobs.ts` | Replaced by current FastAPI / Next.js paths |
| `knowledgeDocs`, `jobMatches`, `roadmapTasks` | Replaced by actual model/table names such as `knowledge_docs`, `job_matches`, `roadmap_tasks` |
| `roadmap_agent.ts` | Replaced by `backend/src/api/v1/endpoints/roadmaps.py` and `backend/src/services/strategy/roadmap_generation_service.py` |
| Overconfident `IMPLEMENTED` everywhere | Replaced with `PARTIAL`, `IMPLEMENTED_NEEDS_HARDENING`, and `NEEDS_TESTS` where appropriate |

---

## Notes on Roadmap Alignment

The roadmap workflow is intentionally documented in [docs/ROADMAP.md](ROADMAP.md).
This matrix only tracks the broader requirement surface and keeps older PRD claims honest against the current codebase.

The following roadmap truths remain in force:

- Roadmap list, details, generation, task toggle, and progress aggregation exist.
- Generation is hybrid: persisted evidence + preferences + LLM + deterministic fallback.
- Some analytics fields remain explicitly `not_tracked` until persisted.
- No separate always-on autonomous recalculation service is verified.
- Progress is aggregated from stored goals/tasks and refreshed by UI/API.

---

## Validation Notes

- Route evidence should continue to be checked against `backend/src/main.py` and the FastAPI router files.
- Frontend references should continue to use current App Router paths under `frontend/src/app/`.
- If a claim cannot be tied to source code or runtime evidence, mark it as `NEEDS_TESTS` or `STALE_DOC_CLAIM`.
