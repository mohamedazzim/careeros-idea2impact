---
title: "CareerOS Product Overview"
document_id: "01_product_overview"
domain: "product"
feature: "overview"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - product
  - overview
---

# CareerOS Product Overview

CareerOS is a career operations platform for candidates who want to turn resume evidence into job discovery, job matching, application package generation, interview preparation, learning guidance, and governed opportunity alerts. The implemented product combines a Next.js dashboard with FastAPI APIs, PostgreSQL records, Qdrant vector search, Gemini/DeepSeek LLM calls, NVIDIA embeddings, TheirStack job ingestion, and optional voice/webhook integrations.

## What Problem CareerOS Solves

CareerOS solves the practical gap between having a resume and running a repeatable career workflow. The application lets a user upload resume/profile evidence, extract searchable text, index chunks, discover India-focused technical jobs, calculate deterministic match and gap scores, generate tailored application assets, practice interviews, and view opportunity intelligence.

## Target Users

The primary implemented user is an authenticated candidate. Admin and operator concepts appear through role schemas, audit logs, health checks, approvals, and command-center pages, but the main connected end-to-end workflows are candidate workflows.

## Implemented Product Surface

| Product area | Status | Evidence |
| --- | --- | --- |
| Authenticated account and profile | IMPLEMENTED | `backend/src/api/v1/endpoints/auth.py`, `frontend/src/components/LoginView.tsx` |
| Resume and Knowledge Hub upload | IMPLEMENTED | `backend/src/api/v1/endpoints/knowledge.py`, `frontend/src/components/KnowledgeHub.tsx` |
| Job refresh and job feed | IMPLEMENTED | `backend/src/api/v1/endpoints/jobs.py`, `backend/src/integrations/theirstack/sync_service.py` |
| Job matching and eligibility | IMPLEMENTED | `backend/src/services/opportunity/job_intelligence_service.py`, `backend/src/services/job_location_filter.py` |
| Application packages | IMPLEMENTED | `backend/src/api/v1/endpoints/packages.py`, `frontend/src/components/ApplicationPackagesView.tsx` |
| Interview preparation | IMPLEMENTED | `backend/src/api/v1/endpoints/interview.py`, `frontend/src/components/InterviewCoachView.tsx` |
| Mentor/docs RAG chatbot | IMPLEMENTED | `backend/src/services/rag/service.py`, `frontend/src/components/rag/*` |
| ElevenLabs outbound voice agent | PARTIALLY_IMPLEMENTED | `backend/src/services/opportunity/conversational_outbound_call_service.py` |

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/main.py`
- `frontend/src/app/dashboard/page.tsx`
- `backend/src/services/opportunity/job_intelligence_service.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
