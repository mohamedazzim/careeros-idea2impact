from prometheus_client import Counter, Histogram, Gauge

# API Metrics
API_REQUEST_COUNT = Counter("api_request_count", "API requests", ["method", "endpoint", "status"])
API_LATENCY = Histogram("api_latency_seconds", "API request latency", ["method", "endpoint"])

# Retrieval Metrics
RETRIEVAL_LATENCY_HIST = Histogram("retrieval_latency_seconds", "Retrieval Pipeline Latency", ["operation"])
QDRANT_LATENCY_HIST = Histogram("qdrant_latency_seconds", "Qdrant Search Latency")
RERANK_LATENCY_HIST = Histogram("rerank_latency_seconds", "Reranker Latency")

# LLM Metrics
LLM_TOKEN_USAGE = Counter("llm_token_usage_total", "LLM Tokens", ["model", "token_type"])
LLM_LATENCY_HIST = Histogram("llm_latency_seconds", "LLM Latency", ["model", "operation"])
LLM_FAILURES = Counter("llm_failures_total", "LLM Failures", ["model", "error_type"])

# Phase 4A: Claude Intelligence Orchestration Metrics
CLAUDE_CALLS = Counter("claude_calls_total", "Claude API calls", ["model", "status"])
CLAUDE_LATENCY = Histogram("claude_latency_seconds", "Claude API latency", ["model", "operation"])
CLAUDE_COST_ESTIMATE = Histogram("claude_cost_usd", "Claude estimated cost per call")
CLAUDE_CIRCUIT_OPEN = Counter("claude_circuit_open_total", "Claude circuit breaker opened")
CLAUDE_RATE_LIMIT = Counter("claude_rate_limit_total", "Claude rate limit 429 hits")

# Phase 4A: Grounding & Hallucination Metrics
GROUNDING_FAILURES = Counter("grounding_failures_total", "Grounding guard rejections", ["reason"])
GROUNDING_SCORE = Histogram("grounding_score", "Grounding scores per response")
HALLUCINATION_DETECTED = Counter("hallucination_detected_total", "Hallucinations detected", ["severity"])
HALLUCINATION_MITIGATED = Counter("hallucination_mitigated_total", "Hallucinations mitigated", ["type"])
HALLUCINATION_RISK_SCORE = Histogram("hallucination_risk_score", "Hallucination risk scores")

# Phase 4A: Output Validation Metrics
OUTPUT_VALIDATION_FAILURES = Counter("output_validation_failures_total", "Validation failures", ["reason"])
OUTPUT_JSON_REPAIRS = Counter("output_json_repairs_total", "JSON repair attempts")
OUTPUT_SCHEMA_MISMATCH = Counter("output_schema_mismatch_total", "Schema compliance failures")

# Phase 4A: Confidence & Prompt Metrics
CONFIDENCE_DISTRIBUTION = Histogram("confidence_distribution", "Overall confidence scores")
CONFIDENCE_BREAKDOWN = Histogram("confidence_breakdown", "Confidence factor scores", ["factor"])
PROMPT_VERSION_CALLS = Counter("prompt_version_calls_total", "Prompt version usage", ["prompt_id", "version"])
PROMPT_REGRESSION = Histogram("prompt_regression", "Prompt metric regression", ["prompt_id", "metric"])

# Phase 4B Hardening: Contradiction & Recommendation Metrics
CONTRADICTION_DETECTED = Counter("contradiction_detected_total", "Contradictions detected", ["category", "severity"])
RECOMMENDATION_SUPPRESSION = Counter("recommendation_suppression_total", "Recommendations suppressed", ["reason"])
CITATION_VALIDATION_FAILURES = Counter("citation_validation_failures_total", "Citation validation failures", ["reason"])
RECRUITER_CONSISTENCY = Histogram("recruiter_consistency", "Recruiter review consistency score")

# Phase 4B Hardening: Intelligence Concurrency & Timeout
INTELLIGENCE_CONCURRENCY_PRESSURE = Histogram("intelligence_concurrency_pressure", "Concurrent intelligence stages")
INTELLIGENCE_STAGE_TIMEOUT = Counter("intelligence_stage_timeout_total", "Intelligence stage timeouts", ["stage"])
INTELLIGENCE_STAGE_LATENCY = Histogram("intelligence_stage_latency_seconds", "Intelligence stage latency", ["stage"])

