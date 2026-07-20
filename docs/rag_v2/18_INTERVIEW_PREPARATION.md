---
title: "Interview Preparation"
document_id: "18_interview_preparation"
domain: "interview"
feature: "interview coach"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - interview
  - coach
  - websocket
---

# Interview Preparation

CareerOS interview preparation includes session start, response handling, pause/resume, interruption, replay, kill, history, memory, end/report, delete, intelligence, health, and websocket lifecycle routes. The frontend includes `InterviewCoachView` and supporting interview components.

## API Surface

The interview router exposes lifecycle endpoints through `backend/src/api/v1/endpoints/interview.py`. It coordinates interview services, memory, reports, and realtime session behavior. Tests cover phase-seven interview behavior and websocket lifecycle paths.

## Implementation Boundary

The repository contains browser audio and realtime structures, but actual provider behavior depends on runtime configuration and external services. The system should be described as implemented for interview session orchestration and partially provider-dependent for live speech components.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/api/v1/endpoints/interview.py`
- `backend/src/services/interview`
- `backend/src/graphs/interview_graph.py`
- `backend/src/models/interview.py`
- `frontend/src/components/InterviewCoachView.tsx`
- `frontend/src/components/interview`
- `backend/tests/test_phase7_interview.py`
- `backend/tests/interview/test_websocket_lifecycle.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
