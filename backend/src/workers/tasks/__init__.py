"""
Background task implementations.
Modular task organization for the ARQ worker.
"""
from .ingestion import process_resume_task
from .retries import (
    TaskRetryableError,
    TaskPermanentError,
    retry_failed_task
)
from .lifecycle import (
    update_resume_status,
    publish_status_update
)
from .status import get_job_status
from .cleanup import (
    cleanup_status_keys,
    abort_job
)

__all__ = [
    # Main task
    "process_resume_task",
    # Error types
    "TaskRetryableError",
    "TaskPermanentError",
    # Retry operations
    "retry_failed_task",
    # Status management
    "update_resume_status",
    "publish_status_update",
    "get_job_status",
    # Cleanup
    "cleanup_status_keys",
    "abort_job",
]