# Phase 4B Hardening: Confidence Calibration Drift
CONFIDENCE_CALIBRATION_DRIFT = Histogram("confidence_calibration_drift", "Confidence calibration shift", ["factor"])
CONTRADICTION_PENALTY = Histogram("contradiction_penalty", "Contradiction penalty applied to confidence")

# Phase 4C: Career Strategy Intelligence Metrics
STRATEGY_ROADMAP_LATENCY = Histogram("strategy_roadmap_latency_seconds", "Roadmap generation latency", ["roadmap_type"])
STRATEGY_CONFIDENCE = Histogram("strategy_confidence", "Strategy confidence distributions", ["strategy_type"])
STRATEGY_RECOMMENDATION_SUPPRESSION = Counter("strategy_recommendation_suppression_total", "Strategy recommendations suppressed", ["reason"])
STRATEGY_HALLUCINATION = Counter("strategy_hallucination_total", "Strategy hallucination detections", ["strategy_type", "severity"])
STRATEGY_TRAJECTORY_CONSISTENCY = Histogram("strategy_trajectory_consistency", "Career trajectory consistency score")
STRATEGY_ROADMAP_COMPLEXITY = Histogram("strategy_roadmap_complexity", "Roadmap item count")
STRATEGY_HIRING_CONFIDENCE = Histogram("strategy_hiring_confidence", "Hiring probability confidence")
STRATEGY_AI_READINESS = Histogram("strategy_ai_readiness", "AI engineering readiness score")
STRATEGY_OPPORTUNITY_RANK = Histogram("strategy_opportunity_rank", "Opportunity prioritization scores")

# Phase 4D: Domain Governance Metrics
DOMAIN_CALL_TOTAL = Counter("domain_call_total", "Claude calls by domain", ["domain", "status"])
DOMAIN_LATENCY = Histogram("domain_latency_seconds", "Per-domain Claude latency", ["domain"])
DOMAIN_TOKEN_USAGE = Counter("domain_token_usage_total", "Per-domain token consumption", ["domain", "token_type"])
DOMAIN_SEMAPHORE_WAIT = Histogram("domain_semaphore_wait_seconds", "Semaphore acquisition wait time", ["domain"])
DOMAIN_SEMAPHORE_PRESSURE = Histogram("domain_semaphore_pressure", "Concurrent callers waiting on semaphore", ["domain"])
DOMAIN_TOKEN_PRESSURE = Histogram("domain_token_pressure", "Token budget utilization ratio", ["domain"])
DOMAIN_THROTTLE_EVENTS = Counter("domain_throttle_events_total", "Token-pressure throttling events", ["domain"])
DOMAIN_RETRY_AMPLIFICATION = Counter("domain_retry_amplification_total", "Retry attempts by domain", ["domain", "attempt"])
DOMAIN_RATE_LIMIT_HITS = Counter("domain_rate_limit_hits_total", "Rate limit hits by domain", ["domain"])
DOMAIN_TIMEOUTS = Counter("domain_timeouts_total", "Timeout events by domain", ["domain"])
DOMAIN_POSTHOC_TRUNCATIONS = Counter("domain_posthoc_truncations_total", "Post-hoc structural truncations", ["prompt_id", "field"])

# Phase 4D: Interview Intelligence Metrics
INTERVIEW_LATENCY = Histogram("interview_latency_seconds", "Interview evaluation latency", ["interview_type", "status"])
INTERVIEW_ADAPTIVE_TRANSITIONS = Counter("interview_adaptive_transitions_total", "Difficulty level transitions", ["from_level", "to_level", "reason"])
INTERVIEW_DIFFICULTY_ESCALATION = Counter("interview_difficulty_escalation_total", "Difficulty escalations by type", ["interview_type", "level"])
INTERVIEW_HALLUCINATION = Counter("interview_hallucination_total", "Interview hallucination detections", ["interview_type", "severity"])
INTERVIEW_CRITIQUE_SUPPRESSION = Counter("interview_critique_suppression_total", "Critique suppressions", ["reason"])
INTERVIEW_CONTRADICTION_PRESSURE = Counter("interview_contradiction_pressure_total", "Contradiction pressure events", ["interview_type", "severity"])
INTERVIEW_RUBRIC_CONFIDENCE = Histogram("interview_rubric_confidence", "Rubric confidence scores", ["rubric_type"])
INTERVIEW_CONCURRENCY_PRESSURE = Histogram("interview_concurrency_pressure", "Active interview sessions")
INTERVIEW_SESSION_TOKEN_PRESSURE = Histogram("interview_session_token_pressure", "Session token consumption", ["session_id"])
INTERVIEW_WEAKNESS_PATTERN = Histogram("interview_weakness_pattern", "Detected weakness pattern counts", ["pattern_type"])

