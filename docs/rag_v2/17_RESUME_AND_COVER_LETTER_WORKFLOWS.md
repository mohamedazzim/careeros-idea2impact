---
title: "Resume And Cover Letter Workflows"
document_id: "17_resume_and_cover_letter_workflows"
domain: "documents"
feature: "resume package generation"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - resume
  - cover-letter
  - packages
---

# Resume And Cover Letter Workflows

CareerOS supports resume/knowledge upload, text extraction, analysis, vector indexing, package generation, regeneration, and download. PDF extraction uses PyMuPDF and DOCX extraction uses python-docx when base64 file content is supplied.

## Resume Upload And Analysis

`POST /knowledge/upload` validates content, creates a knowledge document, and starts real analysis when possible. The analysis path can mask PII, chunk resume text with a 1000 character size and 200 character overlap, embed chunks, write synthetic resume rows, upsert Qdrant resume vectors, and run resume analysis plus optional alignment.

## Application Package Generation

`POST /api/v1/packages/generate` creates tailored application assets for a job. The implementation asks the LLM provider for structured `PackageContent`, validates the schema, and falls back to deterministic content when evidence is sparse or LLM output fails validation. Package records store tailored resume, cover letter, outreach message, and interview guide content as JSON strings.

## Operational Notes

The upload analysis uses an in-process `asyncio.create_task`, so work can be lost on process exit unless moved to a durable worker. Package quality depends on resume/job evidence density and model availability.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/api/v1/endpoints/knowledge.py`
- `backend/src/api/v1/endpoints/packages.py`
- `backend/src/models/knowledge.py`
- `backend/src/models/resume.py`
- `backend/src/models/package.py`
- `backend/src/services/resume`
- `frontend/src/components/KnowledgeHub.tsx`
- `frontend/src/components/ApplicationPackagesView.tsx`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
