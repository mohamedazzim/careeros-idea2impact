"""
LangSmith integration for CareerOS AI.
Production-grade observability with tracing, feedback, and run management.
"""
from .client import (
    LangSmithManager,
    langsmith_client,
    get_run_url,
    get_manager,
    setup_langsmith
)
from .breaker import (
    get_langsmith_circuit_breaker,
    install_langsmith_log_filter,
)
from .decorators import (
    traceable,
    get_current_run_id
)
from .feedback import submit_feedback
from .datasets import create_dataset, log_to_dataset

__all__ = [
    # Client
    "LangSmithManager",
    "langsmith_client",
    "get_run_url",
    "get_manager",
    "setup_langsmith",
    "get_langsmith_circuit_breaker",
    "install_langsmith_log_filter",
    # Tracing
    "traceable",
    "get_current_run_id",
    # Feedback
    "submit_feedback",
    # Datasets
    "create_dataset",
    "log_to_dataset"
]