# Phase 4D Hardening: Interview Runtime Safety Metrics
INTERVIEW_SESSION_DURATION = Histogram("interview_session_duration_seconds", "Total session duration", ["interview_type"])
INTERVIEW_TRANSITION_FREQUENCY = Counter("interview_transition_frequency_total", "Adaptive transition frequency", ["from_level", "to_level"])
INTERVIEW_CRITIQUE_SUPPRESSION_FREQ = Counter("interview_critique_suppression_freq_total", "Critique suppression frequency", ["reason"])
INTERVIEW_CONTRADICTION_ESCALATION_FREQ = Counter("interview_contradiction_escalation_freq_total", "Contradiction escalation frequency", ["severity"])
INTERVIEW_RETRY_AMPLIFICATION = Counter("interview_retry_amplification_total", "Interview retry amplification", ["operation", "attempt"])
INTERVIEW_MEMORY_RESTORATION = Counter("interview_memory_restoration_total", "Session recovery from persistence", ["source"])
INTERVIEW_SESSION_RECOVERY_FAILURE = Counter("interview_session_recovery_failure_total", "Failed session recovery attempts")

# Agent Metrics
AGENT_NODE_LATENCY_HIST = Histogram("agent_node_latency_seconds", "Agent Node Latency", ["node"])
AGENT_RETRIES = Counter("agent_retries_total", "Agent Retries", ["node"])
AGENT_CHECKPOINTS = Counter("agent_checkpoints_total", "Agent Checkpoints", ["node"])

# MCP Metrics
MCP_INVOCATION_COUNT = Counter("mcp_invocation_total", "MCP Invocations", ["tool"])
MCP_LATENCY_HIST = Histogram("mcp_latency_seconds", "MCP Latency", ["tool"])
MCP_FAILURES = Counter("mcp_failures_total", "MCP Failures", ["tool"])

# Document Pipeline Metrics
PARSER_COUNT = Counter("parser_requests_total", "Document parser invocations", ["format", "status"])
PARSER_LATENCY = Histogram("parser_latency_seconds", "Document parsing latency", ["format"])
PARSER_BYTES = Histogram("parser_bytes_processed", "Document bytes processed", ["format"])
PARSER_PAGE_COUNT = Histogram("parser_page_count", "Page count per document", ["format"])

# OCR Pipeline Metrics
OCR_COUNT = Counter("ocr_requests_total", "OCR processing invocations", ["trigger", "status"])
OCR_LATENCY = Histogram("ocr_latency_seconds", "OCR processing latency", ["trigger"])
OCR_CONFIDENCE = Histogram("ocr_confidence_score", "OCR confidence scores", ["trigger"])
OCR_FALLBACK_COUNT = Counter("ocr_fallback_total", "OCR fallback invocations", ["reason"])

# MIME Detection Metrics
MIME_DETECTION_COUNT = Counter("mime_detection_total", "MIME type detections", ["method", "result"])
MIME_CORRUPTED_COUNT = Counter("mime_corrupted_total", "Corrupted file detections", ["format"])
MIME_UNSUPPORTED_COUNT = Counter("mime_unsupported_total", "Unsupported format rejections", ["detected_type"])

# Phase 2C: Normalization Metrics
NORMALIZATION_COUNT = Counter("normalization_total", "Normalization pipeline invocations", ["status"])
NORMALIZATION_LATENCY = Histogram("normalization_latency_seconds", "Normalization latency")
NORMALIZATION_FIXES = Counter("normalization_fixes_total", "Text fixes applied", ["fix_type"])

# Phase 2C: Chunking Metrics
CHUNKING_COUNT = Counter("chunking_total", "Chunking pipeline invocations", ["method", "status"])
CHUNKING_LATENCY = Histogram("chunking_latency_seconds", "Chunking latency", ["method"])
CHUNK_SIZE_HIST = Histogram("chunk_size_tokens", "Chunk token distribution", ["section"])

