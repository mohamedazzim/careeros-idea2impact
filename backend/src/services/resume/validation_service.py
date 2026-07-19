"""
Resume validation service.
Handles all file validation, content checks, and format verification.
"""
import logging
from typing import Set
from fastapi import UploadFile

logger = logging.getLogger(__name__)

# File type validation constants
ALLOWED_EXTENSIONS: Set[str] = {'.pdf', '.docx', '.doc', '.txt', '.rtf'}
MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB


class ValidationError(Exception):
    """Raised when file validation fails."""
    pass


class ResumeValidationService:
    """
    Service for validating resume uploads.
    Separates validation logic from API endpoints.
    """

    def __init__(self):
        self.allowed_extensions = ALLOWED_EXTENSIONS
        self.max_file_size = MAX_FILE_SIZE

    async def validate_upload(self, file: UploadFile) -> bytes:
        """
        Complete validation of uploaded resume file.

        Args:
            file: Uploaded file from FastAPI

        Returns:
            File content as bytes

        Raises:
            ValidationError: If validation fails
        """
        # Validate filename exists
        self._validate_filename(file.filename)

        # Validate extension
        self._validate_extension(file.filename)

        # Read and validate content
        content = await self._read_and_validate_content(file)

        return content

    def _validate_filename(self, filename: str) -> None:
        """Validate filename is present."""
        if not filename:
            raise ValidationError("No filename provided")

    def _validate_extension(self, filename: str) -> None:
        """Validate file extension is allowed."""
        filename_lower = filename.lower()
        if not any(filename_lower.endswith(ext) for ext in self.allowed_extensions):
            raise ValidationError(
                f"Invalid file type. Allowed: {', '.join(self.allowed_extensions)}"
            )

    async def _read_and_validate_content(self, file: UploadFile) -> bytes:
        """Read file and validate size/format."""
        try:
            content = await file.read()
        except Exception as e:
            raise ValidationError(f"Failed to read file: {e}")

        # Check file size
        if len(content) > self.max_file_size:
            raise ValidationError(
                f"File too large. Maximum size: {self.max_file_size / 1024 / 1024}MB"
            )

        # Validate PDF magic number
        if file.filename.lower().endswith('.pdf') and not content.startswith(b'%PDF'):
            raise ValidationError("Invalid PDF file")

        return content

    def get_content_type(self, filename: str) -> str:
        """Determine content type from filename."""
        content_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.txt': 'text/plain',
            '.rtf': 'application/rtf'
        }

        filename_lower = filename.lower()
        for ext, content_type in content_types.items():
            if filename_lower.endswith(ext):
                return content_type

        return 'application/octet-stream'


# Global service instance
validation_service = ResumeValidationService()
