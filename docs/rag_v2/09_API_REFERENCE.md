---
title: "API Reference"
document_id: "09_api_reference"
domain: "api"
feature: "routes"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - api
  - routes
---

# API Reference Generated From Route Declarations

This API reference is generated from FastAPI route decorators in `backend/src/api`. Authentication is marked from visible `Depends(get_current_user)` or `Depends(get_current_user_id)` route parameters.

| Method | Path | Function | Source | Auth | Response model |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/health/live` | `health_live` | `backend/src/api/health.py` | No/route-local | `Dict[str, Any]` |
| GET | `/api/health/ready` | `health_ready` | `backend/src/api/health.py` | No/route-local | `Dict[str, Any]` |
| GET | `/api/health/deep` | `health_deep` | `backend/src/api/health.py` | No/route-local | `Dict[str, Any]` |
| GET | `/api/health/detailed` | `health_detailed` | `backend/src/api/health.py` | No/route-local | `Dict[str, Any]` |
| GET | `/api/health/dependencies` | `health_dependencies` | `backend/src/api/health.py` | No/route-local | `Dict[str, Any]` |
| GET | `/api/agents/status` | `get_agent_status` | `backend/src/api/v1/endpoints/agents.py` | No/route-local | `List[AgentStatus]` |
| GET | `/api/approvals` | `list_approvals` | `backend/src/api/v1/endpoints/approvals.py` | Yes | `` |
| GET | `/api/approvals/stats` | `approval_stats` | `backend/src/api/v1/endpoints/approvals.py` | Yes | `ApprovalStatsResponse` |
| GET | `/api/approvals/notifications` | `list_notifications` | `backend/src/api/v1/endpoints/approvals.py` | Yes | `` |
| POST | `/api/approvals/notifications/read` | `mark_notifications_read` | `backend/src/api/v1/endpoints/approvals.py` | Yes | `` |
| GET | `/api/approvals/{approval_id}` | `get_approval` | `backend/src/api/v1/endpoints/approvals.py` | Yes | `` |
| POST | `/api/approvals/{approval_id}/comment` | `add_comment` | `backend/src/api/v1/endpoints/approvals.py` | Yes | `` |
| POST | `/api/approvals/{approval_id}/approve` | `approve` | `backend/src/api/v1/endpoints/approvals.py` | Yes | `` |
| POST | `/api/approvals/{approval_id}/reject` | `reject` | `backend/src/api/v1/endpoints/approvals.py` | Yes | `` |
| POST | `/api/approvals/{approval_id}/execute` | `execute` | `backend/src/api/v1/endpoints/approvals.py` | Yes | `` |
| POST | `/api/approvals/{approval_id}/edit` | `edit` | `backend/src/api/v1/endpoints/approvals.py` | Yes | `` |
| POST | `/api/approvals` | `create_approval` | `backend/src/api/v1/endpoints/approvals.py` | Yes | `` |
| POST | `/api/auth/register` | `register` | `backend/src/api/v1/endpoints/auth.py` | No/route-local | `` |
| POST | `/api/auth/login` | `login` | `backend/src/api/v1/endpoints/auth.py` | No/route-local | `` |
| GET | `/api/auth/me` | `get_current_user_profile` | `backend/src/api/v1/endpoints/auth.py` | Yes | `` |
| PATCH | `/api/auth/me` | `update_profile` | `backend/src/api/v1/endpoints/auth.py` | Yes | `` |
| POST | `/api/auth/change-password` | `change_password` | `backend/src/api/v1/endpoints/auth.py` | Yes | `` |
| POST | `/api/auth/forgot-password` | `forgot_password` | `backend/src/api/v1/endpoints/auth.py` | No/route-local | `` |
| POST | `/api/auth/reset-password` | `reset_password` | `backend/src/api/v1/endpoints/auth.py` | No/route-local | `` |
| POST | `/api/auth/logout` | `logout` | `backend/src/api/v1/endpoints/auth.py` | Yes | `` |
| DELETE | `/api/auth/account` | `delete_account` | `backend/src/api/v1/endpoints/auth.py` | Yes | `` |
| GET | `/api/followups` | `followups` | `backend/src/api/v1/endpoints/autonomous_engagement.py` | Yes | `` |
| POST | `/api/followups/{task_id}/execute` | `execute_followup` | `backend/src/api/v1/endpoints/autonomous_engagement.py` | Yes | `` |
| GET | `/api/application-lifecycle` | `lifecycles` | `backend/src/api/v1/endpoints/autonomous_engagement.py` | Yes | `` |
| GET | `/api/application-lifecycle/{job_id}` | `lifecycle` | `backend/src/api/v1/endpoints/autonomous_engagement.py` | Yes | `` |
| GET | `/api/career-progress` | `progress` | `backend/src/api/v1/endpoints/autonomous_engagement.py` | Yes | `` |
| GET | `/api/opportunity-reranking` | `reranking` | `backend/src/api/v1/endpoints/autonomous_engagement.py` | Yes | `` |
| POST | `/api/demo-rag/chat` | `demo_rag_chat` | `backend/src/api/v1/endpoints/demo_rag.py` | No/route-local | `DemoRagChatResponse` |
| POST | `/api/demo-rag/index` | `demo_rag_index` | `backend/src/api/v1/endpoints/demo_rag.py` | No/route-local | `DemoRagIndexResponse` |
| GET | `/api/demo-rag/health` | `demo_rag_health` | `backend/src/api/v1/endpoints/demo_rag.py` | No/route-local | `DemoRagHealthResponse` |
| GET | `/api/demo-rag/golden-questions` | `demo_rag_golden_questions` | `backend/src/api/v1/endpoints/demo_rag.py` | No/route-local | `` |
| GET | `/api/eval/runs` | `list_eval_runs` | `backend/src/api/v1/endpoints/evaluation.py` | Yes | `` |
| GET | `/api/eval/runs/{run_id}/details` | `get_run_details` | `backend/src/api/v1/endpoints/evaluation.py` | No/route-local | `` |
| GET | `/api/eval/runs/{run_id}/progress` | `get_run_progress` | `backend/src/api/v1/endpoints/evaluation.py` | No/route-local | `` |
| POST | `/api/eval/benchmark` | `trigger_benchmark` | `backend/src/api/v1/endpoints/evaluation.py` | Yes | `` |
| POST | `/api/eval/hallucination/detect` | `detect_hallucination` | `backend/src/api/v1/endpoints/evaluation.py` | Yes | `` |
| GET | `/api/events` | `list_events` | `backend/src/api/v1/endpoints/events.py` | Yes | `CareerEventsListResponse` |
| GET | `/api/events/{event_uid}` | `get_event` | `backend/src/api/v1/endpoints/events.py` | Yes | `CareerEventResponse` |
| POST | `/api/interview/start` | `start_interview` | `backend/src/api/v1/endpoints/interview.py` | Yes | `` |
| POST | `/api/interview/respond` | `interview_respond` | `backend/src/api/v1/endpoints/interview.py` | No/route-local | `` |
| GET | `/api/interview/status/{session_uid}` | `interview_status` | `backend/src/api/v1/endpoints/interview.py` | No/route-local | `` |
| POST | `/api/interview/pause/{session_uid}` | `pause_interview` | `backend/src/api/v1/endpoints/interview.py` | No/route-local | `` |
| POST | `/api/interview/resume/{session_uid}` | `resume_interview` | `backend/src/api/v1/endpoints/interview.py` | No/route-local | `` |
| POST | `/api/interview/interrupt/{session_uid}` | `interrupt_interview` | `backend/src/api/v1/endpoints/interview.py` | No/route-local | `` |
| GET | `/api/interview/replay/{session_uid}` | `interview_replay` | `backend/src/api/v1/endpoints/interview.py` | No/route-local | `` |
| POST | `/api/interview/kill/{session_uid}` | `kill_interview` | `backend/src/api/v1/endpoints/interview.py` | No/route-local | `` |
| GET | `/api/interview/history` | `interview_history` | `backend/src/api/v1/endpoints/interview.py` | Yes | `` |
| GET | `/api/interview/memory` | `interview_memory` | `backend/src/api/v1/endpoints/interview.py` | Yes | `` |
| POST | `/api/interview/end` | `end_interview` | `backend/src/api/v1/endpoints/interview.py` | Yes | `` |
| GET | `/api/interview/report/{session_uid}` | `interview_report` | `backend/src/api/v1/endpoints/interview.py` | No/route-local | `` |
| DELETE | `/api/interview/session/{session_uid}` | `delete_interview_session` | `backend/src/api/v1/endpoints/interview.py` | Yes | `` |
| GET | `/api/interview/intelligence` | `interview_intelligence` | `backend/src/api/v1/endpoints/interview.py` | Yes | `` |
| GET | `/api/interview/health` | `interview_health` | `backend/src/api/v1/endpoints/interview.py` | No/route-local | `` |
| GET | `/api/jobs` | `list_jobs` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `JobsListResponse` |
| GET | `/api/jobs/stats` | `job_stats` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `JobStatsResponse` |
| GET | `/api/jobs/alert-stats` | `alert_decision_stats` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/alerts` | `alert_records` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `AlertRecordsResponse` |
| GET | `/api/jobs/applications` | `get_applications` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| POST | `/api/jobs/phase2/run` | `run_phase2_intelligence` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/phase2/dashboard` | `get_phase2_dashboard` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/phase2/jobs/{job_id}` | `get_phase2_job_intelligence` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/providers/twilio/health` | `twilio_health` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/providers/twilio/reconcile` | `reconcile_twilio_calls` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/providers/elevenlabs/health` | `elevenlabs_health` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/providers/pipedream/health` | `pipedream_health` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/providers/theirstack/health` | `theirstack_health` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/voice-sessions` | `get_voice_sessions` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/voice-sessions/{session_id}` | `get_voice_session` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/voice-sessions/{session_id}/transition` | `transition_voice_session` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/career-memory` | `get_career_memory` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/outcome-intelligence` | `get_outcome_intelligence` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/{job_id}` | `get_job` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `JobResponse` |
| POST | `/api/jobs/refresh` | `refresh_jobs` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/refresh/{session_id}` | `get_refresh_status` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| POST | `/api/jobs/{job_id}/application` | `update_application` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| GET | `/api/jobs/{job_id}/application` | `get_application_status` | `backend/src/api/v1/endpoints/jobs.py` | Yes | `` |
| POST | `/api/knowledge/upload` | `knowledge_upload` | `backend/src/api/v1/endpoints/knowledge.py` | Yes | `` |
| GET | `/api/knowledge` | `list_knowledge_docs` | `backend/src/api/v1/endpoints/knowledge.py` | Yes | `` |
| GET | `/api/knowledge/{doc_id}` | `get_knowledge_doc` | `backend/src/api/v1/endpoints/knowledge.py` | Yes | `` |
| DELETE | `/api/knowledge/{doc_id}` | `delete_knowledge_doc` | `backend/src/api/v1/endpoints/knowledge.py` | Yes | `` |
| POST | `/api/knowledge/{doc_id}/analyze` | `trigger_analysis` | `backend/src/api/v1/endpoints/knowledge.py` | Yes | `` |
| GET | `/api/knowledge/{doc_id}/score` | `get_analysis_score` | `backend/src/api/v1/endpoints/knowledge.py` | Yes | `` |
| GET | `/api/knowledge/alignment-report/{run_id}` | `get_alignment_report` | `backend/src/api/v1/endpoints/knowledge.py` | Yes | `` |
| GET | `/api/learning/skill-gaps` | `get_skill_gaps` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningGapSummaryResponse` |
| GET | `/api/learning/paths` | `list_paths` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningPathsListResponse` |
| GET | `/api/learning/paths/{skill_slug}` | `get_path` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningPathEnvelopeResponse` |
| POST | `/api/learning/paths/refresh` | `refresh_paths` | `backend/src/api/v1/endpoints/learning.py` | Yes | `RefreshPathsResponse` |
| GET | `/api/learning/gap-actions` | `get_gap_actions` | `backend/src/api/v1/endpoints/learning.py` | Yes | `GapActionsResponse` |
| POST | `/api/learning/gap-actions/refresh` | `refresh_gap_actions` | `backend/src/api/v1/endpoints/learning.py` | Yes | `GapActionsResponse` |
| GET | `/api/learning/github-projects` | `get_github_projects` | `backend/src/api/v1/endpoints/learning.py` | Yes | `GitHubProjectsResponse` |
| POST | `/api/learning/github-projects/refresh` | `refresh_github_projects` | `backend/src/api/v1/endpoints/learning.py` | Yes | `GitHubProjectsResponse` |
| POST | `/api/learning/resources/{resource_id}/open` | `open_learning_resource` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningTrackingActionResponse` |
| POST | `/api/learning/resources/{resource_id}/start` | `start_learning_resource` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningTrackingActionResponse` |
| PATCH | `/api/learning/sessions/{session_uid}/progress` | `update_learning_progress` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningTrackingActionResponse` |
| POST | `/api/learning/sessions/{session_uid}/complete` | `complete_learning_resource` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningTrackingActionResponse` |
| POST | `/api/learning/sessions/{session_uid}/abandon` | `abandon_learning_resource` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningTrackingActionResponse` |
| POST | `/api/learning/resources/{resource_id}/feedback` | `submit_learning_feedback` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningTrackingActionResponse` |
| POST | `/api/learning/provenance/{provenance_uid}/open` | `open_learning_resource_by_provenance` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningTrackingActionResponse` |
| POST | `/api/learning/provenance/{provenance_uid}/start` | `start_learning_resource_by_provenance` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningTrackingActionResponse` |
| POST | `/api/learning/provenance/{provenance_uid}/feedback` | `submit_learning_feedback_by_provenance` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningTrackingActionResponse` |
| GET | `/api/learning/resources/{resource_id}/outcome` | `get_learning_resource_outcome` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningResourceOutcomeResponse` |
| GET | `/api/learning/provenance/{provenance_uid}/outcome` | `get_learning_resource_outcome_by_provenance` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningResourceOutcomeResponse` |
| GET | `/api/learning/outcomes` | `list_learning_outcomes` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningOutcomeListResponse` |
| GET | `/api/learning/activity` | `list_learning_activity` | `backend/src/api/v1/endpoints/learning.py` | Yes | `LearningActivityListResponse` |
| GET | `/api/learning/provenance` | `list_provenance` | `backend/src/api/v1/endpoints/learning.py` | Yes | `ResourceProvenanceListResponse` |
| GET | `/api/learning/provenance/{provenance_uid}` | `get_provenance` | `backend/src/api/v1/endpoints/learning.py` | Yes | `ResourceProvenanceSummaryResponse` |
| GET | `/api/learning/resources/{resource_id}/provenance` | `get_resource_provenance` | `backend/src/api/v1/endpoints/learning.py` | Yes | `ResourceProvenanceListResponse` |
| GET | `/api/learning/discovery-runs` | `list_discovery_runs` | `backend/src/api/v1/endpoints/learning.py` | Yes | `ResourceDiscoveryRunListResponse` |
| GET | `/api/learning/discovery-runs/{run_uid}` | `get_discovery_run` | `backend/src/api/v1/endpoints/learning.py` | Yes | `ResourceDiscoveryRunResponse` |
| POST | `/api/mcp/test` | `test_mcp_workflow` | `backend/src/api/v1/endpoints/mcp.py` | Yes | `MCPTraceResponse` |
| GET | `/api/observability/metrics` | `metrics` | `backend/src/api/v1/endpoints/observability.py` | No/route-local | `` |
| GET | `/api/observability/latency` | `get_latency_overview` | `backend/src/api/v1/endpoints/observability.py` | No/route-local | `` |
| GET | `/api/observability/overview` | `get_observability_overview` | `backend/src/api/v1/endpoints/observability.py` | No/route-local | `` |
| GET | `/api/observability/llm` | `get_llm_observability_endpoint` | `backend/src/api/v1/endpoints/observability.py` | No/route-local | `` |
| POST | `/api/opportunities/discover` | `discover_opportunities` | `backend/src/api/v1/endpoints/opportunities_api.py` | Yes | `DiscoverResponse` |
| GET | `/api/opportunities/list` | `list_opportunities` | `backend/src/api/v1/endpoints/opportunities_api.py` | Yes | `` |
| GET | `/api/opportunities/rc3/intelligence` | `rc3_opportunity_intelligence` | `backend/src/api/v1/endpoints/opportunities_api.py` | Yes | `` |
| GET | `/api/opportunities/rc3/timeline/{job_id}` | `communication_timeline` | `backend/src/api/v1/endpoints/opportunities_api.py` | Yes | `` |
| POST | `/api/opportunities/rc3/outcomes` | `rc3_record_outcome` | `backend/src/api/v1/endpoints/opportunities_api.py` | Yes | `` |
| POST | `/api/opportunities/rc3/lifecycle/run` | `rc3_run_lifecycle` | `backend/src/api/v1/endpoints/opportunities_api.py` | Yes | `` |
| POST | `/api/opportunities/alert` | `trigger_opportunity_alert` | `backend/src/api/v1/endpoints/opportunities_api.py` | Yes | `` |
| GET | `/api/opportunities/skill-gap/{job_id}` | `compute_skill_gap` | `backend/src/api/v1/endpoints/opportunities_api.py` | Yes | `SkillGapResponse` |
| POST | `/api/opportunity-alert` | `evaluate_opportunity_alert` | `backend/src/api/v1/endpoints/opportunity_alert.py` | Yes | `OpportunityAlertResponse` |
| POST | `/api/orchestration/trigger` | `trigger_orchestration` | `backend/src/api/v1/endpoints/orchestration.py` | Yes | `` |
| GET | `/api/orchestration/status/{session_uid}` | `orchestration_status` | `backend/src/api/v1/endpoints/orchestration.py` | No/route-local | `` |
| GET | `/api/orchestration/history` | `orchestration_history` | `backend/src/api/v1/endpoints/orchestration.py` | Yes | `` |
| POST | `/api/orchestration/cancel/{session_uid}` | `cancel_orchestration` | `backend/src/api/v1/endpoints/orchestration.py` | No/route-local | `` |
| POST | `/api/orchestration/resume/{session_uid}` | `resume_orchestration` | `backend/src/api/v1/endpoints/orchestration.py` | Yes | `ResumeResponse` |
| GET | `/api/orchestration/governance/decisions` | `governance_decisions` | `backend/src/api/v1/endpoints/orchestration.py` | No/route-local | `` |
| GET | `/api/orchestration/governance/stats` | `governance_stats` | `backend/src/api/v1/endpoints/orchestration.py` | No/route-local | `` |
| GET | `/api/orchestration/traces` | `orchestration_traces` | `backend/src/api/v1/endpoints/orchestration.py` | No/route-local | `` |
| GET | `/api/orchestration/health` | `orchestration_health` | `backend/src/api/v1/endpoints/orchestration.py` | No/route-local | `` |
| GET | `/api/outcomes` | `list_outcomes` | `backend/src/api/v1/endpoints/outcome_intelligence.py` | Yes | `` |
| GET | `/api/outcomes/{candidate_id}` | `candidate_outcomes` | `backend/src/api/v1/endpoints/outcome_intelligence.py` | Yes | `` |
| GET | `/api/conversations/{conversation_id}` | `get_conversation` | `backend/src/api/v1/endpoints/outcome_intelligence.py` | Yes | `` |
| POST | `/api/conversations/process` | `process_conversation` | `backend/src/api/v1/endpoints/outcome_intelligence.py` | Yes | `` |
| GET | `/api/candidate-memory/{candidate_id}` | `candidate_memory` | `backend/src/api/v1/endpoints/outcome_intelligence.py` | Yes | `` |
| GET | `/api/candidate-concerns/{candidate_id}` | `candidate_concerns` | `backend/src/api/v1/endpoints/outcome_intelligence.py` | Yes | `` |
| GET | `/api/packages` | `list_packages` | `backend/src/api/v1/endpoints/packages.py` | Yes | `` |
| POST | `/api/packages/generate` | `generate_package` | `backend/src/api/v1/endpoints/packages.py` | Yes | `` |
| GET | `/api/packages/{pkg_id}` | `get_package` | `backend/src/api/v1/endpoints/packages.py` | No/route-local | `` |
| DELETE | `/api/packages/{pkg_id}` | `delete_package` | `backend/src/api/v1/endpoints/packages.py` | Yes | `` |
| POST | `/api/packages/{pkg_id}/regenerate` | `regenerate_package` | `backend/src/api/v1/endpoints/packages.py` | Yes | `` |
| GET | `/api/packages/{pkg_id}/download` | `download_package` | `backend/src/api/v1/endpoints/packages.py` | No/route-local | `` |
| GET | `/api/candidate-memory` | `candidate_memory_preferences` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/candidate-memory/history` | `candidate_memory_history` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/opportunities/reranked` | `reranked_opportunities` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/opportunities/reranked/{job_id}` | `reranked_detail` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| POST | `/api/application-lifecycle/update` | `update_lifecycle` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/application-lifecycle/history` | `lifecycle_history` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/application-lifecycle/current/{job_id}` | `lifecycle_current` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/career-intelligence` | `career_intelligence` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/career-intelligence/weekly-summary` | `career_intelligence_weekly` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/career-coach` | `career_coach_dashboard` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/career-coach/plans` | `career_coach_plans` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/career-coach/goals` | `career_coach_goals` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/career-coach/recommendations` | `career_coach_recommendations` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| POST | `/api/learning-loop/run` | `run_learning_loop` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/learning-loop/history` | `learning_loop_history` | `backend/src/api/v1/endpoints/phase6.py` | Yes | `` |
| GET | `/api/user/preferences` | `get_preferences` | `backend/src/api/v1/endpoints/preferences.py` | Yes | `` |
| PUT | `/api/user/preferences` | `update_preferences` | `backend/src/api/v1/endpoints/preferences.py` | Yes | `` |
| GET | `/api/readiness/score` | `get_readiness_score` | `backend/src/api/v1/endpoints/readiness.py` | Yes | `ReadinessResponse` |
| GET | `/api/readiness/timeline` | `get_career_timeline` | `backend/src/api/v1/endpoints/readiness.py` | Yes | `` |
| GET | `/api/readiness/explain` | `get_explainability` | `backend/src/api/v1/endpoints/readiness.py` | Yes | `` |
| POST | `/api/readiness/report` | `generate_report` | `backend/src/api/v1/endpoints/readiness.py` | Yes | `` |
| GET | `/api/readiness/reports` | `list_reports` | `backend/src/api/v1/endpoints/readiness.py` | Yes | `` |
| GET | `/api/readiness/reports/{report_id}/download` | `download_persisted_report` | `backend/src/api/v1/endpoints/readiness.py` | Yes | `` |
| GET | `/api/readiness/report/download` | `download_report` | `backend/src/api/v1/endpoints/readiness.py` | Yes | `` |
| WEBSOCKET | `/api/realtime/ws/{session_type}` | `realtime_websocket` | `backend/src/api/v1/endpoints/realtime.py` | No/route-local | `` |
| WEBSOCKET | `/api/realtime/interview/{session_uid}` | `interview_websocket` | `backend/src/api/v1/endpoints/realtime.py` | No/route-local | `` |
| WEBSOCKET | `/api/realtime/orchestration/trace/{session_uid}` | `trace_websocket` | `backend/src/api/v1/endpoints/realtime.py` | No/route-local | `` |
| POST | `/api/rerank` | `rerank_execute` | `backend/src/api/v1/endpoints/rerank.py` | Yes | `RerankResponse` |
| GET | `/api/rerank/health` | `rerank_health` | `backend/src/api/v1/endpoints/rerank.py` | No/route-local | `RerankHealthResponse` |
| GET | `/api/rerank/stats` | `rerank_stats` | `backend/src/api/v1/endpoints/rerank.py` | Yes | `RerankStatsResponse` |
| GET | `/api/rerank/history` | `rerank_history` | `backend/src/api/v1/endpoints/rerank.py` | Yes | `RerankHistoryResponse` |
| GET | `/api/roadmaps` | `list_roadmaps` | `backend/src/api/v1/endpoints/roadmaps.py` | Yes | `` |
| GET | `/api/roadmaps/{roadmap_id}` | `get_roadmap` | `backend/src/api/v1/endpoints/roadmaps.py` | Yes | `` |
| POST | `/api/roadmaps/generate` | `generate_roadmap` | `backend/src/api/v1/endpoints/roadmaps.py` | Yes | `` |
| POST | `/api/roadmaps/regenerate` | `regenerate_roadmap` | `backend/src/api/v1/endpoints/roadmaps.py` | Yes | `` |
| GET | `/api/roadmaps/progress` | `get_progress` | `backend/src/api/v1/endpoints/roadmaps.py` | Yes | `` |
| PATCH | `/api/roadmaps/tasks/{task_id}` | `toggle_task` | `backend/src/api/v1/endpoints/roadmaps.py` | Yes | `` |
| GET | `/api/skill-gaps/health` | `health` | `backend/src/api/v1/endpoints/skill_gaps.py` | No/route-local | `` |
| POST | `/api/skill-gaps/analyze` | `analyze_skill_gaps` | `backend/src/api/v1/endpoints/skill_gaps.py` | Yes | `SkillGapAnalysisResponse` |
| GET | `/api/skill-gaps/runs` | `list_runs` | `backend/src/api/v1/endpoints/skill_gaps.py` | Yes | `SkillGapRunListResponse` |
| GET | `/api/skill-gaps/runs/{run_uid}` | `get_run` | `backend/src/api/v1/endpoints/skill_gaps.py` | Yes | `SkillGapRunDetailResponse` |
| GET | `/api/skill-gaps/jobs/{job_id}` | `get_job_analysis` | `backend/src/api/v1/endpoints/skill_gaps.py` | Yes | `SkillGapJobResponse` |
| GET | `/api/skill-gaps/snapshot` | `get_snapshot` | `backend/src/api/v1/endpoints/skill_gaps.py` | Yes | `SkillGapSnapshotResponse` |
| GET | `/api/skill-gaps/skills/{skill_slug}/evidence` | `get_skill_evidence` | `backend/src/api/v1/endpoints/skill_gaps.py` | Yes | `SkillGapSkillEvidenceResponse` |
| GET | `/api/skill-gaps/findings` | `list_findings` | `backend/src/api/v1/endpoints/skill_gaps.py` | Yes | `SkillGapFindingListResponse` |
| GET | `/api/skill-graph/health` | `skill_graph_health` | `backend/src/api/v1/endpoints/skill_graph.py` | No/route-local | `SkillGraphHealthResponse` |
| GET | `/api/skill-graph/summary` | `skill_graph_summary` | `backend/src/api/v1/endpoints/skill_graph.py` | Yes | `SkillGraphSummaryResponse` |
| GET | `/api/skill-graph/nodes` | `list_skill_nodes` | `backend/src/api/v1/endpoints/skill_graph.py` | Yes | `SkillGraphNodeListResponse` |
| GET | `/api/skill-graph/nodes/{skill_slug}` | `get_skill_node` | `backend/src/api/v1/endpoints/skill_graph.py` | Yes | `SkillGraphDetailResponse` |
| GET | `/api/skill-graph/states` | `list_skill_states` | `backend/src/api/v1/endpoints/skill_graph.py` | Yes | `SkillGraphStateListResponse` |
| GET | `/api/skill-graph/import-runs` | `list_import_runs` | `backend/src/api/v1/endpoints/skill_graph.py` | Yes | `SkillGraphImportRunListResponse` |
| POST | `/api/skill-graph/import` | `import_skill_graph` | `backend/src/api/v1/endpoints/skill_graph.py` | Yes | `SkillGraphImportResponse` |
| GET | `/api/troubleshoot/circuits` | `list_circuits` | `backend/src/api/v1/endpoints/troubleshoot.py` | No/route-local | `` |
| POST | `/api/troubleshoot/circuits/toggle` | `toggle_circuit` | `backend/src/api/v1/endpoints/troubleshoot.py` | No/route-local | `` |
| GET | `/api/troubleshoot/audit` | `audit_logs` | `backend/src/api/v1/endpoints/troubleshoot.py` | No/route-local | `` |
| GET | `/api/troubleshoot/pending` | `pending_jobs` | `backend/src/api/v1/endpoints/troubleshoot.py` | No/route-local | `` |
| DELETE | `/api/{resume_id}` | `delete_resume` | `backend/src/api/v1/endpoints/resumes/lifecycle.py` | Yes | `` |
| GET | `/api/` | `list_resumes` | `backend/src/api/v1/endpoints/resumes/retrieval.py` | Yes | `ResumeListResponse` |
| GET | `/api/{resume_id}` | `get_resume` | `backend/src/api/v1/endpoints/resumes/retrieval.py` | Yes | `ResumeDetailResponse` |
| GET | `/api/{resume_id}/versions` | `get_resume_versions` | `backend/src/api/v1/endpoints/resumes/retrieval.py` | Yes | `List[ResumeVersionResponse]` |
| GET | `/api/{resume_id}/download` | `download_resume` | `backend/src/api/v1/endpoints/resumes/retrieval.py` | Yes | `` |
| POST | `/api/{resume_id}/retry` | `retry_resume` | `backend/src/api/v1/endpoints/resumes/retry.py` | Yes | `ResumeRetryResponse` |
| GET | `/api/task/{task_id}` | `get_task_status_endpoint` | `backend/src/api/v1/endpoints/resumes/status.py` | No/route-local | `TaskStatusResponse` |
| POST | `/api/upload` | `upload_resume` | `backend/src/api/v1/endpoints/resumes/upload.py` | Yes | `ResumeUploadResponse` |

## Route Reachability Notes

- `backend/src/api/v1/endpoints/outcome_intelligence.py` is included with prefix `/api`, so its paths are `/api/outcomes`, `/api/conversations/{conversation_id}`, and related paths rather than `/api/v1/...`.
- `backend/src/api/v1/endpoints/opportunity_alert.py` is included with prefix `/api`, so `POST /api/opportunity-alert` exists separately from `POST /api/v1/opportunities/alert`.
- Some backend routes are operational or test-oriented and have no direct frontend consumer found in `frontend/src`.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/main.py`
- `backend/src/api/v1/endpoints`
- `docs/rag_audit_evidence.json`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