# Phase 2C: Masking Metrics
MASKING_COUNT = Counter("masking_total", "Masking pipeline invocations", ["strategy", "status"])
MASKING_LATENCY = Histogram("masking_latency_seconds", "Masking latency")
MASKING_ENTITIES = Counter("masking_entities_total", "Entities masked", ["entity_type", "source"])
MASKING_CONFIDENCE = Histogram("masking_confidence", "Masking confidence scores", ["entity_type"])

# Phase 2C: Embedding Preparation Metrics
EMBED_PREP_COUNT = Counter("embed_prep_total", "Embedding preparation invocations", ["status"])
EMBED_PREP_LATENCY = Histogram("embed_prep_latency_seconds", "Embedding preparation latency")
EMBED_PAYLOAD_COUNT = Histogram("embed_payload_count", "Payloads per batch")
EMBED_SECTION_DISTRIBUTION = Counter("embed_section_distribution", "Chunk sections per batch", ["section"])

# Phase 3A: Embedding Service Metrics
EMBED_SERVICE_CALLS = Counter("embed_service_calls_total", "NV-Embed-v1 API calls", ["input_type", "status"])
EMBED_SERVICE_LATENCY = Histogram("embed_service_latency_seconds", "NV-Embed-v1 API latency", ["input_type"])
EMBED_SERVICE_RETRIES = Counter("embed_service_retries_total", "NV-Embed-v1 retry attempts", ["input_type"])
EMBED_SERVICE_BATCH_SIZE = Histogram("embed_service_batch_size", "Texts per embedding batch")
EMBED_SERVICE_CACHE = Counter("embed_service_cache_total", "Embedding cache hits/misses", ["result"])

# Phase 3A: Qdrant Service Metrics
QDRANT_SERVICE_INSERTS = Counter("qdrant_service_inserts_total", "Qdrant vector inserts", ["collection", "status"])
QDRANT_SERVICE_QUERIES = Counter("qdrant_service_queries_total", "Qdrant vector queries", ["collection"])
QDRANT_SERVICE_DELETES = Counter("qdrant_service_deletes_total", "Qdrant vector deletes", ["collection"])
QDRANT_POINTS_INSERTED = Histogram("qdrant_points_inserted", "Points per upsert batch", ["collection"])
QDRANT_INDEX_SIZE = Histogram("qdrant_index_size_bytes", "Qdrant collection size estimate", ["collection"])

# Phase 3A: Retrieval Service Metrics
RETRIEVAL_SERVICE_CALLS = Counter("retrieval_service_calls_total", "Retrieval pipeline invocations", ["status"])
RETRIEVAL_SERVICE_SCORES = Histogram("retrieval_service_scores", "Retrieval similarity scores")
RETRIEVAL_SERVICE_TOP_K = Histogram("retrieval_service_top_k", "Results returned per query")

# Phase 3A: Indexing Pipeline Metrics
INDEXING_COUNT = Counter("indexing_pipeline_total", "Indexing pipeline invocations", ["status"])
INDEXING_LATENCY = Histogram("indexing_latency_seconds", "Indexing pipeline latency")
INDEXING_CHUNKS_INDEXED = Counter("indexing_chunks_total", "Chunks indexed", ["collection"])
INDEXING_BATCHES = Counter("indexing_batches_total", "Indexing batches processed", ["collection"])

# Phase 3B: Resilience Metrics
EMBED_CIRCUIT_BREAKER_STATE = Counter("embed_circuit_breaker_state", "Circuit breaker state transitions", ["from_state", "to_state"])
EMBED_RATE_LIMIT_HITS = Counter("embed_rate_limit_hits_total", "Rate limit 429 responses", ["input_type"])
EMBED_QUEUE_DEPTH = Histogram("embed_queue_depth", "Backpressure queue depth")
EMBED_QUEUE_REJECTIONS = Counter("embed_queue_rejections_total", "Queue full rejections")

# Phase 3B: Retrieval Observability Metrics
RETRIEVAL_MISS_TOTAL = Counter("retrieval_miss_total", "Queries returning zero results", ["collection"])
RETRIEVAL_EMPTY_RESULTS = Counter("retrieval_empty_results_total", "Empty result sets after filtering", ["collection", "stage"])
RETRIEVAL_RERANK_FAILURES = Counter("retrieval_rerank_failures_total", "Reranker failures")
EMBED_CACHE_HIT_RATIO = Histogram("embed_cache_hit_ratio", "Embedding cache hit ratio per batch")

