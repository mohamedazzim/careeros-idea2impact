---
title: "Configuration And Environment Variables"
document_id: "21_configuration_and_environment_variables"
domain: "ops"
feature: "configuration"
audience:
  - user
  - developer
  - operator
implementation_status: "IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - configuration
  - environment
---

# Configuration And Environment Variables

Configuration is centralized in `backend/src/core/config.py::Settings`. This document lists discovered settings without exposing secrets.

## Settings Inventory

| Variable | Type | Safe default / placeholder | Source |
| --- | --- | --- | --- |
| `PROJECT_NAME` | `str` | `"CareerOS AI Enterprise"` | `backend/src/core/config.py::Settings` |
| `BACKEND_CORS_ORIGINS` | `List[str]` | `Field(` | `backend/src/core/config.py::Settings` |
| `ENVIRONMENT` | `str` | `"development"` | `backend/src/core/config.py::Settings` |
| `SECRET_KEY` | `str` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `ALGORITHM` | `str` | `"HS256"` | `backend/src/core/config.py::Settings` |
| `POSTGRES_USER` | `str` | `"postgres"` | `backend/src/core/config.py::Settings` |
| `POSTGRES_PASSWORD` | `str` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `POSTGRES_DB` | `str` | `"careeros_db"` | `backend/src/core/config.py::Settings` |
| `DATABASE_URL` | `str` | `"postgresql+asyncpg://postgres:data@localhost:5432/careeros_db"` | `backend/src/core/config.py::Settings` |
| `REDIS_URL` | `str` | `"redis://localhost:6379/0"` | `backend/src/core/config.py::Settings` |
| `REDIS_HOST` | `str` | `"localhost"` | `backend/src/core/config.py::Settings` |
| `REDIS_PORT` | `int` | `6379` | `backend/src/core/config.py::Settings` |
| `REDIS_DB` | `int` | `0` | `backend/src/core/config.py::Settings` |
| `QDRANT_URL` | `str` | `"http://localhost:6333"` | `backend/src/core/config.py::Settings` |
| `QDRANT_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `AWS_ACCESS_KEY_ID` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `AWS_SECRET_ACCESS_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `AWS_REGION` | `str` | `"us-east-1"` | `backend/src/core/config.py::Settings` |
| `S3_BUCKET_NAME` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `S3_ENDPOINT_URL` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `STORAGE_TYPE` | `str` | `"local"` | `backend/src/core/config.py::Settings` |
| `STORAGE_BASE_PATH` | `str` | `"/tmp/careeros_storage"` | `backend/src/core/config.py::Settings` |
| `NVIDIA_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `NVIDIA_NIM_BASE_URL` | `str` | `"https://integrate.api.nvidia.com/v1"` | `backend/src/core/config.py::Settings` |
| `DEEPSEEK_MODEL` | `str` | `"meta/llama-3.3-70b-instruct"` | `backend/src/core/config.py::Settings` |
| `PRIMARY_LLM_PROVIDER` | `str` | `"gemini"` | `backend/src/core/config.py::Settings` |
| `PRIMARY_LLM_MODEL` | `str` | `"gemini-2.5-flash"` | `backend/src/core/config.py::Settings` |
| `GEMINI_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `GEMINI_PRIMARY_MODEL` | `str` | `"gemini-2.5-flash"` | `backend/src/core/config.py::Settings` |
| `GEMINI_REASONING_MODEL` | `str` | `"gemini-2.5-flash"` | `backend/src/core/config.py::Settings` |
| `GEMINI_TIMEOUT` | `int` | `60` | `backend/src/core/config.py::Settings` |
| `GEMINI_MAX_RETRIES` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `FALLBACK_LLM_PROVIDER` | `str` | `"deepseek"` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_1` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_2` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_3` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_4` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_5` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_6` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_7` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_8` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_9` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_10` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_11` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_12` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_13` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_14` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_KEY_15` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_1` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_2` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_3` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_4` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_5` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_6` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_7` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_8` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_9` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_10` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_11` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_12` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_13` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_14` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_API_URL_15` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_BASE_URL` | `str` | `"https://api.theirstack.com"` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_TIMEOUT_SECONDS` | `int` | `30` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_MAX_RETRIES` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_RETRY_BACKOFF_BASE` | `float` | `1.5` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_RESULTS_PER_QUERY` | `int` | `25` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_POSTED_MAX_AGE_DAYS` | `int` | `14` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_MAX_QUERIES_PER_REFRESH` | `int` | `5` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_MAX_KEY_SLOTS` | `int` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_JOB_FETCH_LIMIT` | `int` | `10` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_JOB_FETCH_DAYS` | `int` | `7` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_ENABLE_FREE_COUNT_PREVIEW` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_COMPANY_TYPE` | `str` | `"direct_employer"` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_COUNTRY_CODES` | `List[str]` | `Field(default_factory=lambda: ["IN"])` | `backend/src/core/config.py::Settings` |
| `THEIRSTACK_EMPLOYMENT_STATUSES` | `List[str]` | `Field(default_factory=lambda: ["full_time"])` | `backend/src/core/config.py::Settings` |
| `TWILIO_ACCOUNT_SID` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `TWILIO_AUTH_TOKEN` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `TWILIO_PHONE_NUMBER` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `TWILIO_TEST_PHONE_NUMBER` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `ELEVENLABS_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `ELEVENLABS_CONVAI_AGENT_ID` | `Optional[str]` | `Field(` | `backend/src/core/config.py::Settings` |
| `ELEVENLABS_CONVAI_PHONE_NUMBER_ID` | `Optional[str]` | `Field(` | `backend/src/core/config.py::Settings` |
| `ELEVENLABS_CONVAI_RINGING_TIMEOUT_SECS` | `int` | `60` | `backend/src/core/config.py::Settings` |
| `DEEPGRAM_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `PIPEDREAM_WEBHOOK_URL` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `MAKE_RAG_WEBHOOK_URL` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `MAKE_RAG_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `QDRANT_RAG_DOCS_COLLECTION` | `str` | `"careeros_rag_docs"` | `backend/src/core/config.py::Settings` |
| `RAG_EMBEDDING_MODEL` | `str` | `"nvidia/nv-embed-v1"` | `backend/src/core/config.py::Settings` |
| `RAG_LLM_MODEL` | `str` | `"gemini-2.5-flash"` | `backend/src/core/config.py::Settings` |
| `RAG_USE_MAKE` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `CLAUDE_MODEL` | `str` | `"gemini-2.5-flash"` | `backend/src/core/config.py::Settings` |
| `CLAUDE_MAX_TOKENS` | `int` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `CLAUDE_TEMPERATURE` | `float` | `0.0` | `backend/src/core/config.py::Settings` |
| `CLAUDE_TIMEOUT` | `int` | `60` | `backend/src/core/config.py::Settings` |
| `CLAUDE_MAX_RETRIES` | `int` | `2` | `backend/src/core/config.py::Settings` |
| `CLAUDE_RETRY_BASE_DELAY` | `float` | `2.0` | `backend/src/core/config.py::Settings` |
| `CLAUDE_CIRCUIT_BREAKER_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `CLAUDE_CIRCUIT_THRESHOLD` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `CLAUDE_CIRCUIT_RECOVERY` | `int` | `90` | `backend/src/core/config.py::Settings` |
| `CLAUDE_COST_BUDGET_PER_CALL` | `float` | `0.10` | `backend/src/core/config.py::Settings` |
| `CLAUDE_STREAMING_ENABLED` | `bool` | `False` | `backend/src/core/config.py::Settings` |
| `CLAUDE_RATE_LIMIT_RPM` | `int` | `50` | `backend/src/core/config.py::Settings` |
| `PROMPT_VERSIONING_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `PROMPT_REGRESSION_CHECK_ENABLED` | `bool` | `False` | `backend/src/core/config.py::Settings` |
| `PROMPT_REGISTRY_BACKEND` | `str` | `"disk"` | `backend/src/core/config.py::Settings` |
| `LANGSMITH_ENABLED` | `bool` | `False` | `backend/src/core/config.py::Settings` |
| `LANGSMITH_FAIL_OPEN` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `LANGSMITH_429_COOLDOWN_SECONDS` | `int` | `3600` | `backend/src/core/config.py::Settings` |
| `LANGCHAIN_TRACING_V2` | `bool` | `False` | `backend/src/core/config.py::Settings` |
| `LANGCHAIN_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `LANGCHAIN_PROJECT` | `str` | `"careeros"` | `backend/src/core/config.py::Settings` |
| `LANGCHAIN_ENDPOINT` | `str` | `"https://api.smith.langchain.com"` | `backend/src/core/config.py::Settings` |
| `WORKER_MAX_JOBS` | `int` | `10` | `backend/src/core/config.py::Settings` |
| `WORKER_JOB_TIMEOUT` | `int` | `300` | `backend/src/core/config.py::Settings` |
| `WORKER_RETRY_DELAY` | `int` | `60` | `backend/src/core/config.py::Settings` |
| `WORKER_MAX_RETRIES` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `TASK_MAX_RETRIES` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `TASK_RETRY_DELAY_SECONDS` | `int` | `60` | `backend/src/core/config.py::Settings` |
| `RETRIEVAL_CACHE_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `RETRIEVAL_CACHE_TTL` | `int` | `900` | `backend/src/core/config.py::Settings` |
| `RETRIEVAL_CACHE_TTL_RERANK` | `int` | `1800` | `backend/src/core/config.py::Settings` |
| `RETRIEVAL_CACHE_TTL_CONTEXT` | `int` | `300` | `backend/src/core/config.py::Settings` |
| `RETRIEVAL_CACHE_TTL_ROUTING` | `int` | `3600` | `backend/src/core/config.py::Settings` |
| `RETRIEVAL_CACHE_TTL_QUERY_UNDERSTANDING` | `int` | `86400` | `backend/src/core/config.py::Settings` |
| `RETRIEVAL_CACHE_KEY_PREFIX` | `str` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `CHECKPOINT_DB_PATH` | `str` | `"./data/langgraph_checkpoints.db"` | `backend/src/core/config.py::Settings` |
| `BM25_PERSIST_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `BM25_PERSIST_PATH` | `str` | `"data/bm25"` | `backend/src/core/config.py::Settings` |
| `BM25_STALENESS_TTL` | `int` | `3600` | `backend/src/core/config.py::Settings` |
| `BM25_MAX_COLLECTIONS` | `int` | `5` | `backend/src/core/config.py::Settings` |
| `BM25_STORAGE_TYPE` | `str` | `"redis"` | `backend/src/core/config.py::Settings` |
| `BM25_REDIS_NS` | `str` | `"bm25:"` | `backend/src/core/config.py::Settings` |
| `CALL_ALERT_MIN_MATCH_SCORE` | `int` | `65` | `backend/src/core/config.py::Settings` |
| `CALL_ALERT_DRY_RUN` | `bool` | `False` | `backend/src/core/config.py::Settings` |
| `CALL_ALERT_COOLDOWN_HOURS` | `int` | `24` | `backend/src/core/config.py::Settings` |
| `OUTBOUND_CALL_DRY_RUN` | `bool` | `False` | `backend/src/core/config.py::Settings` |
| `OUTBOUND_TEST_TO_NUMBER` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `JOB_AUTO_REFRESH_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `JOB_AUTO_REFRESH_INTERVAL_MINUTES` | `int` | `30` | `backend/src/core/config.py::Settings` |
| `JOB_AUTO_REFRESH_EMBED_BATCH_SIZE` | `int` | `50` | `backend/src/core/config.py::Settings` |
| `RERANKER_TIMEOUT` | `int` | `30` | `backend/src/core/config.py::Settings` |
| `RERANKER_MAX_RETRIES` | `int` | `2` | `backend/src/core/config.py::Settings` |
| `RERANKER_RETRY_BASE_DELAY` | `float` | `1.0` | `backend/src/core/config.py::Settings` |
| `RERANKER_CIRCUIT_BREAKER_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `RERANKER_CIRCUIT_THRESHOLD` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `RERANKER_MAX_BATCH_SIZE` | `int` | `50` | `backend/src/core/config.py::Settings` |
| `RERANKER_FALLBACK_STRATEGY` | `str` | `"score_sort"` | `backend/src/core/config.py::Settings` |
| `FEDERATION_MAX_CONCURRENT` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `FEDERATION_TIMEOUT` | `int` | `10` | `backend/src/core/config.py::Settings` |
| `FEDERATION_DEDUP_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `FEDERATION_SCORE_NORMALIZE` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `FEDERATION_RESULT_LIMIT` | `int` | `50` | `backend/src/core/config.py::Settings` |
| `DRIFT_THRESHOLD_RECALL` | `float` | `0.15` | `backend/src/core/config.py::Settings` |
| `DRIFT_THRESHOLD_MRR` | `float` | `0.20` | `backend/src/core/config.py::Settings` |
| `DRIFT_THRESHOLD_CONSISTENCY` | `float` | `0.25` | `backend/src/core/config.py::Settings` |
| `DRIFT_CHECK_WINDOW` | `int` | `100` | `backend/src/core/config.py::Settings` |
| `GOLDEN_QUERIES_PATH` | `str` | `"data/golden_queries.json"` | `backend/src/core/config.py::Settings` |
| `DRIFT_ALERT_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `DRIFT_CHECK_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `CONTEXT_MAX_TOKENS` | `int` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `CONTEXT_HARD_OVERFLOW_CUTOFF` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `CONTEXT_MIN_CHUNKS_PER_SOURCE` | `int` | `1` | `backend/src/core/config.py::Settings` |
| `CONTEXT_CHRONOLOGY_PRESERVE` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `CONTEXT_CITATION_PRESERVE` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `STRATEGY_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `STRATEGY_MAX_CONCURRENT` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `STRATEGY_STAGE_TIMEOUT` | `int` | `60` | `backend/src/core/config.py::Settings` |
| `STRATEGY_ROADMAP_MAX_ITEMS` | `int` | `15` | `backend/src/core/config.py::Settings` |
| `STRATEGY_CONFIDENCE_THRESHOLD` | `float` | `0.3` | `backend/src/core/config.py::Settings` |
| `STRATEGY_HALLUCINATION_CHECK_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `STRATEGY_EXPLAINABILITY_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `STRATEGY_CONFIDENCE_BASE` | `float` | `0.5` | `backend/src/core/config.py::Settings` |
| `STRATEGY_CONFIDENCE_COMPLETENESS_WEIGHT` | `float` | `0.75` | `backend/src/core/config.py::Settings` |
| `STRATEGY_TOKEN_PRESSURE_THRESHOLD` | `int` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `STRATEGY_MARKET_ANALYSIS_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_REDIS_KEY_PREFIX` | `str` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_SESSION_TTL` | `int` | `3600` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_SESSION_MAX` | `int` | `50` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_QUESTIONS_MAX` | `int` | `20` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_ESCALATION_CAP` | `int` | `2` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_CONCURRENT_EVALUATIONS` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_TOKEN_BUDGET` | `int` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_TIMEOUT_EVALUATION` | `int` | `30` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_TIMEOUT_QUESTION` | `int` | `20` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_TIMEOUT_FEEDBACK` | `int` | `30` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_RETRY_MAX` | `int` | `2` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_RETRY_BASE_DELAY` | `float` | `1.5` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_ORPHAN_TTL` | `int` | `900` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_STREAMING_BUFFER_SIZE` | `int` | `64` | `backend/src/core/config.py::Settings` |
| `INTERVIEW_SANDBOX_ENABLED` | `bool` | `False` | `backend/src/core/config.py::Settings` |
| `ORCHESTRATION_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `ORCHESTRATION_MAX_RETRIES` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `ORCHESTRATION_TIMEOUT_SECONDS` | `int` | `300` | `backend/src/core/config.py::Settings` |
| `ORCHESTRATION_RECURSION_DEPTH_MAX` | `int` | `5` | `backend/src/core/config.py::Settings` |
| `ORCHESTRATION_MAX_AUTONOMOUS_ACTIONS` | `int` | `10` | `backend/src/core/config.py::Settings` |
| `ORCHESTRATION_MIN_CONFIDENCE_FOR_ACTION` | `float` | `0.75` | `backend/src/core/config.py::Settings` |
| `ORCHESTRATION_SESSION_TTL` | `int` | `7200` | `backend/src/core/config.py::Settings` |
| `ORCHESTRATION_REDIS_KEY_PREFIX` | `str` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `ORCHESTRATION_DEAD_LETTER_TTL` | `int` | `86400` | `backend/src/core/config.py::Settings` |
| `ORCHESTRATION_EVENT_RETENTION` | `int` | `1000` | `backend/src/core/config.py::Settings` |
| `ORCHESTRATION_MAX_CONCURRENT_AGENTS` | `int` | `5` | `backend/src/core/config.py::Settings` |
| `MCP_TOOL_TIMEOUT` | `int` | `30` | `backend/src/core/config.py::Settings` |
| `MCP_MAX_RETRIES` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `MCP_RETRY_BACKOFF_BASE` | `float` | `1.5` | `backend/src/core/config.py::Settings` |
| `MOCK_MCP` | `bool` | `False` | `backend/src/core/config.py::Settings` |
| `VOICE_CALL_TIMEOUT` | `int` | `60` | `backend/src/core/config.py::Settings` |
| `VOICE_CALL_MAX_RETRIES` | `int` | `2` | `backend/src/core/config.py::Settings` |
| `VOICE_ELEVENLABS_VOICE_ID` | `str` | `"default"` | `backend/src/core/config.py::Settings` |
| `VOICE_ELEVENLABS_MODEL` | `str` | `"eleven_multilingual_v2"` | `backend/src/core/config.py::Settings` |
| `VOICE_NOTIFICATION_MIN_URGENCY` | `float` | `0.60` | `backend/src/core/config.py::Settings` |
| `OPPORTUNITY_MATCH_WEIGHTS` | `dict` | `{` | `backend/src/core/config.py::Settings` |
| `OPPORTUNITY_MIN_SCORE_FOR_ACTION` | `float` | `65.0` | `backend/src/core/config.py::Settings` |
| `OPPORTUNITY_VOICE_CALL_MIN_SCORE` | `float` | `80.0` | `backend/src/core/config.py::Settings` |
| `OPPORTUNITY_GOVERNANCE_BLOCK_SCORE` | `float` | `94.0` | `backend/src/core/config.py::Settings` |
| `OPPORTUNITY_POSTED_WITHIN_HOURS` | `int` | `32` | `backend/src/core/config.py::Settings` |
| `OPPORTUNITY_HISTORY_TTL` | `int` | `86400 * 7` | `backend/src/core/config.py::Settings` |
| `AGENT_AUTONOMOUS_CAP_PER_SESSION` | `int` | `5` | `backend/src/core/config.py::Settings` |
| `AGENT_RECURSION_DEPTH_MAX` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `AGENT_DUPLICATE_NOTIFICATION_TTL` | `int` | `3600` | `backend/src/core/config.py::Settings` |
| `AGENT_CONFIDENCE_FLOOR` | `float` | `0.15` | `backend/src/core/config.py::Settings` |
| `JOB_TARGET_COUNTRY` | `str` | `"IN"` | `backend/src/core/config.py::Settings` |
| `JOB_TARGET_MARKET` | `str` | `"India"` | `backend/src/core/config.py::Settings` |
| `JOB_ALLOW_GLOBAL_REMOTE` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `JOB_MAX_AGE_DAYS` | `int` | `30` | `backend/src/core/config.py::Settings` |
| `JOB_REQUIRE_SOURCE_URL` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `JOB_PROVIDER_FETCH_LIMIT` | `int` | `200` | `backend/src/core/config.py::Settings` |
| `LEARNING_RESOURCES_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `LEARNING_RESOURCE_DISCOVERY_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `LEARNING_RESOURCE_PROVIDER` | `str` | `"seeded+dynamic"` | `backend/src/core/config.py::Settings` |
| `LEARNING_RESOURCE_CACHE_TTL_HOURS` | `int` | `168` | `backend/src/core/config.py::Settings` |
| `LEARNING_RESOURCE_MIN_RESULTS_PER_SKILL` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `LEARNING_RESOURCE_MAX_RESULTS_PER_SKILL` | `int` | `8` | `backend/src/core/config.py::Settings` |
| `LEARNING_WEB_SEARCH_PROVIDER` | `str` | `"tavily"` | `backend/src/core/config.py::Settings` |
| `LEARNING_WEB_SEARCH_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `LEARNING_WEB_SEARCH_TIMEOUT_SECONDS` | `int` | `20` | `backend/src/core/config.py::Settings` |
| `BRAVE_SEARCH_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `SERPAPI_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `TAVILY_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `GOOGLE_CSE_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `GOOGLE_CSE_CX` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `UDEMY_CLIENT_ID` | `Optional[str]` | `None` | `backend/src/core/config.py::Settings` |
| `UDEMY_CLIENT_SECRET` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `UDEMY_AFFILIATE_ENABLED` | `bool` | `False` | `backend/src/core/config.py::Settings` |
| `COURSERA_DISCOVERY_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `LEARNING_WEB_SEARCH_ALLOWED_DOMAINS` | `List[str]` | `Field(` | `backend/src/core/config.py::Settings` |
| `YOUTUBE_API_KEY` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `GITHUB_REPO_DISCOVERY_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |
| `GITHUB_TOKEN` | `Optional[str]` | `<secret or credential value omitted>` | `backend/src/core/config.py::Settings` |
| `GITHUB_REPO_CACHE_TTL_HOURS` | `int` | `168` | `backend/src/core/config.py::Settings` |
| `GITHUB_REPO_MIN_RESULTS_PER_SKILL` | `int` | `3` | `backend/src/core/config.py::Settings` |
| `GITHUB_REPO_MAX_RESULTS_PER_SKILL` | `int` | `6` | `backend/src/core/config.py::Settings` |
| `GITHUB_ISSUE_DISCOVERY_ENABLED` | `bool` | `True` | `backend/src/core/config.py::Settings` |


## High-Risk Configuration Areas

- Production startup rejects weak secrets and localhost infrastructure values.
- Provider keys and tokens must be supplied through environment or secret management, never committed documentation.
- Voice calls require consistent ElevenLabs agent ID, ElevenLabs phone number ID, recipient phone number, and either direct API credentials or the Pipedream bridge URL.
- Docs-RAG indexing requires Qdrant availability and embedding provider credentials.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/core/config.py`
- `backend/src/main.py`
- `backend/.env.example`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
