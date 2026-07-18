# CareerOS V2 Entity Relationship Map

Last verified from source code: 2026-06-20

This is a current schema map based on the models and services in the repo. It is intentionally centered on the entities that already drive product behavior.

## 1) Identity and profile

| Entity | Table / model | Important columns | Relationships | Source file | Current use | V2 gap |
|---|---|---|---|---|---|---|
| User | `users` / `User` | `id`, `email`, `password_hash`, `full_name`, `role`, `failed_login_attempts`, `locked_until`, `deleted_at` | Parent for most user-owned records | `backend/src/models/user.py` | Auth, RBAC, ownership | Good enough for V2; do not touch auth semantics without a separate plan |
| Resume | `resumes` / `Resume` | `user_id`, `filename`, `storage_path`, `status`, `metadata` | One user to many resumes | `backend/src/models/resume.py` | Upload and lifecycle | Needs stronger evidence linkage for skill/roadmap explanations |
| Resume version | `resume_versions` / `ResumeVersion` | `resume_id`, `version_num`, `raw_content`, `masked_content`, `normalized_content` | `Resume` -> many versions | `backend/src/models/resume.py` | Versioned resume processing | Good base for evidence history |
| Resume chunk | `resume_chunks` / `ResumeChunk` | `version_id`, `chunk_index`, `content`, `metadata` | `ResumeVersion` -> many chunks | `backend/src/models/resume.py` | Chunking for retrieval/embedding | Needs provenance surfaced more explicitly in V2 |

## 2) Jobs and matching

| Entity | Table / model | Important columns | Relationships | Source file | Current use | V2 gap |
|---|---|---|---|---|---|---|
| Job | `jobs` / `Job` | `job_id`, `title`, `company`, `description`, `location`, `salary_*`, `match_score`, `source_provider`, `freshness_bucket` | Central job record | `backend/src/models/jobs.py` | Discovery, ranking, UI, alerts | Should expose clearer evidence for scores |
| Job match | `job_matches` / `JobMatch` | Matching / scoring / evidence / rank fields | `Job`-centric match record | `backend/src/models/jobs.py` | Persisted match results | Needs stronger explainability and calibration |
| Salary intelligence | `salary_intelligence` / `SalaryIntelligence` | salary ranges, confidence, source | `Job` -> one salary intelligence row | `backend/src/models/jobs.py` | Salary extraction | Needs sufficient-data fallback in explanations |
| Interview prep plan | `interview_preparation_plans` / `InterviewPreparationPlan` | questions, topics, plan JSON, evidence | `Job` + user-linked | `backend/src/models/jobs.py` | Interview prep generation | Should connect more strongly to stored job evidence |
| Timeline event | `application_timeline_events` / `ApplicationTimelineEvent` | `status`, `event_type`, `notes`, `metadata` | `Job` + user timeline | `backend/src/models/jobs.py` | Funnel history | Good candidate for V2 analytics |
| Career memory | `career_memory` / `CareerMemory` | `event_type`, `job_id`, `source_table`, `source_id`, `title`, `data` | `Job` optional | `backend/src/models/jobs.py` | Memory of important events | Needs more structured event taxonomy |
| Alert audit | `alert_decision_audits` / `AlertDecisionAudit` | `decision`, `channel`, `reason`, `scores`, `evidence`, `decision_confidence` | `Job` + user | `backend/src/models/jobs.py` | Audit trail for alerting | Good foundation for governance |

## 3) Voice, communication, and outcomes