# Phase 3B: Payload Size Monitoring
EMBED_PAYLOAD_BYTES = Histogram("embed_payload_bytes", "Payload bytes per vector point", ["collection"])
EMBED_PAYLOAD_BLOAT = Counter("embed_payload_bloat_total", "Payloads exceeding size threshold", ["collection"])
EMBED_PAYLOAD_TRUNCATIONS = Counter("embed_payload_truncations_total", "Payload truncations applied", ["collection", "field"])

# Phase 3B: Indexing Robustness
INDEXING_PARTIAL_BATCH = Counter("indexing_partial_batch_total", "Partial batch successes", ["collection"])
INDEXING_RETRY_IDEMPOTENT = Counter("indexing_retry_idempotent_total", "Idempotent retry attempts", ["collection", "attempt"])
INDEXING_DEAD_LETTER = Counter("indexing_dead_letter_total", "Dead-letter queue enqueue events", ["collection"])

# Phase 3B: Hybrid Retrieval Metrics
HYBRID_RETRIEVAL_CALLS = Counter("hybrid_retrieval_calls_total", "Hybrid retrieval invocations", ["collection", "status"])
HYBRID_RETRIEVAL_LATENCY = Histogram("hybrid_retrieval_latency_seconds", "Hybrid retrieval total latency", ["collection"])
BM25_LATENCY = Histogram("bm25_latency_seconds", "BM25 sparse retrieval latency", ["collection"])
BM25_TOKEN_COUNT = Histogram("bm25_query_tokens", "BM25 query token count")
RRF_FUSION_LATENCY = Histogram("rrf_fusion_latency_seconds", "Reciprocal rank fusion latency")
RRF_FUSION_COUNT = Counter("rrf_fusion_total", "RRF fusion invocations")
RRF_K_PARAM = Histogram("rrf_k_parameter", "RRF k smoothing parameter")
HYBRID_RECALL_GAIN = Histogram("hybrid_recall_gain", "Hybrid vs dense-only recall gain", ["k"])

# Phase 3B: Query Understanding Metrics
QUERY_INTENT_COUNT = Counter("query_intent_total", "Query intent classifications", ["intent"])
QUERY_EXPANSION_COUNT = Counter("query_expansion_total", "Query expansion invocations")
QUERY_EXPANDED_TERMS = Histogram("query_expanded_terms", "Expanded terms per query")
QUERY_SKILL_EXTRACTIONS = Counter("query_skill_extractions_total", "Skills extracted from queries")

# Phase 3B: Retrieval Routing Metrics
RETRIEVAL_ROUTING_COUNT = Counter("retrieval_routing_total", "Routing decisions", ["route", "collection"])
RETRIEVAL_FEDERATED_COUNT = Counter("retrieval_federated_total", "Federated retrieval invocations")
ROUTING_CONFIDENCE = Histogram("routing_confidence", "Routing confidence scores")

# Phase 3B: Context Compression Metrics
CONTEXT_COMPRESSION_COUNT = Counter("context_compression_total", "Context compression invocations")
CONTEXT_COMPRESSION_TOKENS_SAVED = Histogram("context_compression_tokens_saved", "Tokens saved by compression")
CONTEXT_COMPRESSION_RATIO = Histogram("context_compression_ratio", "Compression ratio (compressed/original)")
CONTEXT_DEDUP_REMOVED = Counter("context_dedup_removed_total", "Deduplicated chunk count")
CONTEXT_OVERLAP_REMOVED = Counter("context_overlap_removed_total", "Overlap-reduced chunk count")

# Phase 3B: Reranking Observability
RERANK_CONFIDENCE = Histogram("rerank_confidence", "Reranker confidence scores")
RERANK_SCORE_DISTRIBUTION = Histogram("rerank_score_distribution", "Reranker score distribution")
RERANK_RANK_INVERSION = Histogram("rerank_rank_inversion", "Rank inversion between dense and reranked")
RERANK_SKILL_PRIORITY_BOOST = Counter("rerank_skill_priority_boost_total", "Skill priority boosts applied")

# Phase 3B: Evaluation Metrics
RETRIEVAL_RECALL = Histogram("retrieval_recall_at_k", "Recall@K", ["k"])
RETRIEVAL_PRECISION = Histogram("retrieval_precision_at_k", "Precision@K", ["k"])
RETRIEVAL_MRR = Histogram("retrieval_mrr", "Mean Reciprocal Rank")
RETRIEVAL_NDCG = Histogram("retrieval_ndcg_at_k", "NDCG@K", ["k"])
RETRIEVAL_CONSISTENCY = Histogram("retrieval_consistency", "Retrieval consistency score")
HALLUCINATION_RISK = Histogram("hallucination_risk", "Hallucination risk score")

