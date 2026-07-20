---
title: "Frontend Architecture"
document_id: "07_frontend_architecture"
domain: "frontend"
feature: "frontend architecture"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - frontend
  - nextjs
---

# Frontend Architecture

The CareerOS frontend is a Next.js App Router application under `frontend/src/app` with feature components under `frontend/src/components`, API helper modules under `frontend/src/lib`, hooks under `frontend/src/hooks`, and shared types under `frontend/src/types`.

## Page Inventory

- `frontend/src/app/page.tsx`
- `frontend/src/app/account/page.tsx`
- `frontend/src/app/approvals/page.tsx`
- `frontend/src/app/coach/page.tsx`
- `frontend/src/app/command-center/page.tsx`
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/demo-rag/page.tsx`
- `frontend/src/app/evaluation/page.tsx`
- `frontend/src/app/forgot-password/page.tsx`
- `frontend/src/app/interview/page.tsx`
- `frontend/src/app/jobs/page.tsx`
- `frontend/src/app/jobs/alerts/page.tsx`
- `frontend/src/app/jobs/library/page.tsx`
- `frontend/src/app/knowledge/page.tsx`
- `frontend/src/app/login/page.tsx`
- `frontend/src/app/opportunities/page.tsx`
- `frontend/src/app/ops/page.tsx`
- `frontend/src/app/orchestration/page.tsx`
- `frontend/src/app/orchestration/governance/page.tsx`
- `frontend/src/app/orchestration/history/page.tsx`
- `frontend/src/app/orchestration/live/page.tsx`
- `frontend/src/app/orchestration/traces/page.tsx`
- `frontend/src/app/packages/page.tsx`
- `frontend/src/app/preferences/page.tsx`
- `frontend/src/app/rerank/page.tsx`
- `frontend/src/app/reset-password/page.tsx`
- `frontend/src/app/roadmap/page.tsx`
- `frontend/src/app/skill-graph/page.tsx`
- `frontend/src/app/workflow/alignment-report/[runId]/page.tsx`

## API Client Pattern

Frontend components primarily call `fetch` against `NEXT_PUBLIC_API_URL` or `/api/v1`. Authentication tokens are read from local storage or cookies depending on the component. The demo RAG API helper in `frontend/src/lib/demo-rag.ts` requires a token before calling `/demo-rag/chat`.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `frontend/src/app`
- `frontend/src/components`
- `frontend/src/lib/demo-rag.ts`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
