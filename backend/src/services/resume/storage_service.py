"""
Resume storage service.
Wraps storage operations with resume-specific business logic.
"""
import logging

from src.services.storage import storage_client, StorageError

logger = logging.getLogger(__name__)


class StorageServiceError(Exception):
    """Raised when storage operation fails."""
    pass


class ResumeStorageService:
    """
    Service for resume storage operations.
    Separates storage logic from API endpoints.
    """

    async def save_file(self, filename: str, content: bytes, user_id: str) -> str:
        """
        Save resume file to storage.

        Args:
            filename: Original filename
            content: File content bytes
            user_id: User ID for path organization

        Returns:
            Storage path

        Raises:
            StorageServiceError: If save fails
        """
        try:
            storage_path = await storage_client.save_file(filename, content)
            logger.info("File saved to storage", extra={
                "user_id": user_id,
                "filename": filename,
                "storage_path": storage_path
            })
            return storage_path
        except StorageError as e:
            logger.error(f"Storage error: {e}", extra={
                "user_id": user_id,
                "filename": filename
            })
            raise StorageServiceError(f"Failed to store file: {e}")

    async def delete_file(self, storage_path: str) -> bool:
        """
        Delete file from storage.

        Args:
            storage_path: Path to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            await storage_client.delete_file(storage_path)
            logger.info("File deleted from storage", extra={
                "storage_path": storage_path
            })
            return True
        except Exception as e:
            logger.warning(f"Failed to delete file: {e}", extra={
                "storage_path": storage_path
            })
            return False

    async def get_download_url(self, storage_path: str, expires: int = 3600) -> str:
        """
        Get presigned download URL.

        Args:
            storage_path: File path
            expires: URL expiration in seconds

        Returns:
            Presigned URL

        Raises:
            StorageServiceError: If URL generation fails
        """
        try:
            return await storage_client.get_download_url(storage_path, expires)
        except StorageError as e:
            raise StorageServiceError(f"Failed to generate URL: {e}")

    async def file_exists(self, storage_path: str) -> bool:
        """
        Check if file exists in storage.

        Args:
            storage_path: Path to check

        Returns:
            True if exists
        """
        try:
            return await storage_client.file_exists(storage_path)
        except Exception:
            return False

    async def get_file_content(self, storage_path: str) -> bytes:
        """
        Read file content from storage.

        Args:
            storage_path: Path to read

        Returns:
            File content as bytes

        Raises:
            StorageServiceError: If read fails
        """
        try:
            return await storage_client.read_file(storage_path)
        except StorageError as e:
            raise StorageServiceError(f"Failed to read file: {e}")


# Global service instance
storage_service = ResumeStorageService()
