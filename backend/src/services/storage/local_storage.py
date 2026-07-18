"""
Local filesystem storage adapter for development.
"""
import os
import aiofiles
from src.core.config import settings
from src.observability.langsmith import traceable
from .base import StorageAdapter
import logging

logger = logging.getLogger(__name__)


class LocalStorageAdapter(StorageAdapter):
    """
    Local filesystem storage adapter.
    Uses configured base path from settings.
    """
    
    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or settings.STORAGE_BASE_PATH
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info(f"Local storage initialized at: {self.base_dir}")

    @traceable(name="local_save_file")
    async def save_file(self, filename: str, file_obj: bytes) -> str:
        """Save file to local filesystem."""
        # Sanitize filename to prevent directory traversal
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(self.base_dir, safe_filename)
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_obj)
            
        logger.info("File saved locally", extra={
            "storage_operation": "save",
            "path": file_path,
            "size_bytes": len(file_obj)
        })
        return file_path

    @traceable(name="local_read_file")
    async def read_file(self, file_path: str) -> bytes:
        """Read file from local filesystem."""
        # Ensure path is within base_dir
        full_path = os.path.join(self.base_dir, os.path.basename(file_path))
        
        if not os.path.exists(full_path):
            logger.error(f"File not found: {full_path}")
            raise FileNotFoundError(f"File not found: {full_path}")
            
        async with aiofiles.open(full_path, 'rb') as f:
            data = await f.read()
            
        logger.info("File read locally", extra={
            "storage_operation": "read",
            "path": full_path,
            "size_bytes": len(data)
        })
        return data

    @traceable(name="local_delete_file")
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from local filesystem."""
        full_path = os.path.join(self.base_dir, os.path.basename(file_path))
        
        if not os.path.exists(full_path):
            return False
            
        os.remove(full_path)
        logger.info("File deleted locally", extra={
            "storage_operation": "delete",
            "path": full_path
        })
        return True

    @traceable(name="local_file_exists")
    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists."""
        full_path = os.path.join(self.base_dir, os.path.basename(file_path))
        return os.path.exists(full_path)


