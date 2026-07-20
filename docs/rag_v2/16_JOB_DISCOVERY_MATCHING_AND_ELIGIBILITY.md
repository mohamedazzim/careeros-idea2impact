---
title: "Job Discovery Matching And Eligibility"
document_id: "16_job_discovery_matching_and_eligibility"
domain: "jobs"
feature: "jobs matching eligibility"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - jobs
  - matching
  - theirstack
---

# Job Discovery, Matching, And Eligibility

CareerOS job intelligence combines real provider ingestion, deterministic matching, provider diagnostics, and application workflow status. The verified provider implementation is TheirStack. The matching engine scores stored jobs against resume evidence and returns explanations, missing skills, and priority signals.

## Provider Refresh

`POST /api/v1/jobs/refresh` starts `JobRefreshService.start_refresh`, which creates an orchestration session and enqueues refresh work. TheirStack sync builds resume-driven payloads, applies India and tech-role filters, handles preview and billing-blocked responses, can fall back to broader queries, normalizes returned jobs, and upserts job data.

## Matching Dimensions

`JobIntelligenceService` uses deterministic dimensions for education, skills, projects, experience, certifications, location, keywords, and semantic evidence. The current skill alias table covers Python, SQL, Power BI, machine learning, AI, GenAI, TensorFlow, PyTorch, pandas, numpy, matplotlib, NLP, FastAPI, Django, Docker, and Excel. Domain mismatch can cap the score at 15. Opportunity priority blends match, freshness, provider confidence, salary, and apply URL completeness.

## Eligibility Meaning

Eligibility in the inspected code means suitability for the candidate and configured job market filters. It does not verify legal work authorization, immigration status, or employer-specific visa sponsorship.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/api/v1/endpoints/jobs.py`
- `backend/src/services/job_refresh.py`
- `backend/src/integrations/theirstack/sync_service.py`
- `backend/src/services/opportunity/job_intelligence_service.py`
- `backend/src/services/job_location_filter.py`
- `backend/src/services/job_role_filter.py`
- `frontend/src/components/JobsIntelligenceView.tsx`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
