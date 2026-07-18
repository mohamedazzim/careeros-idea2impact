"""
Background worker infrastructure for CareerOS AI.
ARQ-based task queue with Redis.
"""
from .arq_worker import (
    WorkerSettings,
    get_arq_pool,
    close_arq_pool,
    enqueue_resume_processing,
    enqueue_evaluation_benchmark,
    get_job_status,
    abort_job
)
from .tasks import (
    process_resume_task,
    TaskRetryableError,
    TaskPermanentError,
    retry_failed_task,
    update_resume_status,
    publish_status_update,
    cleanup_status_keys
)

__all__ = [
    # Worker configuration
    "WorkerSettings",
    # Connection management
    "get_arq_pool",
    "close_arq_pool",
    # Job management
    "enqueue_resume_processing",
    "enqueue_evaluation_benchmark",
    "get_job_status",
    "abort_job",
    # Tasks
    "process_resume_task",
    "TaskRetryableError",
    "TaskPermanentError",
    "retry_failed_task",
    "update_resume_status",
    "publish_status_update",
    "cleanup_status_keys"
]