# Phase 3B Hardening: Retrieval Cache Metrics
RETRIEVAL_CACHE_HIT = Counter("retrieval_cache_hit_total", "Retrieval cache hits", ["level"])
RETRIEVAL_CACHE_MISS = Counter("retrieval_cache_miss_total", "Retrieval cache misses", ["level"])
RETRIEVAL_CACHE_WRITE = Counter("retrieval_cache_write_total", "Retrieval cache writes", ["level"])

# Phase 3B Hardening: BM25 Persistence Metrics
BM25_PERSIST_SAVES = Counter("bm25_persist_saves_total", "BM25 index persistence saves", ["collection"])
BM25_PERSIST_LOADS = Counter("bm25_persist_loads_total", "BM25 index persistence loads", ["collection"])
BM25_PERSIST_BYTES = Histogram("bm25_persist_bytes", "BM25 persisted index bytes", ["collection"])
BM25_PERSIST_LATENCY = Histogram("bm25_persist_latency_seconds", "BM25 persist latency", ["operation", "collection"])
BM25_INDEX_SIZE = Histogram("bm25_index_size", "BM25 index doc count", ["collection"])
BM25_INDEX_MEMORY_BYTES = Histogram("bm25_index_memory_bytes", "BM25 index memory footprint", ["collection"])

# Phase 3B Hardening: Drift Monitoring Metrics
RETRIEVAL_DRIFT_SCORE = Histogram("retrieval_drift_score", "Drift score per metric", ["metric"])
DRIFT_ALERT_TRIGGERED = Counter("drift_alert_triggered_total", "Drift alerts triggered")
GOLDEN_QUERY_REGRESSION = Histogram("golden_query_regression", "Golden query benchmark regression", ["metric"])

# Phase 3B Hardening: Reranker Resilience
RERANK_CIRCUIT_OPEN = Counter("rerank_circuit_open_total", "Reranker circuit breaker opened")
RERANK_FALLBACK_USED = Counter("rerank_fallback_used_total", "Reranker fallback strategy invoked", ["strategy"])
RERANK_TIMEOUT = Counter("rerank_timeout_total", "Reranker timeout events")
RERANK_RATE_LIMIT = Counter("rerank_rate_limit_total", "Reranker rate limit hits")

# Phase 3B Hardening: Context Integrity
CONTEXT_OVERFLOW = Counter("context_overflow_total", "Context token-budget overflow events", ["severity"])
CONTEXT_CITATION_ORPHAN = Counter("context_citation_orphan_total", "Orphaned citations detected")
CONTEXT_CHRONOLOGY_VIOLATION = Counter("context_chronology_violation_total", "Chronology violations detected")
CONTEXT_OVERLAP_CORRUPTION = Counter("context_overlap_corruption_total", "Overlap corruption detected", ["severity"])

# Phase 3B Hardening: Federated Retrieval
FEDERATION_DEDUP_REMOVED = Counter("federation_dedup_removed_total", "Cross-collection duplicate removals")
FEDERATION_COLLECTION_COUNT = Histogram("federation_collection_count", "Collections per federated query")
FEDERATION_LATENCY = Histogram("federation_latency_seconds", "Federated retrieval total latency")
FEDERATION_SCORE_NORMALIZE = Counter("federation_score_normalize_total", "Score normalization invocations", ["collection"])

# ── Phase 5: Agentic MCP Orchestration ───────────────────────────────

