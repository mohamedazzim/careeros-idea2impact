---
title: "End To End User Journeys"
document_id: "05_end_to_end_user_journeys"
domain: "product"
feature: "user journeys"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - journeys
---

# End-To-End User Journeys

## Journey: Upload Resume And Build Candidate Evidence

User signs in, opens Knowledge Hub, uploads a resume or profile document, and the frontend calls `POST /api/v1/knowledge/upload`. The backend extracts PDF/DOCX text when `file_base64` is supplied, rejects unextractable resume content, creates a `knowledge_docs` row, and starts `_run_real_analysis`. The background analysis masks PII when possible, chunks text with chunk size 1000 and overlap 200, embeds chunks through `EmbeddingService`, persists synthetic resume/resume-version/resume-chunk rows, upserts vectors into `careeros_resumes`, and stores analysis results on the knowledge document.

## Journey: Refresh Jobs And Calculate Matches

`POST /api/v1/jobs/refresh` creates an orchestration session and enqueues `enqueue_job_refresh`. The provider path uses TheirStack search payloads derived from resume skills, India market filters, tech-role hints, and provider credentials. Normalized jobs are upserted to `jobs`. Matching recalculates `job_matches`.

## Journey: Generate Application Package

`POST /api/v1/packages/generate` creates an `application_packages` row, resolves the job, gathers Knowledge Hub documents, calls Gemini/DeepSeek structured generation, validates `PackageContent`, and stores tailored resume, cover letter, outreach, and interview guide JSON.

## Journey: Trigger Voice Opportunity Alert

`POST /api/v1/opportunities/alert` validates ownership, builds an opportunity object, evaluates urgency, resolves a safe recipient phone number, creates orchestration/audit records, runs `OpportunityAlertAgent.evaluate_and_alert`, and can initiate an ElevenLabs ConvAI outbound call. This journey is `PARTIALLY_IMPLEMENTED` because no inbound ElevenLabs callback endpoint is present.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `frontend/src/components/KnowledgeHub.tsx`
- `frontend/src/components/JobsIntelligenceView.tsx`
- `frontend/src/components/ApplicationPackagesView.tsx`
- `frontend/src/components/OpportunityCenterView.tsx`
- `backend/src/api/v1/endpoints/opportunities_api.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
