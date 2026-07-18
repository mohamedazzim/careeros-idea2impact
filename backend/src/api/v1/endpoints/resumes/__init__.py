"""
Resume API endpoints.
Modular endpoint organization for maintainability.
"""
from fastapi import APIRouter

from .upload import router as upload_router
from .retrieval import router as retrieval_router
from .status import router as status_router
from .retry import router as retry_router
from .lifecycle import router as lifecycle_router

# Aggregate all routers
router = APIRouter()

# Include all sub-routers with their prefixes
router.include_router(upload_router)
router.include_router(retrieval_router)
router.include_router(status_router)
router.include_router(retry_router)
router.include_router(lifecycle_router)

# Re-export for backwards compatibility
from .shared import get_current_user
from .upload import upload_resume
from .retrieval import list_resumes, get_resume, get_resume_versions, download_resume
from .status import get_task_status_endpoint
from .retry import retry_resume
from .lifecycle import delete_resume

__all__ = [
    "router",
    "get_current_user",
    "upload_resume",
    "list_resumes",
    "get_resume",
    "get_resume_versions",
    "download_resume",
    "get_task_status_endpoint",
    "retry_resume",
    "delete_resume"
]