AGENT_EXECUTION_COUNT = Counter("agent_execution_total", "Agent executions", ["agent_name", "status"])
AGENT_EXECUTION_LATENCY = Histogram("agent_execution_latency_seconds", "Agent execution latency", ["agent_name"])
ORCHESTRATION_FAILURES = Counter("orchestration_failures_total", "Orchestration failures", ["node_name", "reason"])
GRAPH_RESUME_COUNT = Counter("graph_resume_total", "Graph resume invocations", ["graph_name"])
MCP_EXECUTION_TOTAL = Counter("mcp_execution_total", "MCP tool executions", ["tool_name", "status"])
MCP_EXECUTION_LATENCY = Histogram("mcp_execution_latency_ms", "MCP tool execution latency ms", ["tool_name"])
MCP_EXECUTION_FAILURES = Counter("mcp_execution_failures_total", "MCP execution failures", ["tool_name", "reason"])
MCP_RETRY_AMPLIFICATION = Counter("mcp_retry_amplification_total", "MCP retry amplification", ["tool_name", "attempt"])
AUTONOMOUS_ACTION_COUNT = Counter("autonomous_action_total", "Autonomous actions taken", ["action_type", "status"])
NOTIFICATION_SUPPRESSION_COUNT = Counter("notification_suppression_total", "Notifications suppressed", ["reason"])
RECURSION_PREVENTION_COUNT = Counter("recursion_prevention_total", "Recursion preventions triggered")
VOICE_CALL_LATENCY = Histogram("voice_call_latency_seconds", "Voice call end-to-end latency", ["stage"])
OPPORTUNITY_PROCESSING_LATENCY = Histogram("opportunity_processing_latency_seconds", "Opportunity processing latency", ["stage"])
ORCHESTRATION_SESSION_GAUGE = Gauge("orchestration_active_sessions", "Active orchestration sessions")
AGENT_CONFIDENCE_GAUGE = Gauge("agent_confidence_current", "Agent confidence score", ["agent_name"])
GOVERNANCE_DECISION_COUNT = Counter("governance_decision_total", "Governance decisions", ["decision_type", "verdict"])
EVENT_BUS_QUEUE_DEPTH_GAUGE = Gauge("event_bus_queue_depth", "Event bus queue depth")

# ── Phase 6: Distributed Autonomous Runtime Metrics ──────────────────

WORKER_ACTIVE_GAUGE = Gauge("worker_active_total", "Active orchestration workers")
WORKER_EXECUTIONS_GAUGE = Gauge("worker_executions_active", "Active executions per worker", ["worker_id"])
QUEUE_PRIORITY_DEPTH_GAUGE = Gauge("queue_priority_depth", "Priority queue depth")
QUEUE_RETRY_DEPTH_GAUGE = Gauge("queue_retry_depth", "Retry queue depth")
QUEUE_DEAD_LETTER_GAUGE = Gauge("queue_dead_letter_depth", "Dead letter queue depth")
ORCHESTRATION_REPLAY_TOTAL = Counter("orchestration_replay_total", "Orchestration replays", ["status"])
ORCHESTRATION_RESUME_TOTAL = Counter("orchestration_resume_total", "Orchestration resumes", ["status"])
LOCK_ACQUISITION_TOTAL = Counter("lock_acquisition_total", "Lock acquisitions", ["result"])
LOCK_LEASE_RENEWALS = Counter("lock_lease_renewals_total", "Lock lease renewals", ["status"])
SCHEDULER_JOB_EXECUTIONS = Counter("scheduler_job_executions_total", "Scheduled job executions", ["job_name", "status"])
DISTRIBUTED_OWNERSHIP_CONFLICTS = Counter("distributed_ownership_conflicts_total", "Distributed lock conflicts")
RETRY_EXHAUSTION_TOTAL = Counter("retry_exhaustion_total", "Retry exhaustion events", ["reason"])
DEAD_LETTER_REPLAY_TOTAL = Counter("dead_letter_replay_total", "Dead letter replays", ["status"])
WEBSOCKET_CONNECTIONS = Gauge("websocket_connections", "Active WebSocket connections")
STREAM_EVENTS_TOTAL = Counter("stream_events_total", "Stream events published", ["event_type"])
HUMAN_LOOP_PENDING = Gauge("human_loop_approvals_pending", "Pending human-in-the-loop approvals")
HUMAN_LOOP_OVERRIDES = Counter("human_loop_overrides_total", "Governance overrides by humans")
HUMAN_LOOP_ESCALATIONS = Counter("human_loop_escalations_total", "Escalations triggered", ["severity"])

# ── Phase 7: Real-Time Multimodal Interview Metrics ──────────────────

