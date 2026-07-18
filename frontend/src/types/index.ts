export interface User {
  id: string;
  email: string;
  role: string;
  full_name?: string;
  created_at: string;
}

export interface UserPreferences {
  alert_threshold: number; // default: 85
  notification_email: string;
  quiet_hours_start: string; // e.g., "22:00"
  quiet_hours_end: string;   // e.g., "08:00"
  enable_twilio_alerts?: boolean;
  enable_linkedin_posts?: boolean;
  target_role?: string;
  target_salary?: string;
  target_location?: string;
  experience_level?: string;
  career_stage?: string;
  preferred_work_mode?: string;
  timeline_months?: number;
}

export interface KnowledgeDoc {
  id: string;
  filename: string;
  doc_type: 'resume' | 'doc' | 'upload';
  content?: string;
  raw_text?: string;
  cleaned_text?: string;
  status: 'uploaded' | 'ingested' | 'processing' | 'stripping_pii' | 'masking_pii' | 'embedding' | 'chunking_and_embedding' | 'persisting_chunks' | 'indexing' | 'evaluating' | 'indexed' | 'analyzed' | 'failed';
  chunk_count?: number;
  embedding_status?: string;
  vector_count?: number;
  content_length?: number;
  is_selectable?: boolean;
  pii_entities?: Array<{ entity_type: string; original_text: string; mask_token: string }>;
  created_at: string;
}

export interface KnowledgeChunk {
  id: string;
  doc_id: string;
  chunk_text: string;
  qdrant_point_id: string;
  index: number;
}

export interface Gap {
  id: string;
  category: string;
  severity: 'high' | 'medium' | 'low';
  description: string;
  suggestion: string;
}

export interface Strength {
  id: string;
  title: string;
  impact: 'high' | 'medium' | 'low';
  description: string;
}

export interface ScoreComponent {
  key: string;
  label: string;
  score: number;
  weight: number;
  contribution: number;
  max_contribution: number;
  matched: string[];
  missing: string[];
  evidence: string[];
}

export interface AlignmentExplainability {
  overall_score: number;
  grade: string;
  formula: string;
  weights: Record<string, number>;
  components: ScoreComponent[];
  matched_skills: string[];
  missing_skills: string[];
  matched_items: string[];
  missing_items: string[];
  resume_overview: Record<string, string>;
  jd_overview: Record<string, string | string[]>;
  improvement_suggestions: string[];
  final_recommendation: string;
  score_scenarios?: {
    if_missing_skills_added?: number;
    if_relocation_added?: number;
    if_tensorflow_pytorch_projects_added?: number;
  };
}

export interface MatchResult {
  match_score: number;
  grade: string;
  strengths: Strength[];
  gaps: Gap[];
  summary: string;
  recommendations: string[];
  explainability?: AlignmentExplainability;
  resume_quality_score?: number;
}

export interface AnalysisRun {
  id: string;
  doc_id: string;
  job_description: string;
  status: 'idle' | 'retrieving' | 'reranking' | 'scoring' | 'completed' | 'failed';
  created_at: string;
  match_result?: MatchResult;
  error?: string;
}

export interface Job {
  id: string;
  source: string;
  source_provider?: string;
  source_job_id?: string;
  source_url?: string;
  external_id?: string;
  job_hash?: string;
  title: string;
  company: string;
  location: string;
  employment_type?: string;
  description?: string;
  full_description?: string;
  apply_url: string;
  posted_at?: string;
  posted_date?: string;
  fetched_at?: string;
  ingested_at?: string;
  created_at: string;
  skills?: JobSkill[];
  skills_required?: string[];
  extracted_skills?: string[];
  salary?: string;
  url_type?: string;
  freshness_score?: number;
  freshness_bucket?: string;
  provider_quality_score?: number;
  salary_quality_score?: number;
  opportunity_priority_score?: number;
  lifecycle_state?: string;
  apply_url_valid?: boolean;
  match?: JobMatch;
}

export type JobSortOption = 'best_match' | 'posted_at_desc' | 'fetched_at_desc' | 'freshness_desc' | 'company_asc';

export interface JobSkill {
  id: string;
  job_id: string;
  skill: string;
  importance: 'high' | 'medium' | 'low';
}

export interface JobSource {
  id: string;
  name: string;
  status: 'active' | 'inactive' | 'syncing';
  last_sync: string;
}

export interface JobIngestionRun {
  id: string;
  source: string;
  started_at: string;
  completed_at: string;
  status: 'running' | 'completed' | 'failed';
  jobs_found: number;
  jobs_added: number;
}

