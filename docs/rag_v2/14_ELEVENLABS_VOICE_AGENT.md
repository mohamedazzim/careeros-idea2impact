---
title: "ElevenLabs Voice Agent"
document_id: "14_elevenlabs_voice_agent"
domain: "voice"
feature: "outbound opportunity calls"
audience:
  - user
  - developer
  - operator
implementation_status: "PARTIALLY_IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - voice
  - elevenlabs
  - convai
  - outbound
---

# ElevenLabs Voice Agent

The only supported CareerOS opportunity voice-agent path is ElevenLabs Conversational AI (ConvAI). It starts from `POST /api/v1/opportunities/alert`, flows through `OpportunityAlertAgent`, uses `CommunicationOrchestrator.deliver`, and then calls `ElevenLabsConversationalOutboundCallService.initiate_call` for `VOICE_CALL` delivery. CareerOS should document and operate this as ConvAI only; Twilio and Pipedream are not separate in-app voice-agent implementations.

The direct provider call is the ElevenLabs ConvAI outbound-call API. If a webhook bridge is configured, it is still a bridge into the same ConvAI outbound-call payload, not a separate Pipedream voice agent. Twilio is external telephony wiring behind the ElevenLabs ConvAI phone-number setup and is not the app-owned call orchestration path.

## Call Initiation Flow

```mermaid
sequenceDiagram
  participant FE as Frontend opportunity alert
  participant API as /api/v1/opportunities/alert
  participant Alert as OpportunityAlertAgent
  participant Comm as CommunicationOrchestrator
  participant Voice as ElevenLabsConversationalOutboundCallService
  participant EL as ElevenLabs ConvAI
  FE->>API: user_id, job/opportunity context, channels
  API->>Alert: evaluate_and_alert
  Alert->>Comm: deliver VOICE_CALL request
  Comm->>Comm: skip generic webhook for voice_call_uses_conversational_transport
  Comm->>Voice: initiate_call(context, recipient)
  Voice->>Voice: validate recipient, reject sender/test numbers
  alt dry run enabled
    Voice-->>Comm: dry_run_conversation and payload
  Voice->>EL: POST ConvAI outbound-call payload
  Voice->>Voice: capture conversation_id/call_sid when present
```

## Runtime Requirements

- Recipient phone number must normalize to a valid E.164-like value.
- `ELEVENLABS_CONVAI_AGENT_ID` and `ELEVENLABS_CONVAI_PHONE_NUMBER_ID` are required for real calls.
- Direct ConvAI mode requires `ELEVENLABS_API_KEY`; a webhook bridge may relay the same ConvAI payload but must not be treated as a separate voice product.
- `CALL_ALERT_DRY_RUN` or `OUTBOUND_CALL_DRY_RUN` returns the exact payload without making a provider call.

## Dynamic Variables Sent To The Agent

The outbound call payload includes opportunity and candidate context such as `user_name`, `job_title`, `company`, `company_description`, `job_description`, `location`, `employment_type`, `experience_level`, `salary_range`, `match_score`, `matching_skills`, `missing_skills`, `recommended_skills`, `deadline`, `application_url`, `urgency_score`, `opportunity_priority_score`, `resume_strengths`, `resume_gaps`, `interview_focus_areas`, and `phone_number`.

## Prompt Status

`voice_opportunity_agent.py` contains a conversational prompt for "Alex", the CareerOS opportunity advisor. In the inspected call path, `conversational_outbound_call_service.initiate_call` passes `prompt=None` and `first_message=None` into `start_session`; therefore production behavior depends on the external ElevenLabs agent configuration plus the dynamic variables passed in the payload. The repository implements the prompt text but does not currently inject that prompt as a ConvAI override for outbound calls.

## Failure Modes

- Missing destination number: provider payload error or dry-run validation failure.
- Destination equals configured Twilio sender/test number: rejected before provider call.
- Missing ConvAI agent or phone number ID: configuration error.
- ElevenLabs ConvAI HTTP 4xx or 5xx: `upstream_http_error`.
- Conversation ID absent in provider response: call may still start, but transcript capture cannot be correlated reliably.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/api/v1/endpoints/opportunities_api.py`
- `backend/src/agents/opportunity_alert_agent.py`
- `backend/src/services/opportunity/communication_orchestrator.py`
- `backend/src/services/opportunity/conversational_outbound_call_service.py`
- `backend/src/services/opportunity/voice_opportunity_agent.py`
- `backend/tests/test_call_safety.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
