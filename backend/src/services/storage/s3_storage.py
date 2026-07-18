"""
S3 Storage Adapter for production file storage.
Supports AWS S3 and MinIO-compatible endpoints.
"""
from __future__ import annotations
from typing import Optional
import aioboto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config as BotoConfig

from src.core.config import settings
from src.observability.langsmith import traceable
from .base import StorageAdapter
import logging

logger = logging.getLogger(__name__)


class S3StorageAdapter(StorageAdapter):
    """
    Production-grade S3 storage adapter with retry logic and observability.
    """
    
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None
    ):
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME
        self.region = region or settings.AWS_REGION
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.access_key = access_key or settings.AWS_ACCESS_KEY_ID
        self.secret_key = secret_key or settings.AWS_SECRET_ACCESS_KEY
        
        if not self.bucket_name:
            raise ValueError("S3 bucket name must be provided")
        
        # Configure boto3 with retries
        self.boto_config = BotoConfig(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            connect_timeout=10,
            read_timeout=30,
            max_pool_connections=25
        )
        
        self._session: Optional[aioboto3.Session] = None
        
    @property
    def session(self) -> aioboto3.Session:
        """Lazy initialization of boto3 session."""
        if self._session is None:
            self._session = aioboto3.Session()
        return self._session
    
    def _get_client_kwargs(self) -> dict:
        """Build kwargs for S3 client creation."""
        kwargs = {
            'service_name': 's3',
            'region_name': self.region,
            'config': self.boto_config
        }
        
        if self.endpoint_url:
            kwargs['endpoint_url'] = self.endpoint_url
            
        if self.access_key and self.secret_key:
            kwargs['aws_access_key_id'] = self.access_key
            kwargs['aws_secret_access_key'] = self.secret_key
            
        return kwargs
    
    @traceable(name="s3_save_file")
    async def save_file(self, filename: str, file_obj: bytes) -> str:
        """
        Save a file to S3 and return its URI.
        
        Args:
            filename: The key/name of the file
            file_obj: The file content in bytes
            
        Returns:
            S3 URI (s3://bucket-name/key)
            
        Raises:
            StorageError: If upload fails after retries
        """
        try:
            async with self.session.client(**self._get_client_kwargs()) as client:
                await client.put_object(
                    Bucket=self.bucket_name,
                    Key=filename,
                    Body=file_obj,
                    ContentType=self._get_content_type(filename),
                    ServerSideEncryption='AES256'  # Enable server-side encryption
                )
                
            s3_uri = f"s3://{self.bucket_name}/{filename}"
            logger.info(f"File saved to S3: {s3_uri}", extra={
                "storage_operation": "save",
                "bucket": self.bucket_name,
                "key": filename,
                "size_bytes": len(file_obj)
            })
            return s3_uri
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"S3 upload failed: {error_code}", extra={
                "storage_operation": "save",
                "error_code": error_code,
                "key": filename,
                "error": str(e)
            })
            raise StorageError(f"Failed to upload file to S3: {error_code}") from e
        except BotoCoreError as e:
            logger.error(f"S3 connection error: {e}", extra={
                "storage_operation": "save",
                "key": filename,
                "error": str(e)
            })
            raise StorageError(f"S3 connection failed: {e}") from e
    
    @traceable(name="s3_read_file")
    async def read_file(self, file_path: str) -> bytes:
        """
        Read a file from S3.
        
        Args:
            file_path: S3 URI (s3://bucket/key) or just the key
            
        Returns:
            File content as bytes
            
        Raises:
            StorageError: If file not found or download fails
        """
        # Parse S3 URI if provided
        if file_path.startswith("s3://"):
            key = file_path.split("/", 3)[-1]
        else:
            key = file_path
            
        try:
            async with self.session.client(**self._get_client_kwargs()) as client:
                response = await client.get_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
                async with response['Body'] as stream:
                    data = await stream.read()
                    
            logger.info("File read from S3", extra={
                "storage_operation": "read",
                "bucket": self.bucket_name,
                "key": key,
                "size_bytes": len(data)
            })
            return data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"S3 file not found: {key}", extra={
                    "storage_operation": "read",
                    "error_code": error_code,
                    "key": key
                })
                raise StorageError(f"File not found in S3: {key}") from e
            
            logger.error(f"S3 download failed: {error_code}", extra={
                "storage_operation": "read",
                "error_code": error_code,
                "key": key,
                "error": str(e)
            })
            raise StorageError(f"Failed to download file from S3: {error_code}") from e
    
    @traceable(name="s3_delete_file")
    async def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from S3.
        
        Args:
            file_path: S3 URI or key
            
        Returns:
            True if deleted, False if not found
        """
        if file_path.startswith("s3://"):
            key = file_path.split("/", 3)[-1]
        else:
            key = file_path
            
        try:
            async with self.session.client(**self._get_client_kwargs()) as client:
                await client.delete_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
                
            logger.info("File deleted from S3", extra={
                "storage_operation": "delete",
                "bucket": self.bucket_name,
                "key": key
            })
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                return False
            raise StorageError(f"Failed to delete file from S3: {error_code}") from e
    
    @traceable(name="s3_file_exists")
    async def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in S3.
        
        Args:
            file_path: S3 URI or key
            
        Returns:
            True if exists, False otherwise
        """
        if file_path.startswith("s3://"):
            key = file_path.split("/", 3)[-1]
        else:
            key = file_path
            
        try:
            async with self.session.client(**self._get_client_kwargs()) as client:
                await client.head_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    @traceable(name="s3_generate_presigned_url")
    async def generate_presigned_url(
        self, 
        file_path: str, 
        expiration: int = 3600,
        operation: str = 'get_object'
    ) -> str:
        """
        Generate a presigned URL for temporary access.
        
        Args:
            file_path: S3 URI or key
            expiration: URL expiration in seconds (max 7 days)
            operation: S3 operation ('get_object' or 'put_object')
            
        Returns:
            Presigned URL string
        """
        if file_path.startswith("s3://"):
            key = file_path.split("/", 3)[-1]
        else:
            key = file_path
            
        try:
            async with self.session.client(**self._get_client_kwargs()) as client:
                url = await client.generate_presigned_url(
                    ClientMethod=operation,
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': key
                    },
                    ExpiresIn=expiration
                )
            return url
        except ClientError as e:
            raise StorageError(f"Failed to generate presigned URL: {e}") from e
    
    def _get_content_type(self, filename: str) -> str:
        """Determine content type from filename extension."""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        content_types = {
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'txt': 'text/plain',
            'rtf': 'application/rtf',
            'html': 'text/html',
            'htm': 'text/html',
            'json': 'application/json',
            'xml': 'application/xml'
        }
        return content_types.get(ext, 'application/octet-stream')


class StorageError(Exception):
    """Raised when storage operations fail."""
    pass


# Factory function for creating storage adapter based on configuration
def create_storage_adapter() -> StorageAdapter:
    """
    Factory function to create the appropriate storage adapter
    based on configuration.
    """
    if settings.STORAGE_TYPE.lower() == 's3':
        if not settings.S3_BUCKET_NAME:
            raise ValueError("S3_BUCKET_NAME must be set when STORAGE_TYPE=s3")
        return S3StorageAdapter()
    else:
        from .local_storage import LocalStorageAdapter
        return LocalStorageAdapter(base_dir=settings.STORAGE_BASE_PATH)
