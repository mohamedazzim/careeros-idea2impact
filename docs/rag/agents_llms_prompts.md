# Agents, LLMs, and Prompting

Last verified from source code: 2026-06-14

## Core agent inventory

The core agent layer has 11 agents in `backend/src/agents`.

| Agent | Responsibility |
| --- | --- |
| `OpportunityDiscoveryAgent` | Finds and ranks opportunities from resume and market context |
| `OpportunityScoringAgent` | Scores opportunity fit across multiple dimensions |
| `OpportunityPrioritizationAgent` | Computes the final priority score |
| `DeadlineUrgencyAgent` | Calculates urgency based on deadlines and market factors |
| `NotificationDecisionAgent` | Decides whether to notify and through which channel |
| `ElevenLabsVoiceSynthesisAgent` | Prepares voice scripts and triggers synthesis |
| `TwilioVoiceAgent` | Dispatches call actions through Twilio MCP routing |
| `OrchestrationGovernanceAgent` | Enforces recursion, confidence, and action limits |
| `ExplainabilityAgent` | Builds the reasoned explanation and evidence summary |
| `AgentObservability` | Records execution metrics and telemetry |
| `OpportunityAlertAgent` | Coordinates alert generation for persisted matches |

## LLM provider design

- Primary provider: Gemini 2.5 Flash
- Fallback provider: DeepSeek NIM via `FallbackProvider`
- Prompts are versioned in `backend/src/services/intelligence/prompt_versioning.py`

## Prompt families

- Core reasoning prompts
- ATS and resume intelligence prompts
- Career strategy prompts
- Interview intelligence prompts

## Source anchors

- `backend/src/agents`
- `backend/src/services/opportunity`
- `backend/src/services/intelligence/prompt_versioning.py`
- `backend/src/services/llm/factory.py`
- `backend/src/services/llm/fallback_provider.py`
- `backend/src/services/mcp/mcp_router.py`
- `backend/src/core/config.py`
