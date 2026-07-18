"""
Task status endpoint.
Query background job processing status.
"""
import logging

from fastapi import APIRouter, HTTPException, status

from src.schemas.resume.resume import TaskStatusResponse
from src.workers.arq_worker import get_job_status
from src.observability.langsmith import traceable

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/task/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get task status",
    description="Get the status of a background processing task."
)
@traceable(name="get_task_status")
async def get_task_status_endpoint(
    task_id: str
) -> TaskStatusResponse:
    """
    Check the status of a background resume processing task.
    
    Returns current status, result (if complete), and error (if failed).
    """
    try:
        status_info = await get_job_status(task_id)
    except Exception as e:
        logger.error(f"Failed to get job status: {e}", extra={"task_id": task_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task status"
        )
    
    if not status_info.get("exists"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return TaskStatusResponse(
        task_id=task_id,
        status=status_info.get("status", "unknown"),
        result=status_info.get("result"),
        error=status_info.get("error"),
        created_at=status_info.get("enqueue_time"),
        started_at=status_info.get("start_time"),
        completed_at=status_info.get("finish_time"),
        attempts=status_info.get("attempts", 0)
    )
