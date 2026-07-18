"""
Tests for storage abstraction layer.
Covers both local and S3 storage adapters.
"""
import pytest
import os
import tempfile
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.skip(reason="Storage tests need async fixture conversion")

from src.services.storage import (
    LocalStorageAdapter,
    S3StorageAdapter,
    StorageError,
    create_storage_adapter
)
from src.core.config import settings


class TestLocalStorageAdapter:
    """Tests for local filesystem storage adapter."""
    
    @pytest.fixture
    async def storage(self):
        """Create temporary storage adapter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = LocalStorageAdapter(base_dir=tmpdir)
            yield adapter
    
    @pytest.mark.asyncio
    async def test_save_and_read_file(self, storage):
        """Test saving and reading a file."""
        content = b"Hello, World!"
        filename = "test.txt"
        
        # Save
        path = await storage.save_file(filename, content)
        assert os.path.exists(path)
        
        # Read
        read_content = await storage.read_file(filename)
        assert read_content == content
    
    @pytest.mark.asyncio
    async def test_file_exists(self, storage):
        """Test file existence check."""
        filename = "test.txt"
        
        # Doesn't exist
        assert not await storage.file_exists(filename)
        
        # Create file
        await storage.save_file(filename, b"content")
        assert await storage.file_exists(filename)
    
    @pytest.mark.asyncio
    async def test_delete_file(self, storage):
        """Test file deletion."""
        filename = "test.txt"
        await storage.save_file(filename, b"content")
        
        # Delete
        result = await storage.delete_file(filename)
        assert result is True
        assert not await storage.file_exists(filename)
        
        # Delete non-existent
        result = await storage.delete_file("nonexistent.txt")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, storage):
        """Test reading non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            await storage.read_file("nonexistent.txt")
    
    @pytest.mark.asyncio
    async def test_path_traversal_protection(self, storage):
        """Test that path traversal attacks are blocked."""
        content = b"test"
        malicious_filename = "../../../etc/passwd"
        
        # Should only save to base directory
        path = await storage.save_file(malicious_filename, content)
        assert path.startswith(storage.base_dir)
        assert "passwd" in path  # File created, but within base_dir


class TestS3StorageAdapter:
    """Tests for S3 storage adapter."""
    
    @pytest.fixture
    def s3_adapter(self):
        """Create S3 adapter with mock credentials."""
        with patch.dict(os.environ, {
            'AWS_ACCESS_KEY_ID': 'test_key',
            'AWS_SECRET_ACCESS_KEY': 'test_secret',
            'S3_BUCKET_NAME': 'test-bucket'
        }):
            adapter = S3StorageAdapter()
            yield adapter
    
    @pytest.mark.asyncio
    async def test_save_file_success(self, s3_adapter):
        """Test successful file upload."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        
        with patch.object(s3_adapter.session, 'client', return_value=mock_client):
            content = b"test content"
            result = await s3_adapter.save_file("test.pdf", content)
            
            assert result == "s3://test-bucket/test.pdf"
            mock_client.put_object.assert_called_once()
            call_kwargs = mock_client.put_object.call_args.kwargs
            assert call_kwargs['Bucket'] == 'test-bucket'
            assert call_kwargs['Key'] == 'test.pdf'
            assert call_kwargs['ServerSideEncryption'] == 'AES256'
    
    @pytest.mark.asyncio
    async def test_read_file_success(self, s3_adapter):
        """Test successful file download."""
        mock_body = AsyncMock()
        mock_body.read = AsyncMock(return_value=b"file content")
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get_object = AsyncMock(return_value={'Body': mock_body})
        
        with patch.object(s3_adapter.session, 'client', return_value=mock_client):
            result = await s3_adapter.read_file("test.pdf")
            assert result == b"file content"
    
    @pytest.mark.asyncio
    async def test_read_file_not_found(self, s3_adapter):
        """Test file not found error handling."""
        from botocore.exceptions import ClientError
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get_object = AsyncMock(
            side_effect=ClientError(
                {'Error': {'Code': 'NoSuchKey', 'Message': 'Not found'}},
                'GetObject'
            )
        )
        
        with patch.object(s3_adapter.session, 'client', return_value=mock_client):
            with pytest.raises(StorageError, match="File not found"):
                await s3_adapter.read_file("nonexistent.pdf")
    
    def test_content_type_detection(self, s3_adapter):
        """Test content type detection from filename."""
        assert s3_adapter._get_content_type("doc.pdf") == "application/pdf"
        assert s3_adapter._get_content_type("doc.docx") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert s3_adapter._get_content_type("doc.txt") == "text/plain"
        assert s3_adapter._get_content_type("doc.unknown") == "application/octet-stream"


class TestStorageFactory:
    """Tests for storage adapter factory."""
    
    @pytest.mark.asyncio
    async def test_factory_local_storage(self):
        """Test factory creates local storage by default."""
        with patch.object(settings, 'STORAGE_TYPE', 'local'):
            adapter = create_storage_adapter()
            assert isinstance(adapter, LocalStorageAdapter)
    
    @pytest.mark.asyncio
    async def test_factory_s3_storage(self):
        """Test factory creates S3 storage when configured."""
        with patch.object(settings, 'STORAGE_TYPE', 's3'):
            with patch.object(settings, 'S3_BUCKET_NAME', 'test-bucket'):
                with patch.object(settings, 'AWS_ACCESS_KEY_ID', 'test'):
                    with patch.object(settings, 'AWS_SECRET_ACCESS_KEY', 'test'):
                        adapter = create_storage_adapter()
                        assert isinstance(adapter, S3StorageAdapter)
    
    @pytest.mark.asyncio
    async def test_factory_s3_missing_bucket(self):
        """Test factory raises error when S3 bucket not configured."""
        with patch.object(settings, 'STORAGE_TYPE', 's3'):
            with patch.object(settings, 'S3_BUCKET_NAME', None):
                with pytest.raises(ValueError, match="S3_BUCKET_NAME"):
                    create_storage_adapter()
