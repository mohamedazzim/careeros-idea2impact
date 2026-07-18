"""
LangSmith client management.
Singleton client initialization and configuration.
"""
import logging
from typing import Optional

from langsmith import Client

from src.core.config import settings

from .breaker import get_langsmith_circuit_breaker

logger = logging.getLogger(__name__)


class LangSmithManager:
    """
    Manages LangSmith client and tracing configuration.
    Singleton pattern for global access.
    """
    
    _instance: Optional['LangSmithManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._client: Optional[Client] = None
        self._enabled = False
        self._initialize()
        self._initialized = True
    
    def _initialize(self):
        """Initialize LangSmith client based on configuration."""
        breaker = get_langsmith_circuit_breaker()
        if not breaker.enabled_by_config():
            logger.info("LangSmith tracing disabled (LANGSMITH_ENABLED=false)")
            return
        
        if breaker.cooldown_active():
            logger.warning(
                "LangSmith disabled temporarily: reason=%s cooldown_seconds=%s",
                breaker.status_snapshot().get("reason"),
                breaker.cooldown_remaining_seconds(),
            )
            return
        
        if not settings.LANGCHAIN_API_KEY:
            logger.warning("LangSmith API key not set (LANGCHAIN_API_KEY)")
            return
        
        try:
            self._client = Client(
                api_key=settings.LANGCHAIN_API_KEY,
                api_url=settings.LANGCHAIN_ENDPOINT
            )
            self._enabled = True
            logger.info(f"LangSmith initialized for project: {settings.LANGCHAIN_PROJECT}")
        except Exception as e:
            logger.error(f"Failed to initialize LangSmith: {e}")
            self._enabled = False
    
    @property
    def client(self) -> Optional[Client]:
        """Get LangSmith client."""
        return self._client
    
    @property
    def enabled(self) -> bool:
        """Check if LangSmith is enabled and configured."""
        breaker = get_langsmith_circuit_breaker()
        if not breaker.should_allow_requests():
            return False
        return self._enabled and self._client is not None
    
    def get_run_url(self, run_id: str) -> Optional[str]:
        """Generate a URL to view a run in LangSmith UI."""
        if not self.enabled:
            return None
        
        base_url = settings.LANGCHAIN_ENDPOINT.replace('/api/v1', '')
        return f"{base_url}/projects/{settings.LANGCHAIN_PROJECT}/runs/{run_id}"


# Global LangSmith manager instance
_langsmith_manager = LangSmithManager()


# Public exports
langsmith_client = _langsmith_manager.client


def get_run_url(run_id: str) -> Optional[str]:
    """Get URL to view run in LangSmith UI."""
    return _langsmith_manager.get_run_url(run_id)


def get_manager() -> LangSmithManager:
    """Get the global LangSmith manager instance."""
    return _langsmith_manager


# Backwards compatibility alias
def setup_langsmith() -> Optional[Client]:
    """Backwards compatibility function."""
    return _langsmith_manager.client
