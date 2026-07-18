# Agent Cards

Last verified from source code: 2026-06-14

## OpportunityDiscoveryAgent

| Field | Details |
| --- | --- |
| Purpose | Find candidate opportunities from resume and market context |
| Trigger | Opportunity discovery run or jobs refresh |
| Inputs | Candidate context, resume content, market signals |
| Outputs | Ranked opportunity list, market signal counts |
| Related files | `backend/src/agents/opportunity_discovery_agent.py`; `backend/src/api/v1/endpoints/opportunities_api.py` |
| Why it matters | It starts the matching story |

## OpportunityScoringAgent

| Field | Details |
| --- | --- |
| Purpose | Score fit across skill, role, seniority, urgency, and market dimensions |
| Trigger | Opportunity scoring step inside the pipeline |
| Inputs | Job details, resume context, extracted skills |
| Outputs | Dimension scores, evidence, fit score, confidence |
| Related files | `backend/src/agents/opportunity_scoring_agent.py`; `backend/src/services/orchestration/nodes.py` |
| Why it matters | It drives ranking quality and alerts |

## OpportunityPrioritizationAgent

| Field | Details |
| --- | --- |
| Purpose | Convert fit and urgency into a final priority score |
| Trigger | After scoring, before notification decisions |
| Inputs | Fit score, urgency score, confidence |
| Outputs | Priority score and ordering signals |
| Related files | `backend/src/agents/opportunity_prioritization_agent.py` |
| Why it matters | It helps decide which opportunities get attention first |

## DeadlineUrgencyAgent

| Field | Details |
| --- | --- |
| Purpose | Estimate urgency from deadline and market timing |
| Trigger | After scoring, before governance |
| Inputs | Deadline, application urgency, market demand |
| Outputs | Urgency score and explanation |
| Related files | `backend/src/agents/deadline_urgency_agent.py` |
| Why it matters | It prevents low-urgency items from taking over |

## NotificationDecisionAgent

| Field | Details |
| --- | --- |
| Purpose | Decide whether to notify and which channel to use |
| Trigger | After score and urgency are computed |
| Inputs | Fit score, confidence, urgency, governance verdict |
| Outputs | Channel decision, should-notify flag, reason |
| Related files | `backend/src/agents/notification_decision_agent.py` |
| Why it matters | It gates outbound action and user-visible alerts |

## ElevenLabsVoiceSynthesisAgent

| Field | Details |
| --- | --- |
| Purpose | Prepare voice payloads and trigger ElevenLabs synthesis |
| Trigger | When the notification decision allows voice delivery |
| Inputs | Candidate/job context, call script, dynamic variables |
| Outputs | Audio payload, MCP log, synthesized call content |
| Related files | `backend/src/agents/elevenlabs_voice_synthesis_agent.py` |
| Why it matters | It powers the outbound call experience |

## TwilioVoiceAgent

| Field | Details |
| --- | --- |
| Purpose | Dispatch call actions through Twilio MCP routing |
| Trigger | After voice synthesis or call preparation |
| Inputs | Phone number, call payload, call metadata |
| Outputs | Call status, call SID or simulated result, MCP log |
| Related files | `backend/src/agents/twilio_voice_agent.py` |
| Why it matters | It is the delivery step for outbound calls |

## OrchestrationGovernanceAgent

| Field | Details |
| --- | --- |
| Purpose | Enforce recursion depth, confidence, and action caps |
| Trigger | Before autonomous or outbound actions |
| Inputs | Execution state, confidence, prior actions |
| Outputs | Governance verdict, penalties, reasons |
| Related files | `backend/src/agents/orchestration_governance_agent.py` |
| Why it matters | It protects the app from unsafe autonomous behavior |

## ExplainabilityAgent

| Field | Details |
| --- | --- |
| Purpose | Compile readable reasoning and evidence summaries |
| Trigger | After scoring and governance |
| Inputs | Scores, evidence, governance output, match context |
| Outputs | Explanation text, evidence chain, trace-friendly summary |
| Related files | `backend/src/agents/explainability_agent.py` |
| Why it matters | It makes the system understandable to users and reviewers |

## AgentObservability

| Field | Details |
| --- | --- |
| Purpose | Capture agent execution metrics and telemetry |
| Trigger | Every agent execution or governance event |
| Inputs | Latency, confidence, execution result |
| Outputs | Prometheus metrics and observability signals |
| Related files | `backend/src/agents/agent_observability.py` |
| Why it matters | It makes debugging and production review possible |

## OpportunityAlertAgent

| Field | Details |
| --- | --- |
| Purpose | Convert a persisted match into an alert and action path |
| Trigger | When a job crosses the alert threshold or the alert API is called |
| Inputs | Match data, urgency, phone number, user context |
| Outputs | Alert record, communication request, optional outbound action |
| Related files | `backend/src/agents/opportunity_alert_agent.py` |
| Why it matters | It bridges scoring into actual action |