| Entity | Table / model | Important columns | Relationships | Source file | Current use | V2 gap |
|---|---|---|---|---|---|---|
| Communication request | `communication_requests` / `CommunicationRequest` | `correlation_id`, `user_id`, `job_id`, `channel`, `communication_status`, `communication_provider`, `delivery_attempts`, `pipedream_request`, `pipedream_response`, `webhook_status` | Parent for outbound comms | `backend/src/models/jobs.py` | Delivery pipeline, duplicate suppression, audit | Needs richer provider-result normalization |
| Voice session | `voice_sessions` / `VoiceSession` | `session_uid`, `communication_request_id`, `user_id`, `job_id`, `status`, `voice_provider`, `voice_metadata` | Tied to `CommunicationRequest` | `backend/src/models/jobs.py` | Live call session record | Needs more end-state certainty and transcript linkage |
| Voice conversation | `voice_conversations` / `VoiceConversation` | `voice_session_id`, `role`, `content`, `intelligence_snapshot` | `VoiceSession` -> many turns | `backend/src/models/jobs.py` | Transcript-like turn storage | Needs speaker/turn metadata consistency |
| Voice outcome | `voice_outcomes` / `VoiceOutcome` | `voice_session_id`, `outcome`, `provider_status`, `call_sid`, `data` | `VoiceSession` -> outcomes | `backend/src/models/jobs.py` | Call outcome capture | Could feed V2 conversion analytics |
| Opportunity context | `opportunity_conversation_contexts` / `OpportunityConversationContext` | `conversation_context`, `context_sources`, `context_confidence` | `Job` + user | `backend/src/models/jobs.py` | Conversation grounding | Good candidate for evidence graph |
| Opportunity outcome event | `opportunity_outcome_events` / `OpportunityOutcomeEvent` | `status`, `channel`, `data` | `Job` + `CommunicationRequest` | `backend/src/models/jobs.py` | Outcome tracking | Needs richer lifecycle semantics |
| Outcome metrics | `opportunity_outcome_metrics` / `OpportunityOutcomeMetric` | `metric_name`, `metric_value`, `dimensions`, `calculated_at` | User-owned metric rows | `backend/src/models/jobs.py` | Aggregated metrics | Several metrics may still be sparse until event volume grows |
| Conversion metrics | `opportunity_conversion_metrics` / `OpportunityConversionMetric` | `notified_count`, `applied_count`, `interview_count`, `offer_count`, `conversion_rate` | User-owned metric rows | `backend/src/models/jobs.py` | Funnel conversion view | Good, but depends on accurate event collection |
| Lifecycle run | `opportunity_lifecycle_runs` / `OpportunityLifecycleRun` | `status`, `monitored_counts`, `triggered_actions`, `errors` | User-owned run record | `backend/src/models/jobs.py` | Lifecycle audits | Strong starting point for V2 orchestration analytics |

## 4) Learning and skill development

| Entity | Table / model | Important columns | Relationships | Source file | Current use | V2 gap |
|---|---|---|---|---|---|---|
| Learning resource | `learning_resources` / `LearningResource` | `skill_name`, `title`, `url`, `source_type`, `trust_score`, `relevance_score`, `freshness_score`, `last_verified_at`, `metadata` | Resource catalog | `backend/src/models/learning.py` | Curated + live-discovery resource store | Needs outcome tracking, not just discovery ranking |
| Learning path | `user_skill_learning_paths` / `UserSkillLearningPath` | `user_id`, `skill_name`, `priority`, `estimated_hours`, `status`, `provider_health`, `path_data` | One user + skill | `backend/src/models/learning.py` | Skill-gap to path generation | Needs explicit evidence citations and completion feedback |
| Learning path item | `learning_path_items` / `LearningPathItem` | `path_id`, `title`, `description`, `completed`, `resource_url`, `order_index` | `LearningPath` -> many items | `backend/src/models/learning.py` | Ordered learning steps | Good base for V2 progress tracking |
| Learning session | `learning_sessions` / `LearningSession` | `session_uid`, `user_id`, `resource_id`, `provenance_uid`, `path_id`, `path_item_id`, `status`, `completion_percentage`, `started_at`, `ended_at` | `LearningResource` + optional path/item | `backend/src/models/learning.py` | Open/start/progress/complete/abandon tracking | Needs longer-lived session histories for better outcome confidence |
| Resource feedback | `resource_feedback` / `ResourceFeedback` | `feedback_uid`, `user_id`, `resource_id`, `session_uid`, `rating`, `would_recommend`, `helpfulness_score`, `outcome_tag` | `LearningSession` + `LearningResource` | `backend/src/models/learning.py` | Feedback capture | Good evidence source for quality scoring |
| Resource outcome | `resource_outcomes` / `ResourceOutcome` | `resource_id`, `completion_count`, `started_count`, `feedback_count`, `average_rating`, `completion_rate`, `drop_off_rate`, `recommendation_rate`, `average_completion_percentage`, `average_duration_seconds`, `status` | `LearningResource` -> one aggregate row | `backend/src/models/learning.py` | Outcome aggregation for resources | Still sparse until more activity accumulates |
| Learning activity event | `learning_activity_events` / `LearningActivityEvent` | `activity_uid`, `user_id`, `event_type`, `resource_id`, `session_uid`, `skill_slug`, `payload_json`, `event_time` | `LearningResource` + optional session/path/item | `backend/src/models/learning.py` | Audit trail for learning actions | Good replayable evidence layer |

