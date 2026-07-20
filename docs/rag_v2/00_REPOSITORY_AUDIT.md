---
title: "CareerOS Repository Audit"
document_id: "00_repository_audit"
domain: "repository"
feature: "source audit"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - audit
  - traceability
---

# CareerOS Repository Audit

CareerOS is a full-stack career operations platform implemented as a FastAPI backend, Next.js frontend, PostgreSQL persistence layer, Redis runtime layer, and Qdrant vector retrieval layer. This audit is based on repository evidence, not legacy documentation. The evidence scan found 213 backend route decorators, 87 ORM model classes, 256 settings fields, 29 frontend page files, and 18 legacy RAG documents.

## Repository Structure And Applications

- `backend/src/main.py` creates the FastAPI app, registers middleware, validates production configuration, and includes routers.
- `backend/src/api/v1/endpoints/` contains API route modules for auth, jobs, opportunities, knowledge, packages, interview, RAG, orchestration, learning, skill graph, approvals, observability, and more.
- `backend/src/models/` contains SQLAlchemy ORM models for users, resumes, knowledge documents, jobs, matches, applications, voice sessions, conversations, learning, orchestration, approvals, and outcome intelligence.
- `frontend/src/app/` is a Next.js App Router application with dashboard, jobs, opportunities, knowledge, packages, interview, coach, roadmap, RAG demo, orchestration, command center, approvals, and account pages.

## Detected Technology Stack

| Layer | Evidence-backed stack | Status |
| --- | --- | --- |
| Frontend | Next.js, React, TypeScript | IMPLEMENTED |
| Backend | FastAPI, Pydantic, SQLAlchemy async, Alembic | IMPLEMENTED |
| Database | PostgreSQL via `DATABASE_URL` | IMPLEMENTED |
| Queue/cache | Redis and ARQ worker modules | IMPLEMENTED |
| Vector store | Qdrant async client, cosine vectors, 4096 dimensions | IMPLEMENTED |
| Embeddings | NVIDIA NV-Embed | IMPLEMENTED; external credential required |
| LLM | Gemini 2.5 Flash primary and DeepSeek NIM fallback | IMPLEMENTED; external credentials required |
| Voice | ElevenLabs ConvAI outbound-call service only; older ElevenLabs/Twilio wrappers are supporting or legacy-adjacent surfaces | PARTIALLY_IMPLEMENTED |

## Feature To File Mapping

