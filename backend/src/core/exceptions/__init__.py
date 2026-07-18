"""Domain exception hierarchy for CareerOS.

Structured exceptions with error codes, status codes, and
correlation IDs for every layer of the application.
"""
from typing import Any, Dict, Optional


# ── Base Exception ──────────────────────────────────────────────────

class CareerOSError(Exception):
    """Base exception for all CareerOS errors."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    domain: str = "core"

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if status_code:
            self.status_code = status_code
        if error_code:
            self.error_code = error_code
        self.correlation_id = correlation_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.error_code,
            "message": self.message,
            "domain": self.domain,
            "status_code": self.status_code,
            "details": self.details,
            "correlation_id": self.correlation_id,
        }


# ── Authentication Exceptions ───────────────────────────────────────

class AuthenticationError(CareerOSError):
    domain = "auth"
    status_code = 401
    error_code = "AUTHENTICATION_FAILED"


class InvalidCredentialsError(AuthenticationError):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"


class TokenExpiredError(AuthenticationError):
    status_code = 401
    error_code = "TOKEN_EXPIRED"


class TokenInvalidError(AuthenticationError):
    status_code = 401
    error_code = "TOKEN_INVALID"


class AuthorizationError(CareerOSError):
    domain = "auth"
    status_code = 403
    error_code = "AUTHORIZATION_FAILED"


class InsufficientRoleError(AuthorizationError):
    status_code = 403
    error_code = "INSUFFICIENT_ROLE"


# ── Resource Exceptions ─────────────────────────────────────────────

class NotFoundError(CareerOSError):
    domain = "resource"
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(CareerOSError):
    domain = "resource"
    status_code = 409
    error_code = "CONFLICT"


class AlreadyExistsError(ConflictError):
    error_code = "ALREADY_EXISTS"


# ── Validation Exceptions ───────────────────────────────────────────

class ValidationError(CareerOSError):
    domain = "validation"
    status_code = 422
    error_code = "VALIDATION_ERROR"


class InvalidRequestError(ValidationError):
    error_code = "INVALID_REQUEST"


class MissingFieldError(ValidationError):
    error_code = "MISSING_FIELD"


class FileValidationError(ValidationError):
    error_code = "FILE_VALIDATION_ERROR"


# ── Processing Exceptions ───────────────────────────────────────────

class ProcessingError(CareerOSError):
    domain = "processing"
    status_code = 500
    error_code = "PROCESSING_ERROR"


class DocumentParseError(ProcessingError):
    error_code = "DOCUMENT_PARSE_ERROR"


class InsufficientContentError(ProcessingError):
    status_code = 422
    error_code = "INSUFFICIENT_CONTENT"


class PIIMaskingError(ProcessingError):
    error_code = "PII_MASKING_ERROR"


class EmbeddingError(ProcessingError):
    domain = "embedding"
    error_code = "EMBEDDING_ERROR"


class IndexingError(ProcessingError):
    domain = "indexing"
    error_code = "INDEXING_ERROR"


# ── Retrieval Exceptions ────────────────────────────────────────────

class RetrievalError(CareerOSError):
    domain = "retrieval"
    status_code = 502
    error_code = "RETRIEVAL_ERROR"


class VectorStoreError(RetrievalError):
    error_code = "VECTOR_STORE_ERROR"


class RerankerError(RetrievalError):
    error_code = "RERANKER_ERROR"


class RerankerCircuitOpenError(RerankerError):
    status_code = 503
    error_code = "RERANKER_CIRCUIT_OPEN"


class NoResultsError(RetrievalError):
    status_code = 404
    error_code = "NO_RESULTS"


# ── LLM / Intelligence Exceptions ───────────────────────────────────

class LLMError(CareerOSError):
    domain = "llm"
    status_code = 502
    error_code = "LLM_ERROR"


class ClaudeError(LLMError):
    error_code = "CLAUDE_ERROR"


class ClaudeCircuitOpenError(ClaudeError):
    status_code = 503
    error_code = "CLAUDE_CIRCUIT_OPEN"


class ClaudeRateLimitError(ClaudeError):
    status_code = 429
    error_code = "CLAUDE_RATE_LIMITED"


class DeepSeekError(LLMError):
    error_code = "DEEPSEEK_ERROR"


class HallucinationDetectedError(LLMError):
    status_code = 422
    error_code = "HALLUCINATION_DETECTED"


class GroundingError(LLMError):
    status_code = 422
    error_code = "GROUNDING_FAILED"


class EvaluationError(LLMError):
    domain = "evaluation"
    error_code = "EVALUATION_ERROR"


# ── Orchestration / Agent Exceptions ────────────────────────────────

class OrchestrationError(CareerOSError):
    domain = "orchestration"
    status_code = 500
    error_code = "ORCHESTRATION_ERROR"


class GraphExecutionError(OrchestrationError):
    error_code = "GRAPH_EXECUTION_ERROR"


class AgentExecutionError(OrchestrationError):
    error_code = "AGENT_EXECUTION_ERROR"


class AgentTimeoutError(AgentExecutionError):
    status_code = 504
    error_code = "AGENT_TIMEOUT"


class GovernanceBlockedError(OrchestrationError):
    status_code = 403
    error_code = "GOVERNANCE_BLOCKED"


# ── MCP Exceptions ──────────────────────────────────────────────────

class MCPError(CareerOSError):
    domain = "mcp"
    status_code = 502
    error_code = "MCP_ERROR"


class MCPTimeoutError(MCPError):
    status_code = 504
    error_code = "MCP_TIMEOUT"


class MCPConnectionError(MCPError):
    status_code = 502
    error_code = "MCP_CONNECTION_ERROR"


class MCPToolError(MCPError):
    status_code = 502
    error_code = "MCP_TOOL_ERROR"


class TwilioError(MCPError):
    error_code = "TWILIO_ERROR"


class ElevenLabsError(MCPError):
    error_code = "ELEVENLABS_ERROR"


# ── Interview Exceptions ────────────────────────────────────────────

class InterviewError(CareerOSError):
    domain = "interview"
    status_code = 500
    error_code = "INTERVIEW_ERROR"


class SessionNotFoundError(InterviewError):
    status_code = 404
    error_code = "INTERVIEW_SESSION_NOT_FOUND"


class SessionExpiredError(InterviewError):
    status_code = 410
    error_code = "INTERVIEW_SESSION_EXPIRED"


# ── Infrastructure Exceptions ───────────────────────────────────────

class InfrastructureError(CareerOSError):
    domain = "infrastructure"
    status_code = 503
    error_code = "INFRASTRUCTURE_ERROR"


class DatabaseError(InfrastructureError):
    error_code = "DATABASE_ERROR"


class RedisError(InfrastructureError):
    error_code = "REDIS_ERROR"


class QdrantError(InfrastructureError):
    error_code = "QDRANT_ERROR"


class ConfigurationError(InfrastructureError):
    error_code = "CONFIGURATION_ERROR"


class ServiceUnavailableError(InfrastructureError):
    error_code = "SERVICE_UNAVAILABLE"