## 5) Roadmaps

| Entity | Table / model | Important columns | Relationships | Source file | Current use | V2 gap |
|---|---|---|---|---|---|---|
| Roadmap | `roadmaps` / `Roadmap` | `user_id`, `title`, `target_role`, `target_salary`, `target_location`, `status`, `progress_pct`, `recommendations`, `velocity_history`, `trace_id` | Parent of roadmap goals/tasks | `backend/src/models/roadmap.py` | Career roadmap object | Progress telemetry still needs better truth labeling |
| Roadmap goal | `roadmap_goals` / `RoadmapGoal` | `title`, `description`, `category`, `priority`, `order_index` | `Roadmap` -> goals | `backend/src/models/roadmap.py` | Goal grouping | Can support better evidence mapping |
| Roadmap task | `roadmap_tasks` / `RoadmapTask` | `task_uid`, `goal_id`, `title`, `description`, `completed`, `due_date`, `order_index` | `RoadmapGoal` -> tasks | `backend/src/models/roadmap.py` | User task tracking | Needs telemetry and analytics beyond defaults |

## 6) Knowledge and RAG

| Entity | Table / model | Important columns | Relationships | Source file | Current use | V2 gap |
|---|---|---|---|---|---|---|
| Knowledge doc | `knowledge_docs` / `KnowledgeDoc` | `doc_uid`, `user_id`, `title`, `content`, `summary`, `source`, `chunk_count`, `status`, `analysis_results` | User-owned doc record | `backend/src/models/knowledge.py` | Knowledge Hub upload/analyze | Needs better provenance for RAG-style evidence |

## 7) Orchestration and governance

| Entity | Table / model | Important columns | Relationships | Source file | Current use | V2 gap |
|---|---|---|---|---|---|---|
| Orchestration session | `orchestration_sessions` / `OrchestrationSession` | `session_uid`, `user_id`, `graph_name`, `status`, `current_node`, `completion_pct`, `errors`, `metadata` | Parent for events | `backend/src/models/orchestration.py` | Graph/session tracking | Useful for V2 event-driven architecture |
| Orchestration event | `orchestration_events` / `OrchestrationEvent` | `event_type`, `node_name`, `agent_name`, `payload`, `status`, `retry_count`, `duration_ms` | `OrchestrationSession` -> events | `backend/src/models/orchestration.py` | Node-by-node audit | Good evidence layer for explainability |
| Autonomous action | `autonomous_actions` / `AutonomousAction` | `action_type`, `status`, `confidence`, `reasoning_chain`, `evidence_chain`, `governance_verdict`, `suppressed` | Session/user scoped | `backend/src/models/orchestration.py` | Governed actions | Can become the backbone of future automation |
| Notification history | `notification_history` / `NotificationHistory` | `channel`, `status`, `voice_script`, `elevenlabs_result`, `twilio_result`, `call_sid`, `urgency_score`, `suppressed` | User + opportunity | `backend/src/models/orchestration.py` | Delivery audit | Needs stronger normalization and less provider-specific leakage |
| Opportunity score | `opportunity_scores` / `OpportunityScore` | score breakdown + reason fields | User + session scoped | `backend/src/models/orchestration.py` | Opportunity prioritization | Good source for explainable ranking |
| Governance decision | `governance_decisions` / `GovernanceDecision` | decision / reason / confidence / policy data | Session or action scoped | `backend/src/models/orchestration.py` | Approval / governance audit | Useful for HITL and safety |
| MCP execution log | `mcp_execution_logs` / `MCPExecutionLog` | tool, provider, request, response, status, latency | MCP calls | `backend/src/models/orchestration.py` | Audit and debugging | Good candidate for V2 observability |

## 8) Outcome intelligence and career coaching

The current outcome-intelligence model file adds several analytics and memory tables, including:

- `conversation_sessions`
- `conversation_transcripts`
- `candidate_concerns`
- `candidate_preference_memory`
- `opportunity_call_outcomes`
- `conversation_sync_jobs`
- `followup_tasks`
- `application_lifecycle`
- `career_progress_metrics`
- `opportunity_reranking_records`
- `application_lifecycle_audit`
- `candidate_preference_history`
- `career_coach_plans`
- `career_coach_goals`
- `career_coach_recommendations`
- `learning_loop_runs`