export interface JobRefreshProviderResult {
  provider: string;
  display_name?: string;
  status: 'queued' | 'running' | 'completed' | 'blocked' | 'error' | 'skipped' | string;
  configured?: boolean;
  provider_blocked?: boolean;
  billing_required?: boolean;
  provider_status_code?: number;
  found?: number;
  normalized?: number;
  added?: number;
  updated?: number;
  duplicates_removed?: number;
  expired_removed?: number;
  error_count?: number;
  embedded?: number;
  query_context?: {
    provider?: string;
    display_name?: string;
    query?: string;
    location?: string;
    limit?: number;
    since?: string;
    configured?: boolean;
    query_count?: number;
    skill_terms?: string[];
  };
  sample_updated_jobs?: Array<{
    title?: string;
    company?: string;
    provider?: string;
    external_job_id?: string;
    last_seen_at?: string;
    updated_fields?: string[];
  }>;
  message?: string | null;
}

export interface JobRefreshVisibilityReason {
  code: string;
  message: string;
}

export interface JobRefreshDiagnostics {
  status: 'queued' | 'running' | 'completed' | 'failed' | string;
  reason_code: string;
  reason: string;
  summary: {
    found: number;
    added: number;
    updated: number;
    duplicates_removed: number;
    expired_removed: number;
    errors: number;
    embedded: number;
  };
  provider_results: JobRefreshProviderResult[];
  visibility_reason?: JobRefreshVisibilityReason;
  totals?: {
    fetched: number;
    new_unique: number;
    updated_existing: number;
    duplicate_results: number;
    visible_new_jobs: number;
  };
  dedupe?: {
    strategy: string;
    new_insert_count: number;
    existing_match_count: number;
    duplicate_result_count: number;
    possible_over_dedupe_count: number;
  };
  visibility?: {
    visible_list_changed: boolean;
    reason_if_unchanged?: string | null;
    message?: string | null;
  };
  sample_updated_jobs?: Array<{
    title?: string;
    company?: string;
    provider?: string;
    external_job_id?: string;
    last_seen_at?: string;
    updated_fields?: string[];
  }>;
  provider_query_contexts?: Array<{
    provider?: string;
    display_name?: string;
    query?: string;
    location?: string;
    limit?: number;
    since?: string;
    configured?: boolean;
    query_count?: number;
    skill_terms?: string[];
  }>;
}

export interface JobRefreshResponse {
  session_uid: string;
  session_id: number;
  status: string;
  message?: string;
  started_at?: string | null;
  active_resume?: Record<string, any> | null;
  provider_catalog?: Array<{ name: string; display_name?: string; supported_mode?: string }>;
  diagnostics?: JobRefreshDiagnostics;
}

export interface JobRefreshStatusResponse {
  session_id: number;
  session_uid: string;
  status: string;
  current_node?: string | null;
  completion_pct?: number;
  progress?: { processed: number; total: number; failed: number };
  stage_history?: Array<{ node: string; label: string; at: string }>;
  provider_health?: Record<string, any>;
  provider_results?: JobRefreshProviderResult[];
  refresh_summary?: JobRefreshDiagnostics['summary'];
  visibility_reason?: JobRefreshVisibilityReason;
  diagnostics?: JobRefreshDiagnostics;
  resume?: Record<string, any> | null;
  error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface JobMatch {
  id: string;
  user_id: string;
  job_id: string;
  match_score: number;
  confidence: number;
  created_at: string;
  strengths?: Strength[];
  gaps?: Gap[];
  summary?: string;
  recommendations?: string[];
}

export interface ApplicationPackage {
  id: string;
  user_id: string;
  job_id: string;
  status: 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  resume?: GeneratedResume;
  cover_letter?: GeneratedCoverLetter;
  messages?: GeneratedMessage[];
  interview_guide?: GeneratedInterviewGuide;
  versions?: PackageVersion[];
  
