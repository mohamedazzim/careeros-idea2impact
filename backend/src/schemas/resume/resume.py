"""
Resume API schemas.
Pydantic models for request/response validation.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ResumeUploadResponse(BaseModel):
    """Response for resume upload endpoint."""
    id: int = Field(..., description="Resume ID")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status")
    task_id: Optional[str] = Field(None, description="Background task ID")
    created_at: datetime = Field(..., description="Upload timestamp")

    model_config = ConfigDict(from_attributes=True)


class TaskStatusResponse(BaseModel):
    """Response for task status endpoint."""
    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Current status")
    result: Optional[Dict[str, Any]] = Field(None, description="Result data if complete")
    error: Optional[str] = Field(None, description="Error message if failed")
    message: Optional[str] = Field(None, description="Additional message")
    created_at: Optional[str] = Field(None, description="Task creation time")
    started_at: Optional[str] = Field(None, description="Processing start time")
    completed_at: Optional[str] = Field(None, description="Completion time")
    attempts: int = Field(0, description="Number of processing attempts")

    model_config = ConfigDict(from_attributes=True)


class ResumeDetailResponse(BaseModel):
    """Detailed resume information."""
    id: int = Field(..., description="Resume ID")
    user_id: str = Field(..., description="Owner user ID")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status")
    error_message: Optional[str] = Field(None, description="Error if failed")
    task_id: Optional[str] = Field(None, description="Background task ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class ResumeListItem(BaseModel):
    """Single resume item in list response."""
    id: int = Field(..., description="Resume ID")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class ResumeListResponse(BaseModel):
    """Paginated list of resumes."""
    items: List[ResumeListItem] = Field(..., description="Resume items")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Skipped records")
    limit: int = Field(..., description="Page size")

    model_config = ConfigDict(from_attributes=True)


class ResumeVersionResponse(BaseModel):
    """Resume version information."""
    id: int = Field(..., description="Version ID")
    resume_id: int = Field(..., description="Parent resume ID")
    version_num: int = Field(..., description="Version number")
    raw_content_preview: Optional[str] = Field(None, description="Preview of raw content")
    masked_content_preview: Optional[str] = Field(None, description="Preview of masked content")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate(cls, obj):
        """Custom validation to truncate long content fields."""
        data = {
            "id": obj.id,
            "resume_id": obj.resume_id,
            "version_num": obj.version_num,
            "raw_content_preview": obj.raw_content[:200] + "..." if obj.raw_content and len(obj.raw_content) > 200 else obj.raw_content,
            "masked_content_preview": obj.masked_content[:200] + "..." if obj.masked_content and len(obj.masked_content) > 200 else obj.masked_content,
            "created_at": obj.created_at
        }
        return cls(**data)


class ResumeRetryRequest(BaseModel):
    """Request body for retry endpoint."""
    force: bool = Field(False, description="Force retry even if not failed")

    model_config = ConfigDict(from_attributes=True)


class ResumeRetryResponse(BaseModel):
    """Response for resume retry endpoint."""
    resume_id: int = Field(..., description="Resume ID")
    job_id: str = Field(..., description="Queued background job ID")
    message: str = Field(..., description="Retry submission status")

    model_config = ConfigDict(from_attributes=True)


class ResumeChunkResponse(BaseModel):
    """Resume chunk information."""
    id: int = Field(..., description="Chunk ID")
    version_id: int = Field(..., description="Parent version ID")
    chunk_index: int = Field(..., description="Chunk sequence number")
    content_preview: str = Field(..., description="Preview of chunk content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Chunk metadata")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)