These are important because they represent the current bridge between operational activity and higher-level coaching or outcome intelligence.

## 9) Skill graph and evidence import

| Entity | Table / model | Important columns | Relationships | Source file | Current use | V2 gap |
|---|---|---|---|---|---|---|
| Skill graph node | `skill_graph_nodes` / `SkillGraphNode` | `skill_slug`, `display_name`, `category`, `status`, `confidence`, `evidence_count`, `user_count`, `last_import_run_id` | Parent for aliases, edges, evidence, user states | `backend/src/models/skill_graph.py` | Canonical skill node registry | Needs broader evidence volume before downstream scoring can rely on it fully |
| Skill graph alias | `skill_graph_aliases` / `SkillGraphAlias` | `alias`, `normalized_alias`, `skill_slug`, `source`, `confidence` | Alias lookup to node | `backend/src/models/skill_graph.py` | Skill name normalization | Needs source-level provenance for some alias families |
| Skill graph edge | `skill_graph_edges` / `SkillGraphEdge` | `source_skill_slug`, `target_skill_slug`, `edge_type`, `weight`, `evidence_count` | Node-to-node relationship | `backend/src/models/skill_graph.py` | Relationship graph for learning / gap reasoning | Needs stronger calibration over time |
| Skill graph evidence | `skill_graph_evidence` / `SkillGraphEvidence` | `skill_slug`, `source_type`, `source_uid`, `source_label`, `score`, `payload` | Evidence row attached to a node | `backend/src/models/skill_graph.py` | Evidence-backed graph explanation | Needs more canonical provenance sources |
| Skill graph import run | `skill_graph_import_runs` / `SkillGraphImportRun` | `run_uid`, `status`, `node_count`, `edge_count`, `evidence_count`, `notes` | Import audit record | `backend/src/models/skill_graph.py` | Import history / dashboard | Good base for reindex audits |
| User skill state | `user_skill_states` / `UserSkillState` | `user_id`, `skill_slug`, `proficiency`, `confidence`, `evidence_count` | User + skill node | `backend/src/models/skill_graph.py` | Per-user skill state snapshots | Needs more longitudinal updates from learning and outcomes |

## 10) Skill gap engine entities

| Entity | Table / model | Important columns | Relationships | Source file | Current use | V2 gap |
|---|---|---|---|---|---|---|
| Skill gap analysis run | `skill_gap_analysis_runs` / `SkillGapAnalysisRun` | `run_uid`, `user_id`, `job_id`, `source_scope`, `status`, `overall_confidence`, `summary`, `analysis_version` | Parent for findings and evidence | `backend/src/models/skill_gap.py` | Persisted analysis run record | Needs broader calibration across more jobs and users |
| Skill gap finding | `skill_gap_findings` / `SkillGapFinding` | `run_uid`, `skill_name`, `skill_slug`, `gap_status`, `confidence`, `reason_summary`, `recommendation` | Belongs to analysis run; has evidence rows | `backend/src/models/skill_gap.py` | Gap classification and explanation | Needs richer longitudinal validation |
| Skill gap finding evidence | `skill_gap_finding_evidence` / `SkillGapFindingEvidence` | `finding_id`, `source_type`, `source_uid`, `source_label`, `score`, `payload` | Belongs to a finding | `backend/src/models/skill_gap.py` | Evidence payload for each finding | Needs broader provenance sources |
| User skill gap snapshot | `user_skill_gap_snapshots` / `UserSkillGapSnapshot` | `user_id`, `job_id`, `run_uid`, `summary`, `finding_count`, `insufficient_count` | Latest per-user snapshot of skill gap analysis | `backend/src/models/skill_gap.py` | Cached summary for UI / API | Needs more history and recalibration over time |

## 11) Schema implications for V2

The current schema already supports a serious V2 roadmap, but these areas need attention:

1. More explicit evidence relationships across scores and recommendations.
2. Better separation of live signals versus seeded/fallback signals.
3. Stronger event history for learning and outcome analytics.
4. More durable transcript and call-state normalization.
5. Better null/`insufficient_data` modeling for analytics that are not yet backed by enough events.