  summary_sheet?: {
    match_score: number;
    top_strengths: string[];
    skill_gaps: string[];
    recommended_talking_points: string[];
  };
}

export interface GeneratedResume {
  id: string;
  package_id: string;
  content: string;
  version: number;
  created_at: string;
}

export interface GeneratedCoverLetter {
  id: string;
  package_id: string;
  content: string;
  version: number;
  created_at: string;
}

export interface GeneratedMessage {
  id: string;
  package_id: string;
  message_type: 'recruiter' | 'hiring_manager';
  content: string;
  created_at: string;
}

export interface GeneratedInterviewGuide {
  id: string;
  package_id: string;
  content: string;
  created_at: string;
}

export interface PackageVersion {
  id: string;
  package_id: string;
  version: number;
  change_reason: string;
  created_at: string;
}

export interface InterviewSession {
  id: string;
  user_id: string;
  job_id: string;
  interview_type: 'hr' | 'technical' | 'behavioral' | 'ai_engineer' | 'software_engineer' | 'custom';
  status: 'processing' | 'ongoing' | 'completed' | 'failed';
  started_at: string;
  ended_at?: string;
  overall_score?: number;
  difficulty?: string;
  topics?: string[];
  total_questions?: number;
  current_question_index?: number;
}

export interface InterviewMessage {
  id: string;
  session_id: string;
  role: 'assistant' | 'user';
  message: string;
  created_at: string;
  technical_score?: number;
  communication_score?: number;
  confidence_score?: number;
  relevance_score?: number;
  overall_score?: number;
}

export interface InterviewFeedback {
  id: string;
  session_id: string;
  question_id: string;
  score: number;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  technical_score?: number;
  communication_score?: number;
  confidence_score?: number;
  relevance_score?: number;
}

export interface LongTermMemory {
  id: string;
  user_id: string;
  memory_type: 'strength' | 'weakness' | 'goal' | 'preference' | 'communication' | 'feedback' | 'trend';
  content: string;
  confidence: number;
  source_session_id?: string;
  created_at: string;
  updated_at: string;
}

export interface MemoryEvent {
  id: string;
  user_id: string;
  event_type: 'interview_completed' | 'weakness_identified' | 'strength_unlocked' | 'improvement_trend';
  summary: string;
  created_at: string;
}

export type ApprovalType = 
  | 'LINKEDIN_POST' 
  | 'RECRUITER_MESSAGE' 
  | 'HIRING_MANAGER_MESSAGE' 
  | 'APPLICATION_PACKAGE' 
  | 'EMAIL' 
  | 'PHONE_ALERT' 
  | 'CUSTOM';

export type ApprovalStatus = 
  | 'draft' 
  | 'pending' 
  | 'approved' 
  | 'rejected' 
  | 'executed' 
  | 'archived';

export interface Approval {
  id: string;
  user_id: string;
  approval_type: ApprovalType;
  status: ApprovalStatus;
  title: string;
  summary: string;
  payload_json: {
    type: ApprovalType;
    content: string;
    metadata?: Record<string, any>;
    generated_by?: string;
    trace_id?: string;
    run_id?: string;
    [key: string]: any;
  };
  created_at: string;
  updated_at: string;
}

export interface ApprovalAction {
  id: string;
  approval_id: string;
  action_type: 'APPROVED' | 'REJECTED' | 'EDITED' | 'EXECUTED';
  performed_by: string;
  notes?: string;
  created_at: string;
}

export interface ApprovalHistory {
  id: string;
  approval_id: string;
  old_status: ApprovalStatus;
  new_status: ApprovalStatus;
  changed_by: string;
  reason?: string;
  created_at: string;
}

export interface ApprovalComment {
  id: string;
  approval_id: string;
  user_id: string;
  comment: string;
  created_at: string;
}

export interface ApprovalTemplate {
  id: string;
  approval_type: ApprovalType;
  default_title: string;
  default_description: string;
  created_at: string;
}

export type OpportunityAlertType = 'HIGH_MATCH' | 'INTERVIEW_REMINDER';
export type OpportunityAlertStatus = 'pending' | 'approved' | 'rejected' | 'dismissed';

export interface OpportunityAlert {
  id: string;
  user_id: string;
  job_id: string;
  alert_type: OpportunityAlertType;
  status: OpportunityAlertStatus;
  match_score?: number;
  created_at: string;
  notes?: string;
}

export interface LinkedInPost {
  id: string;
  user_id: string;
  approval_id: string;
  content: string;
  published_at?: string;
  status: 'draft' | 'approved' | 'published' | 'rejected';
}

export interface TwilioCall {
  id: string;
  user_id: string;
  approval_id: string;
  call_sid: string;
  duration?: number;
  status: 'initiated' | 'completed' | 'failed';
  created_at: string;
}

export interface McpExecutionLog {
  id: string;
  tool_name: string;
  execution_type: string;
  status: 'success' | 'failed';
  request_payload: string;
  response_payload: string;
  created_at: string;
}

export type RoadmapType = 'SKILL_DEVELOPMENT' | 'INTERVIEW_PREP' | 'JOB_SEARCH' | 'AI_ENGINEER';

export interface Roadmap {
  id: string;
  user_id: string;
  roadmap_type: RoadmapType;
  title: string;
  summary: string;
  status: 'draft' | 'active' | 'completed' | 'archived';
  created_at: string;
  updated_at: string;
  trace_id?: string;
  run_id?: string;
}

export interface RoadmapGoal {
  id: string;
  roadmap_id: string;
  goal_type: 'weekly' | 'monthly' | 'quarterly' | 'milestone';
  title: string;
  description: string;
  target_date: string;
  status: 'pending' | 'in_progress' | 'completed';
}

export interface RoadmapTask {
  id: string;
  goal_id: string;
  task_title: string;
  task_description: string;
  priority: 'high' | 'medium' | 'low';
  status: 'pending' | 'completed';
}

export interface RoadmapProgress {
  id: string;
  roadmap_id: string;
  completion_percentage: number;
  updated_at: string;
  progress_source?: string;
  telemetry_status?: 'not_tracked' | 'partial' | 'tracked';
  observability?: {
    status?: 'not_tracked' | 'partial' | 'tracked';
    summary?: string;
    averageGenerationTimeMs?: number | null;
    averageRefreshTimeMs?: number | null;
    goalCompletionRatePercent?: number;
    recommendationAcceptancePercent?: number;
    totalGenerations?: number | null;
    totalRefreshes?: number | null;
  };
}

export interface RoadmapRecommendation {
  id: string;
  roadmap_id: string;
  recommendation_type: string;
  content: string;
  created_at: string;
}

export interface LearningResource {
  id: number;
  skill_slug: string;
  skill_name: string;
  title: string;
  provider: string;
  source_type: string;
  source_url: string;
  channel_name?: string | null;
  duration_minutes?: number | null;
  difficulty?: string | null;
  format?: string | null;
  is_free: boolean;
  language: string;
  trust_score: number;
  relevance_score: number;
  freshness_score: number;
  last_verified_at?: string | null;
  metadata?: Record<string, any>;
  source_domain?: string | null;
  discovery_source?: string | null;
  verification_status?: string | null;
  price_status?: string | null;
  cache_status?: string | null;
  provenance_summary?: ResourceProvenanceSummary | null;
  outcome_summary?: LearningResourceOutcomeSummary | null;
}

export interface LearningResourceTrackingRequest {
  path_id?: number | null;
  path_item_id?: number | null;
  job_id?: number | null;
  skill_slug?: string | null;
  source_ui?: string | null;
  external_resource_url?: string | null;
  metadata?: Record<string, any>;
}

export interface LearningProgressRequest {
  completion_percentage: number;
  notes?: string | null;
  metadata?: Record<string, any>;
}

export interface LearningCompletionRequest {
  notes?: string | null;
  metadata?: Record<string, any>;
}

export interface LearningAbandonRequest {
  reason?: string | null;
  notes?: string | null;
  metadata?: Record<string, any>;
}

export interface LearningFeedbackRequest {
  session_uid?: string | null;
  rating?: number | null;
  difficulty?: string | null;
  would_recommend?: boolean | null;
  comment?: string | null;
  helpfulness_score?: number | null;
  outcome_tag?: string | null;
  metadata?: Record<string, any>;
}

export interface LearningSession {
  session_uid: string;
  user_id: string;
  resource_id?: number | null;
  provenance_uid?: string | null;
  path_id?: number | null;
  path_item_id?: number | null;
  skill_slug: string;
  job_id?: number | null;
  status: string;
  source_ui?: string | null;
  external_resource_url?: string | null;
  started_at?: string | null;
  last_activity_at?: string | null;
  ended_at?: string | null;
  duration_seconds?: number | null;
  completion_percentage: number;
  metadata_json?: Record<string, any>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface LearningResourceFeedback {
  feedback_uid: string;
  user_id: string;
  resource_id?: number | null;
  provenance_uid?: string | null;
  session_uid?: string | null;
  skill_slug: string;
  rating?: number | null;
  difficulty?: string | null;
  would_recommend?: boolean | null;
  comment?: string | null;
  helpfulness_score?: number | null;
  outcome_tag?: string | null;
  metadata_json?: Record<string, any>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface LearningResourceOutcomeSummary {
  resource_id?: number | null;
  provenance_uid?: string | null;
  skill_slug: string;
  source_type?: string | null;
  provider?: string | null;
  completion_count: number;
  started_count: number;
  feedback_count: number;
  average_rating?: number | null;
  completion_rate?: number | null;
  drop_off_rate?: number | null;
  recommendation_rate?: number | null;
  average_completion_percentage?: number | null;
  average_duration_seconds?: number | null;
  last_calculated_at?: string | null;
  status: string;
  calculation_metadata_json?: Record<string, any>;
  explanation?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export type LearningResourceOutcome = LearningResourceOutcomeSummary;

export interface LearningActivityEvent {
  activity_uid: string;
  user_id: string;
  event_type: string;
  resource_id?: number | null;
  provenance_uid?: string | null;
  session_uid?: string | null;
  path_id?: number | null;
  path_item_id?: number | null;
  skill_slug: string;
  job_id?: number | null;
  payload_json?: Record<string, any>;
  event_time?: string | null;
  created_at?: string | null;
}

export interface LearningTrackingActionResponse {
  status: string;
  message?: string | null;
  session?: LearningSession | null;
  feedback?: LearningResourceFeedback | null;
  outcome?: LearningResourceOutcome | null;
  event?: LearningActivityEvent | null;
  insufficient_data: boolean;
}

export interface LearningResourceOutcomeResponse {
  status: string;
  outcome?: LearningResourceOutcome | null;
  insufficient_data: boolean;
  message?: string | null;
}

export interface LearningOutcomeListResponse {
  status: string;
  total: number;
  outcomes: LearningResourceOutcome[];
}

export interface LearningActivityListResponse {
  status: string;
  total: number;
  events: LearningActivityEvent[];
}

export interface ResourceProvenanceSummary {
  provenance_uid: string;
  provenance_type: string;
  source_entity_type: string;
  source_entity_id: string;
  source_table?: string | null;
  source_pk?: string | null;
  recorded_at?: string | null;
  status: string;
  confidence: string;
  score_total: number;
  score_formula: string;
  score_breakdown: Record<string, any>;
  explanation?: string | null;
  evidence_count: number;
  provider?: string | null;
  skill_slug?: string | null;
  skill_name?: string | null;
  title?: string | null;
  source_url?: string | null;
  resource_id?: number | null;
  discovery_run_uid?: string | null;
}

export interface ResourceDiscoveryRun {
  run_uid: string;
  status: string;
  provider: string;
  source_type: string;
  skill_slug?: string | null;
  skill_name?: string | null;
  candidate_count: number;
  stored_count: number;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface LearningProviderHealthEntry {
  name: string;
  display_name?: string;
  status: 'success' | 'skipped' | 'missing_api_key' | 'quota_exceeded' | 'error' | 'seeded_fallback' | string;
  configured?: boolean;
  enabled?: boolean;
  search_backend?: string;
  allowed_domains?: string[];
  query_templates?: string[];
  last_checked_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  last_result_count?: number | null;
  message?: string | null;
}

export interface LearningProviderHealth {
  enabled: boolean;
  discovery_enabled?: boolean;
  provider: string;
  provider_mode: string;
  status?: string;
  cache_ttl_hours: number;
  min_results_per_skill?: number;
  max_results_per_skill?: number;
  seed_file_present: boolean;
  trusted_sources: number;
  web_search_enabled?: boolean;
  web_search_provider?: string;
  search_backend?: string;
  youtube_configured?: boolean;
  message?: string | null;
  providers: LearningProviderHealthEntry[];
}

export interface LearningPathStep {
  order_index: number;
  step_type: string;
  title: string;
  reason?: string | null;
  estimated_minutes?: number | null;
  practice_project?: string | null;
  resources: LearningResource[];
}

export interface LearningSkillGap {
  skill_slug: string;
  skill_name: string;
  count: number;
  priority: 'high' | 'medium' | 'low' | string;
  estimated_hours: number;
  reason: string;
  source_job_ids: number[];
  source_job_titles: string[];
  job_match_ids: number[];
  max_match_score: number;
  resource_status: 'available' | 'not_available' | string;
}

export interface LearningPath {
  skill_slug: string;
  skill_name: string;
  priority: 'high' | 'medium' | 'low' | string;
  estimated_hours: number;
  reason: string;
  source_job_ids: number[];
  source_job_titles: string[];
  job_match_ids: number[];
  resource_status: 'available' | 'not_available' | string;
  discovery_status?: string | null;
  resource_count?: number;
  resource_titles?: string[];
  source_domains?: string[];
  message?: string | null;
  cached: boolean;
  generated_at: string;
  refreshed_at: string;
  steps: LearningPathStep[];
  provenance_summary?: Record<string, any> | null;
}

export interface LearningPathsResponse {
  status: string;
  user_id: string;
  paths: LearningPath[];
  skill_gaps: LearningSkillGap[];
  provider_health: LearningProviderHealth;
}

export interface LearningSkillGapSummaryResponse {
  status: string;
  user_id: string;
  total_gaps: number;
  unique_skills: number;
  gaps: LearningSkillGap[];
  provider_health: LearningProviderHealth;
}

export interface SkillGapAnalyzeRequest {
  job_id?: number | null;
  target_role_slug?: string | null;
  source_scope: "job" | "role" | "user" | "roadmap";
}

export interface SkillGapEvidence {
  evidence_uid: string;
  finding_uid: string;
  user_id: string;
  skill_slug: string;
  evidence_type: string;
  source_table?: string | null;
  source_id?: string | null;
  source_url?: string | null;
  evidence_strength: string;
  supports_status: string;
  quote_or_snippet?: string | null;
  metadata_json: Record<string, any>;
  confidence: string;
  created_at?: string | null;
}

export interface SkillGapFinding {
  finding_uid: string;
  run_uid: string;
  user_id: string;
  job_id?: number | null;
  skill_node_uid?: string | null;
  skill_slug: string;
  skill_name: string;
  required_by_type: string;
  required_by_id?: string | null;
  gap_status: string;
  confidence: string;
  evidence_count: number;
  missing_evidence: Record<string, any>[];
  reason_summary: string;
  recommendation_summary?: string | null;
  calculation_metadata_json: Record<string, any>;
  evidence: SkillGapEvidence[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SkillGapSummary {
  required_skill_count: number;
  missing_skill_count: number;
  learning_skill_count: number;
  evidenced_skill_count: number;
  validated_skill_count: number;
  insufficient_data_count: number;
}

export interface SkillGapRunSummary {
  run_uid: string;
  user_id: string;
  job_id?: number | null;
  target_role_slug?: string | null;
  source_scope: string;
  source_service: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  required_skill_count: number;
  missing_skill_count: number;
  evidenced_skill_count: number;
  learning_skill_count: number;
  validated_skill_count: number;
  insufficient_data_count: number;
  confidence: string;
  failure_reason?: string | null;
  metadata_json: Record<string, any>;
  created_at?: string | null;
}

export interface SkillGapAnalysisResponse {
  run_uid: string;
  status: string;
  summary: SkillGapSummary;
  findings: SkillGapFinding[];
}

export interface SkillGapRunDetailResponse {
  status: string;
  run: SkillGapRunSummary;
  summary: SkillGapSummary;
  findings: SkillGapFinding[];
}

export interface SkillGapRunListResponse {
  status: string;
  total: number;
  runs: SkillGapRunSummary[];
}

export interface SkillGapFindingListResponse {
  status: string;
  total: number;
  findings: SkillGapFinding[];
}

export interface SkillGapJobResponse {
  status: string;
  job_id: number;
  latest_run?: SkillGapRunSummary | null;
  summary: SkillGapSummary;
  findings: SkillGapFinding[];
}

export interface SkillGapSnapshotResponse {
  status: string;
  snapshot_uid: string;
  user_id: string;
  target_role_slug?: string | null;
  job_id?: number | null;
  run_uid: string;
  summary_json: Record<string, any>;
  missing_count: number;
  learning_count: number;
  evidenced_count: number;
  validated_count: number;
  insufficient_data_count: number;
  created_at?: string | null;
  latest_run?: SkillGapRunSummary | null;
  findings: SkillGapFinding[];
}

export interface SkillGapSkillEvidenceResponse {
  status: string;
  skill_slug: string;
  evidence: SkillGapEvidence[];
  total: number;
}

export interface LearningGapProjectIdea {
  title: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced' | string;
  estimated_hours: number;
  proof_type: string;
  steps: string[];
  source_resources: LearningResource[];
  resume_bullets: string[];
  github_readme_outline: string[];
  source_status: string;
}

export interface LearningGapResumeProof {
  before_gap: string;
  suggested_bullets: string[];
  linkedin_bullets: string[];
  portfolio_description: string;
  source_status: string;
}

export interface LearningGapInterviewProof {
  talking_points: string[];
  sample_answer: string;
  source_status: string;
}

export interface LearningGapAction {
  skill_slug: string;
  skill_name: string;
  count: number;
  priority: 'high' | 'medium' | 'low' | string;
  estimated_hours: number;
  reason: string;
  source_job_ids: number[];
  source_job_titles: string[];
  job_match_ids: number[];
  resource_status: 'available' | 'not_available' | string;
  resource_count: number;
  source_status: string;
  source_resources: LearningResource[];
  project_ideas: LearningGapProjectIdea[];
  resume_proof: LearningGapResumeProof;
  interview_proof: LearningGapInterviewProof;
  provenance_summary?: Record<string, any> | null;
}

export interface LearningGapActionsJobContext {
  job_id?: number | null;
  title?: string | null;
  company?: string | null;
  location?: string | null;
  apply_url?: string | null;
  source_url?: string | null;
  match_score?: number | null;
  missing_skill_slugs: string[];
  missing_skill_names: string[];
}

export interface LearningGapActionsResponse {
  status: string;
  user_id: string;
  job_id?: number | null;
  job_context?: LearningGapActionsJobContext | null;
  cached: boolean;
  generated_at: string;
  provider_health: LearningProviderHealth;
  source_status: string;
  actions: LearningGapAction[];
}

export interface GitHubProjectRepository {
  skill_slug: string;
  skill_name: string;
  full_name: string;
  html_url: string;
  description?: string | null;
  language?: string | null;
  stargazers_count: number;
  forks_count: number;
  watchers_count: number;
  is_template: boolean;
  archived: boolean;
  updated_at?: string | null;
  matched_query: string;
  matched_terms: string[];
  source_status: string;
  provenance_summary?: ResourceProvenanceSummary | null;
}

export interface GitHubProjectIssue {
  skill_slug: string;
  skill_name: string;
  title: string;
  html_url: string;
  repository_full_name: string;
  repository_html_url: string;
  label_names: string[];
  state: string;
  score: number;
  is_pull_request: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  matched_terms: string[];
  source_status: string;
  provenance_summary?: ResourceProvenanceSummary | null;
}

export interface GitHubProjectSkill {
  skill_slug: string;
  skill_name: string;
  count: number;
  priority: 'high' | 'medium' | 'low' | string;
  estimated_hours: number;
  reason: string;
  source_job_ids: number[];
  source_job_titles: string[];
  job_match_ids: number[];
  repository_status: 'available' | 'not_available' | string;
  issue_status: 'available' | 'not_available' | string;
  source_status: string;
  repository_count: number;
  template_count: number;
  issue_count: number;
  repositories: GitHubProjectRepository[];
  templates: GitHubProjectRepository[];
  good_first_issues: GitHubProjectIssue[];
  search_queries: string[];
  errors: string[];
  provenance_summary?: Record<string, any> | null;
}

export interface GitHubProjectProviderHealthEntry {
  name: string;
  display_name?: string;
  status: string;
  configured?: boolean;
  enabled?: boolean;
  last_result_count?: number | null;
  message?: string | null;
}

export interface GitHubProjectProviderHealth {
  enabled: boolean;
  provider: string;
  provider_mode: string;
  status: string;
  cache_ttl_hours: number;
  min_results_per_skill: number;
  max_results_per_skill: number;
  issue_discovery_enabled: boolean;
  token_configured: boolean;
  message?: string | null;
  providers?: GitHubProjectProviderHealthEntry[];
}

export interface GitHubProjectsResponse {
  status: string;
  user_id: string;
  job_id?: number | null;
  job_context?: LearningGapActionsJobContext | null;
  cached: boolean;
  generated_at: string;
  provider_health: GitHubProjectProviderHealth;
  source_status: string;
  skills: GitHubProjectSkill[];
}

export interface SkillGraphHealthResponse {
  status: string;
  ready: boolean;
  tables: string[];
  collection: string;
  message?: string | null;
}

export interface SkillGraphNode {
  skill_slug: string;
  skill_name: string;
  category: string;
  status: string;
  evidence_count: number;
  source_count: number;
  user_count: number;
  demand_count: number;
  supply_count: number;
  trust_score: number;
  relevance_score: number;
  freshness_score: number;
  confidence_score: number;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  last_import_run_uid?: string | null;
  metadata?: Record<string, any>;
}

export interface SkillGraphAlias {
  raw_value: string;
  normalized_value: string;
  source_entity_type: string;
  source_entity_id: string;
  source_field: string;
  source_table?: string | null;
  source_pk?: string | null;
  provider?: string | null;
  alias_type: string;
  metadata?: Record<string, any>;
  created_at?: string | null;
  skill_slug: string;
  skill_name: string;
}

export interface SkillGraphEdge {
  edge_uid: string;
  source_skill_slug: string;
  source_skill_name: string;
  target_skill_slug: string;
  target_skill_name: string;
  edge_type: string;
  source_entity_type: string;
  source_entity_id: string;
  source_table?: string | null;
  source_pk?: string | null;
  source_title?: string | null;
  provider?: string | null;
  weight: number;
  evidence_count: number;
  confidence_score: number;
  relation_summary?: string | null;
  metadata?: Record<string, any>;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
}

export interface SkillGraphEvidence {
  evidence_uid: string;
  skill_slug: string;
  skill_name: string;
  source_entity_type: string;
  source_entity_id: string;
  source_table?: string | null;
  source_pk?: string | null;
  source_field: string;
  source_title?: string | null;
  source_url?: string | null;
  provider?: string | null;
  evidence_kind: string;
  raw_value: string;
  normalized_value: string;
  trust_score: number;
  relevance_score: number;
  freshness_score: number;
  confidence: string;
  status: string;
  metadata?: Record<string, any>;
  recorded_at?: string | null;
}

export interface SkillGraphUserState {
  state_uid: string;
  user_id: string;
  skill_slug: string;
  skill_name: string;
  category: string;
  status: string;
  confidence_score: number;
  evidence_count: number;
  demand_count: number;
  supply_count: number;
  learning_signal_count: number;
  resume_signal_count: number;
  started_count: number;
  completion_count: number;
  feedback_count: number;
  average_rating?: number | null;
  last_activity_at?: string | null;
  last_import_run_uid?: string | null;
  recommended_action?: string | null;
  evidence_summary?: Record<string, any>;
  metadata?: Record<string, any>;
}

export interface SkillGraphImportRun {
  run_uid: string;
  user_id?: string | null;
  scope: string;
  status: string;
  strategy: string;
  node_count: number;
  edge_count: number;
  evidence_count: number;
  alias_count: number;
  user_state_count: number;
  source_counts?: Record<string, any>;
  notes?: string | null;
  error_message?: string | null;
  metadata?: Record<string, any>;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SkillGraphSummaryResponse {
  status: string;
  total_nodes: number;
  total_edges: number;
  total_evidence: number;
  total_aliases: number;
  total_user_states: number;
  source_counts?: Record<string, any>;
  top_nodes: SkillGraphNode[];
  user_states: SkillGraphUserState[];
  latest_import_run?: SkillGraphImportRun | null;
}

export interface SkillGraphNodeListResponse {
  status: string;
  total: number;
  nodes: SkillGraphNode[];
}

export interface SkillGraphStateListResponse {
  status: string;
  total: number;
  states: SkillGraphUserState[];
}

export interface SkillGraphImportRunListResponse {
  status: string;
  total: number;
  runs: SkillGraphImportRun[];
}

export interface SkillGraphDetailResponse {
  status: string;
  node: SkillGraphNode;
  aliases: SkillGraphAlias[];
  edges: SkillGraphEdge[];
  evidence: SkillGraphEvidence[];
  user_states: SkillGraphUserState[];
}

export interface SkillGraphImportResponse {
  status: string;
  run: SkillGraphImportRun;
  node_count: number;
  edge_count: number;
  evidence_count: number;
  alias_count: number;
  user_state_count: number;
  source_counts?: Record<string, any>;
}

export type EvaluationType = 'retrieval' | 'reranker' | 'prompt' | 'agent' | 'hallucination' | 'benchmark';
export type EvaluationStatus = 'idle' | 'running' | 'completed' | 'failed';

export interface EvaluationRun {
  id?: string;
  run_uid?: string;
  evaluation_type: EvaluationType;
  status: EvaluationStatus;
  started_at: string;
  created_at?: string;
  completed_at?: string;
  duration_ms?: number;
  trace_id?: string;
  run_id?: string;
  user_id: string;
}

export interface RetrievalMetrics {
  id: string;
  run_id: string;
  recall_5: number;
  recall_10: number;
  recall_20: number;
  precision_5: number;
  precision_10: number;
  mrr: number;
  ndcg: number;
}

export interface RerankerMetrics {
  id: string;
  run_id: string;
  improvement_score: number;
  ranking_improvement: number;
  score_distribution_before: number[];
  score_distribution_after: number[];
}

export interface PromptMetrics {
  id: string;
  run_id: string;
  prompt_name: string;
  prompt_version_id: string;
  success_rate: number;
  failure_rate: number;
  avg_latency_ms: number;
  avg_token_usage: number;
}

export interface AgentMetrics {
  id: string;
  run_id: string;
  agent_name: string;
  success_rate: number;
  failure_rate: number;
  retry_rate: number;
  avg_execution_time_ms: number;
  human_approval_rate: number;
}

export interface HallucinationReport {
  id: string;
  run_id: string;
  source_type: string;
  severity: 'high' | 'medium' | 'low';
  affected_agent: string;
  details: string;
  evidence: string;
  created_at: string;
}
