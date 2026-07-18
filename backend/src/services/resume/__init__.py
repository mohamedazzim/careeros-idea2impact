"""
Resume services module.
Business logic services for resume operations.
"""
from .validation_service import (
    ResumeValidationService,
    validation_service,
    ValidationError,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE
)
from .storage_service import (
    ResumeStorageService,
    storage_service,
    StorageServiceError
)
from .upload_service import (
    ResumeUploadService,
    upload_service,
    UploadServiceError
)
from .retrieval_service import (
    ResumeRetrievalService,
    retrieval_service,
    ResumeNotFoundError,
    RetrievalServiceError
)
from .processing_service import (
    ResumeProcessingService,
    processing_service,
    ProcessingError,
    RetryableProcessingError,
    PermanentProcessingError,
    InsufficientContentError,
    FileNotFoundError
)
from .versioning_service import (
    ResumeVersioningService,
    versioning_service,
    VersioningServiceError
)
from .retry_service import (
    ResumeRetryService,
    retry_service,
    RetryServiceError,
    ResumeNotRetryableError
)
from .status_service import (
    ResumeStatusService,
    status_service,
    StatusServiceError
)
from .deletion_service import (
    ResumeDeletionService,
    deletion_service,
    DeletionServiceError
)

__all__ = [
    # Validation
    "ResumeValidationService",
    "validation_service",
    "ValidationError",
    "ALLOWED_EXTENSIONS",
    "MAX_FILE_SIZE",
    # Storage
    "ResumeStorageService",
    "storage_service",
    "StorageServiceError",
    # Upload
    "ResumeUploadService",
    "upload_service",
    "UploadServiceError",
    # Retrieval
    "ResumeRetrievalService",
    "retrieval_service",
    "ResumeNotFoundError",
    "RetrievalServiceError",
    # Processing
    "ResumeProcessingService",
    "processing_service",
    "ProcessingError",
    "RetryableProcessingError",
    "PermanentProcessingError",
    "InsufficientContentError",
    "FileNotFoundError",
    # Versioning
    "ResumeVersioningService",
    "versioning_service",
    "VersioningServiceError",
    # Retry
    "ResumeRetryService",
    "retry_service",
    "RetryServiceError",
    "ResumeNotRetryableError",
    # Status
    "ResumeStatusService",
    "status_service",
    "StatusServiceError",
    # Deletion
    "ResumeDeletionService",
    "deletion_service",
    "DeletionServiceError"
]