| Domain | Feature | Documentation File | Frontend Source | Backend Source | Database Source | Integration Source | Tests | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| auth | Authentication and profile | `docs/rag_v2/11_AUTHENTICATION_AUTHORIZATION_AND_SECURITY.md` | frontend/src/components/LoginView.tsx; frontend/src/app/login/page.tsx | backend/src/api/v1/endpoints/auth.py | backend/src/models/user.py | JWT cookies/Bearer token | backend/tests/security/test_auth_flow.py | IMPLEMENTED |
| knowledge | Resume and Knowledge Hub upload | `docs/rag_v2/17_RESUME_AND_COVER_LETTER_WORKFLOWS.md` | frontend/src/components/KnowledgeHub.tsx; frontend/src/app/knowledge/page.tsx | backend/src/api/v1/endpoints/knowledge.py | backend/src/models/knowledge.py; backend/src/models/resume.py | Qdrant careernos_resumes through embedding service | backend/tests/test_resumes_api.py; backend/tests/test_demo_rag.py | IMPLEMENTED |
| jobs | Job refresh and provider ingestion | `docs/rag_v2/16_JOB_DISCOVERY_MATCHING_AND_ELIGIBILITY.md` | frontend/src/components/JobsIntelligenceView.tsx; frontend/src/app/jobs/page.tsx | backend/src/api/v1/endpoints/jobs.py; backend/src/workers/tasks/job_ingestion.py | backend/src/models/jobs.py | TheirStack API; Qdrant job vectors | backend/tests/test_theirstack_sync_service.py; backend/tests/test_jobs_refresh_diagnostics.py | IMPLEMENTED |
| matching | Resume-centric job matching | `docs/rag_v2/16_JOB_DISCOVERY_MATCHING_AND_ELIGIBILITY.md` | frontend/src/components/JobsIntelligenceView.tsx | backend/src/services/opportunity/job_intelligence_service.py | backend/src/models/jobs.py::JobMatch | LLM-free deterministic scoring | backend/tests/test_opportunity_match_engine.py; backend/tests/test_job_api_filtering.py | IMPLEMENTED |
| eligibility | India and tech-role eligibility | `docs/rag_v2/16_JOB_DISCOVERY_MATCHING_AND_ELIGIBILITY.md` | frontend/src/components/JobLibraryView.tsx | backend/src/integrations/theirstack/sync_service.py; backend/src/services/job_location_filter.py; backend/src/services/job_role_filter.py | backend/src/models/jobs.py::Job | TheirStack normalized job data | backend/tests/test_india_location_filter.py; backend/tests/test_job_role_filter.py | IMPLEMENTED |
| packages | Tailored resume, cover letter, outreach, interview guide | `docs/rag_v2/17_RESUME_AND_COVER_LETTER_WORKFLOWS.md` | frontend/src/components/ApplicationPackagesView.tsx; frontend/src/app/packages/page.tsx | backend/src/api/v1/endpoints/packages.py | backend/src/models/package.py | Gemini primary with DeepSeek fallback | backend/tests/test_package_schema.py | IMPLEMENTED |
| interview | Interview preparation and practice | `docs/rag_v2/18_INTERVIEW_PREPARATION.md` | frontend/src/components/InterviewCoachView.tsx; frontend/src/app/interview/page.tsx | backend/src/api/v1/endpoints/interview.py; backend/src/services/interview/* | backend/src/models/interview.py | WebSocket realtime path; LLM provider | backend/tests/test_phase7_interview.py; backend/tests/interview/test_websocket_lifecycle.py | IMPLEMENTED |
| demo_rag | Mentor/docs RAG chatbot | `docs/rag_v2/12_RAG_AND_MENTOR_CHATBOT.md` | frontend/src/components/rag/*; frontend/src/app/demo-rag/page.tsx | backend/src/api/v1/endpoints/demo_rag.py; backend/src/services/rag/service.py | Qdrant collection only; no SQL table for docs-RAG chunks | Qdrant, NVIDIA NV-Embed, Gemini/DeepSeek, optional Make.com | backend/tests/test_demo_rag.py | IMPLEMENTED |
| orchestration | Agent orchestration and governance | `docs/rag_v2/13_AGENTS_PROMPTS_AND_LLM_WORKFLOWS.md` | frontend/src/components/CommandCenterView.tsx; frontend/src/app/orchestration/page.tsx | backend/src/api/v1/endpoints/orchestration.py; backend/src/services/orchestration/* | backend/src/models/orchestration.py; backend/src/models/approvals.py | Redis, graph modules, MCP router | backend/tests/test_orchestration.py; backend/tests/test_agent_governance.py | PARTIALLY_IMPLEMENTED |
| voice | ElevenLabs ConvAI outbound voice agent | `docs/rag_v2/14_ELEVENLABS_VOICE_AGENT.md` | frontend/src/components/OpportunityCenterView.tsx; frontend/src/components/JobsIntelligenceView.tsx | backend/src/api/v1/endpoints/opportunities_api.py::trigger_opportunity_alert; backend/src/services/opportunity/conversational_outbound_call_service.py | backend/src/models/jobs.py::VoiceSession; backend/src/models/outcome_intelligence.py | ElevenLabs ConvAI only; Twilio/Pipedream are external plumbing, not alternate voice-agent implementations | backend/tests/test_call_safety.py; backend/tests/test_agent_governance.py | PARTIALLY_IMPLEMENTED |
| make | Make.com docs RAG relay | `docs/rag_v2/19_WORKFLOW_AUTOMATION_AND_MAKE_COM.md` | frontend/src/app/demo-rag/page.tsx | backend/src/services/rag/service.py::_relay_to_make | None | MAKE_RAG_WEBHOOK_URL; MAKE_RAG_API_KEY | backend/tests/test_demo_rag.py | PARTIALLY_IMPLEMENTED |
| pipedream | Pipedream communication bridge | `docs/rag_v2/19_WORKFLOW_AUTOMATION_AND_MAKE_COM.md` | frontend provider health display | backend/src/services/opportunity/pipedream_adapter.py; backend/src/services/opportunity/conversational_outbound_call_service.py | backend/src/models/jobs.py::CommunicationRequest | PIPEDREAM_WEBHOOK_URL | backend/tests/test_call_safety.py | PARTIALLY_IMPLEMENTED |
| twilio | Twilio MCP and call reconciliation | `docs/rag_v2/20_EXTERNAL_INTEGRATIONS.md` | frontend/src/types/index.ts; provider health pages | backend/src/services/mcp/twilio_adapter.py; backend/src/services/mcp/twilio_mcp_service.py; backend/src/services/opportunity/twilio_reconciliation.py | backend/src/models/jobs.py::VoiceOutcome | Twilio REST API and MCP wrapper | backend/tests/test_twilio_mcp.py | PARTIALLY_IMPLEMENTED |
| learning | Learning paths and skill gaps | `docs/rag_v2/03_COMPLETE_FEATURE_CATALOG.md` | frontend/src/components/learning/* | backend/src/api/v1/endpoints/learning.py; backend/src/api/v1/endpoints/skill_gaps.py | backend/src/models/learning.py; backend/src/models/skill_gap.py | YouTube/GitHub/web search providers | backend/tests/test_learning_paths.py; backend/tests/test_skill_gap_engine.py | IMPLEMENTED |

## Incomplete Or Suspicious Modules

- `backend/src/services/vector_store/manager.py` initializes only three collections, while `backend/src/services/vector_store/qdrant_service.py` supports `job_opportunities` and `careeros_rag_docs` too. Status: `DUPLICATE_IMPLEMENTATION`.
- `backend/src/api/v1/endpoints/opportunities_api.py::trigger_opportunity_alert` records `mcp_tool_used="twilio.make_call"` when a phone number exists, but the delivery path in `CommunicationOrchestrator` uses `elevenlabs_convai`. Treat this as a stale label; RAG answers should describe the supported voice path as ConvAI only.
- `backend/src/services/opportunity/elevenlabs_transcript_sync.py` can scan and retrieve transcripts, but no inbound ElevenLabs webhook endpoint was found. Status: `PARTIALLY_IMPLEMENTED`.
- Provider catalog names RemoteOK, Arbeitnow, Adzuna, USAJobs, Greenhouse, and Lever, but inspected real sync code centers on TheirStack. Status: `CONFIGURED_BUT_NOT_USED`.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `docs/rag_audit_evidence.json`
- `backend/src/main.py`
- `backend/src/core/config.py`
- `backend/src/services/opportunity/conversational_outbound_call_service.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
