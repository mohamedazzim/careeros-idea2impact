---
title: "Glossary"
document_id: "27_glossary"
domain: "reference"
feature: "terms"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - glossary
---

# Glossary

- Application package: generated tailored resume, cover letter, outreach message, and interview guide for a job.
- CommunicationRequest: persisted request to deliver an opportunity alert through email, SMS, voice, or webhook-style channel.
- ConvAI: ElevenLabs conversational AI product used for outbound opportunity calls.
- Docs-RAG: CareerOS mentor chatbot over repository documentation.
- Dynamic variables: context fields passed to ElevenLabs so the external agent can personalize a call.
- Eligibility: repository-level job suitability and filter logic, not legal work authorization.
- Golden question: a canonical question and answer used to validate retrieval quality.
- Opportunity priority score: blended score using match, freshness, provider confidence, salary, and apply URL completeness.
- Provider bridge: an external webhook workflow, currently Pipedream for voice bridge or Make.com for docs-RAG relay.
- VoiceSession: CareerOS row tracking an outbound voice interaction lifecycle.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/models/jobs.py`
- `backend/src/models/outcome_intelligence.py`
- `backend/src/services/rag/service.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
