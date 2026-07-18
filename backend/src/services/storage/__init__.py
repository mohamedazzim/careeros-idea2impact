"""
Storage abstraction layer for CareerOS AI.
Supports local filesystem and S3-compatible storage.
"""
from .base import StorageAdapter
from .local_storage import LocalStorageAdapter
from .s3_storage import S3StorageAdapter, StorageError, create_storage_adapter

storage_client = create_storage_adapter()

__all__ = [
    "StorageAdapter",
    "LocalStorageAdapter",
    "S3StorageAdapter",
    "StorageError",
    "create_storage_adapter",
    "storage_client",
]