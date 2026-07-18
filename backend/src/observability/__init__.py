"""
Observability infrastructure for CareerOS AI.
Tracing, metrics, logging, and LangSmith integration.
"""
from .context import request_id_ctx, user_id_ctx, workflow_id_ctx
from .logger import structured_logger
from .metrics import (
    API_REQUEST_COUNT, API_LATENCY,
    RETRIEVAL_LATENCY_HIST, QDRANT_LATENCY_HIST, RERANK_LATENCY_HIST,
    LLM_TOKEN_USAGE, LLM_LATENCY_HIST, LLM_FAILURES,
    AGENT_NODE_LATENCY_HIST, AGENT_RETRIES, AGENT_CHECKPOINTS,
    MCP_INVOCATION_COUNT, MCP_LATENCY_HIST, MCP_FAILURES,
    # Phase 3B resilience
    EMBED_CIRCUIT_BREAKER_STATE,
    EMBED_RATE_LIMIT_HITS,
    EMBED_QUEUE_DEPTH,
    EMBED_QUEUE_REJECTIONS,
    # Phase 3B retrieval observability
    RETRIEVAL_MISS_TOTAL,
    RETRIEVAL_EMPTY_RESULTS,
    RETRIEVAL_RERANK_FAILURES,
    EMBED_CACHE_HIT_RATIO,
    # Phase 3B payload monitoring
    EMBED_PAYLOAD_BYTES,
    EMBED_PAYLOAD_BLOAT,
    EMBED_PAYLOAD_TRUNCATIONS,
    # Phase 3B indexing robustness
    INDEXING_PARTIAL_BATCH,
    INDEXING_RETRY_IDEMPOTENT,
    INDEXING_DEAD_LETTER,
    # Phase 3B hardening: cache
    RETRIEVAL_CACHE_HIT,
    RETRIEVAL_CACHE_MISS,
    RETRIEVAL_CACHE_WRITE,
    # Phase 3B hardening: BM25 persistence
    BM25_PERSIST_SAVES,
    BM25_PERSIST_LOADS,
    BM25_PERSIST_BYTES,
    BM25_PERSIST_LATENCY,
    BM25_INDEX_SIZE,
    BM25_INDEX_MEMORY_BYTES,
    # Phase 3B hardening: drift
    RETRIEVAL_DRIFT_SCORE,
    DRIFT_ALERT_TRIGGERED,
    GOLDEN_QUERY_REGRESSION,
    # Phase 3B hardening: reranker
    RERANK_CIRCUIT_OPEN,
    RERANK_FALLBACK_USED,
    RERANK_TIMEOUT,
    RERANK_RATE_LIMIT,
    # Phase 3B hardening: context integrity
    CONTEXT_OVERFLOW,
    CONTEXT_CITATION_ORPHAN,
    CONTEXT_CHRONOLOGY_VIOLATION,
    CONTEXT_OVERLAP_CORRUPTION,
    # Phase 3B hardening: federated
    FEDERATION_DEDUP_REMOVED,
    FEDERATION_COLLECTION_COUNT,
    FEDERATION_LATENCY,
    FEDERATION_SCORE_NORMALIZE,
    # Phase 5: Agentic MCP Orchestration
    AGENT_EXECUTION_COUNT,
    AGENT_EXECUTION_LATENCY,
    AGENT_CONFIDENCE_GAUGE,
    AUTONOMOUS_ACTION_COUNT,
    NOTIFICATION_SUPPRESSION_COUNT,
    RECURSION_PREVENTION_COUNT,
    ORCHESTRATION_FAILURES,
    GRAPH_RESUME_COUNT,
    VOICE_CALL_LATENCY,
    OPPORTUNITY_PROCESSING_LATENCY,
    ORCHESTRATION_SESSION_GAUGE,
    GOVERNANCE_DECISION_COUNT,
    EVENT_BUS_QUEUE_DEPTH_GAUGE,
    MCP_EXECUTION_TOTAL,
    MCP_EXECUTION_LATENCY,
    MCP_EXECUTION_FAILURES,
    MCP_RETRY_AMPLIFICATION,
)
from .tracing import tracer
from .middleware import ObservabilityMiddleware, observability_middleware

# LangSmith exports
from .langsmith import (
    langsmith_client,
    traceable,
    get_run_url,
    submit_feedback,
    create_dataset,
    log_to_dataset
)

__all__ = [
    # Context
    "request_id_ctx", "user_id_ctx", "workflow_id_ctx",
    # Logging
    "structured_logger",
    # Metrics
    "API_REQUEST_COUNT", "API_LATENCY",
    "RETRIEVAL_LATENCY_HIST", "QDRANT_LATENCY_HIST", "RERANK_LATENCY_HIST",
    "LLM_TOKEN_USAGE", "LLM_LATENCY_HIST", "LLM_FAILURES",
    "AGENT_NODE_LATENCY_HIST", "AGENT_RETRIES", "AGENT_CHECKPOINTS",
    "MCP_INVOCATION_COUNT", "MCP_LATENCY_HIST", "MCP_FAILURES",
    # Tracing
    "tracer",
    "ObservabilityMiddleware",
    # LangSmith
    "langsmith_client",
    "traceable",
    "get_run_url",
    "submit_feedback",
    "create_dataset",
    "log_to_dataset"
    # Phase 5: Agentic MCP Orchestration
    "AGENT_EXECUTION_COUNT", "AGENT_EXECUTION_LATENCY", "AGENT_CONFIDENCE_GAUGE",
    "AUTONOMOUS_ACTION_COUNT", "NOTIFICATION_SUPPRESSION_COUNT",
    "RECURSION_PREVENTION_COUNT", "ORCHESTRATION_FAILURES", "GRAPH_RESUME_COUNT",
    "VOICE_CALL_LATENCY", "OPPORTUNITY_PROCESSING_LATENCY",
    "ORCHESTRATION_SESSION_GAUGE", "GOVERNANCE_DECISION_COUNT",
    "EVENT_BUS_QUEUE_DEPTH_GAUGE", "MCP_EXECUTION_TOTAL", "MCP_EXECUTION_LATENCY",
    "MCP_EXECUTION_FAILURES", "MCP_RETRY_AMPLIFICATION",
]