INTERVIEW_STT_LATENCY = Histogram("interview_stt_latency_ms", "Speech-to-text latency", ["provider"])
INTERVIEW_TTS_LATENCY = Histogram("interview_tts_latency_ms", "Text-to-speech latency", ["voice"])
INTERVIEW_WEBSOCKET_LATENCY = Histogram("interview_websocket_latency_ms", "WebSocket message latency", ["event_type"])
INTERVIEW_SESSION_GAUGE = Gauge("interview_active_sessions", "Active interview sessions")
INTERVIEW_RESPONSE_TIME = Histogram("interview_response_time_ms", "AI response generation time", ["interview_type"])
INTERVIEW_QUESTION_GENERATION_LATENCY = Histogram("interview_question_generation_latency_ms", "Question gen latency")
INTERVIEW_EVALUATION_LATENCY = Histogram("interview_evaluation_latency_ms", "Response evaluation latency")
INTERVIEW_INTERRUPTION_COUNT = Counter("interview_interruption_total", "User interruptions", ["reason"])
INTERVIEW_REPLAY_TOTAL = Counter("interview_replay_total", "Interview replays", ["status"])
INTERVIEW_MODERATION_FLAGS = Counter("interview_moderation_flags_total", "Moderation violations detected", ["severity"])
INTERVIEW_SESSION_KILL_COUNT = Counter("interview_session_kill_total", "Session kill-switch activations")
INTERVIEW_AUDIO_BUFFER_PRESSURE = Histogram("interview_audio_buffer_depth", "Audio buffer items per stream")
INTERVIEW_STREAMING_BACKPRESSURE = Counter("interview_streaming_backpressure_total", "Streaming backpressure events")
INTERVIEW_PROVIDER_FAILOVER = Counter("interview_provider_failover_total", "STT/TTS provider failovers", ["from_provider", "to_provider"])

# ── Phase 8: True Realtime Voice Metrics ──────────────────────────

AUDIO_CHUNK_LATENCY = Histogram("audio_chunk_latency_ms", "Audio chunk transport latency", ["direction"])
WEBSOCKET_AUDIO_BYTES = Counter("websocket_audio_bytes_total", "Audio bytes over WebSocket", ["direction"])
VOICE_ACTIVITY_EVENTS = Counter("voice_activity_events_total", "VAD state transitions", ["transition"])
INTERRUPTION_LATENCY = Histogram("interruption_latency_ms", "Barge-in detection to TTS stop latency")
DUPLEX_TURN_COUNT = Counter("duplex_turn_total", "Conversation turns", ["role"])
SILENCE_TIMEOUT_COUNT = Counter("silence_timeout_total", "Silence timeout events", ["session_type"])
TRANSCRIPT_QUALITY = Histogram("transcript_confidence", "STT transcript confidence scores", ["provider"])
TTS_CHUNK_LATENCY = Histogram("tts_chunk_latency_ms", "TTS chunk generation latency", ["voice"])
WEBSOCKET_RTT = Histogram("websocket_rtt_ms", "WebSocket round-trip time")
DISTRIBUTED_NODE_COUNT = Gauge("distributed_node_count", "Active distributed nodes")
SESSION_OWNERSHIP_TRANSFERS = Counter("session_ownership_transfers_total", "Session ownership transfers between nodes")

# ── Phase 13: Realtime Interview Intelligence Metrics ────────────────

INTERVIEW_WS_CONNECTED = Gauge("interview_ws_connected", "Interview WebSocket connections")
INTERVIEW_WS_DISCONNECTS = Counter("interview_ws_disconnects_total", "Interview WebSocket disconnects")
INTERVIEW_WS_RECONNECTS = Counter("interview_ws_reconnects_total", "Interview WebSocket reconnects")
INTERVIEW_WS_LATENCY_MS = Histogram("interview_ws_latency_ms", "Interview WebSocket round-trip latency")
INTERVIEW_TRANSCRIPT_LATENCY = Histogram("interview_transcript_latency_ms", "Transcript delivery latency", ["type"])
INTERVIEW_AI_RESPONSE_LATENCY = Histogram("interview_ai_response_latency_ms", "AI response latency")
INTERVIEW_DURATION = Histogram("interview_duration_seconds", "Interview session duration")
INTERVIEW_STT_PARTIAL = Counter("interview_stt_partial_total", "Partial STT transcripts")
INTERVIEW_STT_FINAL = Counter("interview_stt_final_total", "Final STT transcripts")
INTERVIEW_FEEDBACK_STREAMED = Counter("interview_feedback_streamed_total", "Live feedback events streamed")
INTERVIEW_GRAPH_NODE_LATENCY = Histogram("interview_graph_node_latency_ms", "Interview graph node latency", ["node"])
