from typing import List, Union, Optional
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "CareerOS AI Enterprise"
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    ENVIRONMENT: str = "development"

    @property
    def DEBUG(self) -> bool:
        return self.ENVIRONMENT == "development"

    # Auth
    SECRET_KEY: str = "dev-secret-change-in-production-via-env"
    ALGORITHM: str = "HS256"

    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "data"
    POSTGRES_DB: str = "careeros_db"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:data@localhost:5432/careeros_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    # AWS S3 Storage
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None
    STORAGE_TYPE: str = "local"
    STORAGE_BASE_PATH: str = "/tmp/careeros_storage"

    # AI
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    DEEPSEEK_MODEL: str = "meta/llama-3.3-70b-instruct"
    PRIMARY_LLM_PROVIDER: str = "gemini"
    PRIMARY_LLM_MODEL: str = "gemini-2.5-flash"

    # Gemini
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_PRIMARY_MODEL: str = "gemini-2.5-flash"
    GEMINI_REASONING_MODEL: str = "gemini-2.5-flash"
    GEMINI_TIMEOUT: int = 60
    GEMINI_MAX_RETRIES: int = 3

    # Fallback
    FALLBACK_LLM_PROVIDER: str = "deepseek"

    # TheirStack Jobs API — 15 key slots with legacy URL aliases
    THEIRSTACK_API_KEY: Optional[str] = None
    THEIRSTACK_API_KEY_1: Optional[str] = None
    THEIRSTACK_API_KEY_2: Optional[str] = None
    THEIRSTACK_API_KEY_3: Optional[str] = None
    THEIRSTACK_API_KEY_4: Optional[str] = None
    THEIRSTACK_API_KEY_5: Optional[str] = None
    THEIRSTACK_API_KEY_6: Optional[str] = None
    THEIRSTACK_API_KEY_7: Optional[str] = None
    THEIRSTACK_API_KEY_8: Optional[str] = None
    THEIRSTACK_API_KEY_9: Optional[str] = None
    THEIRSTACK_API_KEY_10: Optional[str] = None
    THEIRSTACK_API_KEY_11: Optional[str] = None
    THEIRSTACK_API_KEY_12: Optional[str] = None
    THEIRSTACK_API_KEY_13: Optional[str] = None
    THEIRSTACK_API_KEY_14: Optional[str] = None
    THEIRSTACK_API_KEY_15: Optional[str] = None
    THEIRSTACK_API_URL_1: Optional[str] = None
    THEIRSTACK_API_URL_2: Optional[str] = None
    THEIRSTACK_API_URL_3: Optional[str] = None
    THEIRSTACK_API_URL_4: Optional[str] = None
    THEIRSTACK_API_URL_5: Optional[str] = None
    THEIRSTACK_API_URL_6: Optional[str] = None
    THEIRSTACK_API_URL_7: Optional[str] = None
    THEIRSTACK_API_URL_8: Optional[str] = None
    THEIRSTACK_API_URL_9: Optional[str] = None
    THEIRSTACK_API_URL_10: Optional[str] = None
    THEIRSTACK_API_URL_11: Optional[str] = None
    THEIRSTACK_API_URL_12: Optional[str] = None
    THEIRSTACK_API_URL_13: Optional[str] = None
    THEIRSTACK_API_URL_14: Optional[str] = None
    THEIRSTACK_API_URL_15: Optional[str] = None
    THEIRSTACK_BASE_URL: str = "https://api.theirstack.com"
    THEIRSTACK_TIMEOUT_SECONDS: int = 30
    THEIRSTACK_MAX_RETRIES: int = 3
    THEIRSTACK_RETRY_BACKOFF_BASE: float = 1.5
    THEIRSTACK_RESULTS_PER_QUERY: int = 25
    THEIRSTACK_POSTED_MAX_AGE_DAYS: int = 14
    THEIRSTACK_MAX_QUERIES_PER_REFRESH: int = 5
    THEIRSTACK_MAX_KEY_SLOTS: int = 15
    THEIRSTACK_JOB_FETCH_LIMIT: int = 10
    THEIRSTACK_JOB_FETCH_DAYS: int = 7
    THEIRSTACK_ENABLE_FREE_COUNT_PREVIEW: bool = True
    THEIRSTACK_COMPANY_TYPE: str = "direct_employer"
    THEIRSTACK_COUNTRY_CODES: List[str] = Field(default_factory=lambda: ["IN"])
    THEIRSTACK_EMPLOYMENT_STATUSES: List[str] = Field(default_factory=lambda: ["full_time"])

    # MCP / Voice Credentials
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    TWILIO_TEST_PHONE_NUMBER: Optional[str] = None
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_CONVAI_AGENT_ID: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ELEVENLABS_CONVAI_AGENT_ID", "ELEVENLABS_AGENT_ID"),
    )
    ELEVENLABS_CONVAI_PHONE_NUMBER_ID: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "ELEVENLABS_CONVAI_PHONE_NUMBER_ID",
            "ELEVENLABS_AGENT_PHONE_NUMBER_ID",
            "ELEVENLABS_PHONE_NUMBER_ID",
        ),
    )
    ELEVENLABS_CONVAI_RINGING_TIMEOUT_SECS: int = 60
    DEEPGRAM_API_KEY: Optional[str] = None
    PIPEDREAM_WEBHOOK_URL: Optional[str] = None
    MAKE_RAG_WEBHOOK_URL: Optional[str] = None
    MAKE_RAG_API_KEY: Optional[str] = None
    QDRANT_RAG_DOCS_COLLECTION: str = "careeros_rag_docs"
    RAG_EMBEDDING_MODEL: str = "nvidia/nv-embed-v1"
    RAG_LLM_MODEL: str = "gemini-2.5-flash"
    RAG_USE_MAKE: bool = True

    # LLM Intelligence Orchestration
    CLAUDE_MODEL: str = "gemini-2.5-flash"
    CLAUDE_MAX_TOKENS: int = 4096
    CLAUDE_TEMPERATURE: float = 0.0
    CLAUDE_TIMEOUT: int = 60
    CLAUDE_MAX_RETRIES: int = 2
    CLAUDE_RETRY_BASE_DELAY: float = 2.0
    CLAUDE_CIRCUIT_BREAKER_ENABLED: bool = True
    CLAUDE_CIRCUIT_THRESHOLD: int = 3
    CLAUDE_CIRCUIT_RECOVERY: int = 90
    CLAUDE_COST_BUDGET_PER_CALL: float = 0.10
    CLAUDE_STREAMING_ENABLED: bool = False
    CLAUDE_RATE_LIMIT_RPM: int = 50

    # Prompt Governance
    PROMPT_VERSIONING_ENABLED: bool = True
    PROMPT_REGRESSION_CHECK_ENABLED: bool = False
    PROMPT_REGISTRY_BACKEND: str = "disk"

    # LangSmith Observability
    LANGSMITH_ENABLED: bool = False
    LANGSMITH_FAIL_OPEN: bool = True
    LANGSMITH_429_COOLDOWN_SECONDS: int = 3600
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "careeros"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"

    # Worker Configuration
    WORKER_MAX_JOBS: int = 10
    WORKER_JOB_TIMEOUT: int = 300
    WORKER_RETRY_DELAY: int = 60
    WORKER_MAX_RETRIES: int = 3

    # Task Retry Configuration
    TASK_MAX_RETRIES: int = 3
    TASK_RETRY_DELAY_SECONDS: int = 60

    # Retrieval Caching
    RETRIEVAL_CACHE_ENABLED: bool = True
    RETRIEVAL_CACHE_TTL: int = 900
    RETRIEVAL_CACHE_TTL_RERANK: int = 1800
    RETRIEVAL_CACHE_TTL_CONTEXT: int = 300
    RETRIEVAL_CACHE_TTL_ROUTING: int = 3600
    RETRIEVAL_CACHE_TTL_QUERY_UNDERSTANDING: int = 86400
    RETRIEVAL_CACHE_KEY_PREFIX: str = "retrieval:"

    # Checkpoint Persistence
    CHECKPOINT_DB_PATH: str = "./data/langgraph_checkpoints.db"

    # BM25 Index Persistence
    BM25_PERSIST_ENABLED: bool = True
    BM25_PERSIST_PATH: str = "data/bm25"
    BM25_STALENESS_TTL: int = 3600
    BM25_MAX_COLLECTIONS: int = 5
    BM25_STORAGE_TYPE: str = "redis"
    BM25_REDIS_NS: str = "bm25:"

    # Alert Decision Thresholds
    CALL_ALERT_MIN_MATCH_SCORE: int = 65
    CALL_ALERT_DRY_RUN: bool = False
    CALL_ALERT_COOLDOWN_HOURS: int = 24

    # Outbound Safety
    OUTBOUND_CALL_DRY_RUN: bool = False
    OUTBOUND_TEST_TO_NUMBER: Optional[str] = None

    # Auto Job Refresh
    JOB_AUTO_REFRESH_ENABLED: bool = True
    JOB_AUTO_REFRESH_INTERVAL_MINUTES: int = 30
    JOB_AUTO_REFRESH_EMBED_BATCH_SIZE: int = 50

    # Reranker Resilience
    RERANKER_TIMEOUT: int = 30
    RERANKER_MAX_RETRIES: int = 2
    RERANKER_RETRY_BASE_DELAY: float = 1.0
    RERANKER_CIRCUIT_BREAKER_ENABLED: bool = True
    RERANKER_CIRCUIT_THRESHOLD: int = 3
    RERANKER_MAX_BATCH_SIZE: int = 50
    RERANKER_FALLBACK_STRATEGY: str = "score_sort"

    # Federated Retrieval
    FEDERATION_MAX_CONCURRENT: int = 3
    FEDERATION_TIMEOUT: int = 10
    FEDERATION_DEDUP_ENABLED: bool = True
    FEDERATION_SCORE_NORMALIZE: bool = True
    FEDERATION_RESULT_LIMIT: int = 50

    # Retrieval Drift Monitoring
    DRIFT_THRESHOLD_RECALL: float = 0.15
    DRIFT_THRESHOLD_MRR: float = 0.20
    DRIFT_THRESHOLD_CONSISTENCY: float = 0.25
    DRIFT_CHECK_WINDOW: int = 100
    GOLDEN_QUERIES_PATH: str = "data/golden_queries.json"
    DRIFT_ALERT_ENABLED: bool = True
    DRIFT_CHECK_ENABLED: bool = True

    # Context Integrity
    CONTEXT_MAX_TOKENS: int = 4000
    CONTEXT_HARD_OVERFLOW_CUTOFF: bool = True
    CONTEXT_MIN_CHUNKS_PER_SOURCE: int = 1
    CONTEXT_CHRONOLOGY_PRESERVE: bool = True
    CONTEXT_CITATION_PRESERVE: bool = True

    # Phase 4C: Career Strategy Intelligence
    STRATEGY_ENABLED: bool = True
    STRATEGY_MAX_CONCURRENT: int = 3
    STRATEGY_STAGE_TIMEOUT: int = 60
    STRATEGY_ROADMAP_MAX_ITEMS: int = 15
    STRATEGY_CONFIDENCE_THRESHOLD: float = 0.3
    STRATEGY_HALLUCINATION_CHECK_ENABLED: bool = True
    STRATEGY_EXPLAINABILITY_ENABLED: bool = True
    STRATEGY_CONFIDENCE_BASE: float = 0.5
    STRATEGY_CONFIDENCE_COMPLETENESS_WEIGHT: float = 0.75
    STRATEGY_TOKEN_PRESSURE_THRESHOLD: int = 100000
    STRATEGY_MARKET_ANALYSIS_ENABLED: bool = True

    # Phase 4D: Interview Intelligence Runtime
    INTERVIEW_REDIS_KEY_PREFIX: str = "interview:"
    INTERVIEW_SESSION_TTL: int = 3600
    INTERVIEW_SESSION_MAX: int = 50
    INTERVIEW_QUESTIONS_MAX: int = 20
    INTERVIEW_ESCALATION_CAP: int = 2
    INTERVIEW_CONCURRENT_EVALUATIONS: int = 3
    INTERVIEW_TOKEN_BUDGET: int = 250000
    INTERVIEW_TIMEOUT_EVALUATION: int = 30
    INTERVIEW_TIMEOUT_QUESTION: int = 20
    INTERVIEW_TIMEOUT_FEEDBACK: int = 30
    INTERVIEW_RETRY_MAX: int = 2
    INTERVIEW_RETRY_BASE_DELAY: float = 1.5
    INTERVIEW_ORPHAN_TTL: int = 900
    INTERVIEW_STREAMING_BUFFER_SIZE: int = 64
    INTERVIEW_SANDBOX_ENABLED: bool = False

    # Phase 5: Agentic MCP Orchestration
    ORCHESTRATION_ENABLED: bool = True
    ORCHESTRATION_MAX_RETRIES: int = 3
    ORCHESTRATION_TIMEOUT_SECONDS: int = 300
    ORCHESTRATION_RECURSION_DEPTH_MAX: int = 5
    ORCHESTRATION_MAX_AUTONOMOUS_ACTIONS: int = 10
    ORCHESTRATION_MIN_CONFIDENCE_FOR_ACTION: float = 0.75
    ORCHESTRATION_SESSION_TTL: int = 7200
    ORCHESTRATION_REDIS_KEY_PREFIX: str = "orch:"
    ORCHESTRATION_DEAD_LETTER_TTL: int = 86400
    ORCHESTRATION_EVENT_RETENTION: int = 1000
    ORCHESTRATION_MAX_CONCURRENT_AGENTS: int = 5

    # MCP Runtime
    MCP_TOOL_TIMEOUT: int = 30
    MCP_MAX_RETRIES: int = 3
    MCP_RETRY_BACKOFF_BASE: float = 1.5
    MOCK_MCP: bool = False

    # Voice Pipeline
    VOICE_CALL_TIMEOUT: int = 60
    VOICE_CALL_MAX_RETRIES: int = 2
    VOICE_ELEVENLABS_VOICE_ID: str = "default"
    VOICE_ELEVENLABS_MODEL: str = "eleven_multilingual_v2"
    VOICE_NOTIFICATION_MIN_URGENCY: float = 0.60

    # Opportunity Scoring
    OPPORTUNITY_MATCH_WEIGHTS: dict = {
        "ats_fit": 0.25,
        "skill_overlap": 0.20,
        "missing_skills": 0.15,
        "seniority_fit": 0.10,
        "compensation_relevance": 0.05,
        "role_alignment": 0.10,
        "domain_alignment": 0.05,
        "application_urgency": 0.05,
        "posted_within_32_hours": 0.03,
        "market_demand": 0.02,
    }
    OPPORTUNITY_MIN_SCORE_FOR_ACTION: float = 65.0
    OPPORTUNITY_VOICE_CALL_MIN_SCORE: float = 80.0
    OPPORTUNITY_GOVERNANCE_BLOCK_SCORE: float = 94.0
    OPPORTUNITY_POSTED_WITHIN_HOURS: int = 32
    OPPORTUNITY_HISTORY_TTL: int = 86400 * 7

    # Agent Governance
    AGENT_AUTONOMOUS_CAP_PER_SESSION: int = 5
    AGENT_RECURSION_DEPTH_MAX: int = 3
    AGENT_DUPLICATE_NOTIFICATION_TTL: int = 3600
    AGENT_CONFIDENCE_FLOOR: float = 0.15

    # India Market Job Pipeline
    JOB_TARGET_COUNTRY: str = "IN"
    JOB_TARGET_MARKET: str = "India"
    JOB_ALLOW_GLOBAL_REMOTE: bool = False
    JOB_MAX_AGE_DAYS: int = 30
    JOB_REQUIRE_SOURCE_URL: bool = True
    JOB_PROVIDER_FETCH_LIMIT: int = 200

    # Verified Learning Paths
    LEARNING_RESOURCES_ENABLED: bool = True
    LEARNING_RESOURCE_DISCOVERY_ENABLED: bool = True
    LEARNING_RESOURCE_PROVIDER: str = "seeded+dynamic"
    LEARNING_RESOURCE_CACHE_TTL_HOURS: int = 168
    LEARNING_RESOURCE_MIN_RESULTS_PER_SKILL: int = 3
    LEARNING_RESOURCE_MAX_RESULTS_PER_SKILL: int = 8
    LEARNING_WEB_SEARCH_PROVIDER: str = "tavily"
    LEARNING_WEB_SEARCH_ENABLED: bool = True
    LEARNING_WEB_SEARCH_TIMEOUT_SECONDS: int = 20
    BRAVE_SEARCH_API_KEY: Optional[str] = None
    SERPAPI_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    GOOGLE_CSE_API_KEY: Optional[str] = None
    GOOGLE_CSE_CX: Optional[str] = None
    UDEMY_CLIENT_ID: Optional[str] = None
    UDEMY_CLIENT_SECRET: Optional[str] = None
    UDEMY_AFFILIATE_ENABLED: bool = False
    COURSERA_DISCOVERY_ENABLED: bool = True
    LEARNING_WEB_SEARCH_ALLOWED_DOMAINS: List[str] = Field(
        default_factory=lambda: [
            "aws.amazon.com",
            "docs.aws.amazon.com",
            "developer.mozilla.org",
            "docs.docker.com",
            "fastapi.tiangolo.com",
            "git-scm.com",
            "kubernetes.io",
            "www.postgresql.org",
            "python.langchain.com",
            "docs.langchain.com",
            "react.dev",
            "www.tensorflow.org",
            "docs.pytorch.org",
            "www.youtube.com",
            "coursera.org",
            "www.coursera.org",
            "udemy.com",
            "www.udemy.com",
        ]
    )
    YOUTUBE_API_KEY: Optional[str] = None

    # GitHub Project Discovery for Skill Gaps
    GITHUB_REPO_DISCOVERY_ENABLED: bool = True
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_REPO_CACHE_TTL_HOURS: int = 168
    GITHUB_REPO_MIN_RESULTS_PER_SKILL: int = 3
    GITHUB_REPO_MAX_RESULTS_PER_SKILL: int = 6
    GITHUB_ISSUE_DISCOVERY_ENABLED: bool = True

    @field_validator('BACKEND_CORS_ORIGINS', mode='before')
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith('['):
            return [i.strip() for i in v.split(',')]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @field_validator(
        'THEIRSTACK_COUNTRY_CODES',
        'THEIRSTACK_EMPLOYMENT_STATUSES',
        'LEARNING_WEB_SEARCH_ALLOWED_DOMAINS',
        mode='before',
    )
    @classmethod
    def assemble_list_like_settings(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith('['):
            return [i.strip() for i in v.split(',') if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()

try:
    from src.observability.langsmith.bootstrap import install_langsmith_guard

    install_langsmith_guard()
except Exception:
    # Keep settings import resilient even if observability bootstrap fails.
    pass
