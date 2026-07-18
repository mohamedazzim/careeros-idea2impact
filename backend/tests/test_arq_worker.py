"""
Tests for ARQ worker infrastructure.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import asyncio

from src.workers.arq_worker import (
    WorkerSettings,
    get_arq_pool,
    close_arq_pool,
    enqueue_resume_processing,
    get_job_status,
    abort_job
)
from src.core.config import settings


class TestWorkerSettings:
    """Tests for ARQ worker configuration."""
    
    def test_worker_configuration(self):
        """Test worker settings are correctly configured."""
        assert WorkerSettings.redis_settings.host == settings.REDIS_HOST
        assert WorkerSettings.redis_settings.port == settings.REDIS_PORT
        assert WorkerSettings.redis_settings.database == settings.REDIS_DB
        assert WorkerSettings.allow_abort_jobs is True
        assert WorkerSettings.max_jobs == settings.WORKER_MAX_JOBS
        assert WorkerSettings.job_timeout == settings.WORKER_JOB_TIMEOUT
    
    @pytest.mark.asyncio
    async def test_on_startup(self):
        """Test worker startup handler."""
        ctx = {}
        
        with patch('src.workers.arq_worker.async_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            
            with patch('src.workers.arq_worker.redis_client') as mock_redis:
                mock_redis.ping = AsyncMock()
                
                await WorkerSettings.on_startup(ctx)
                
                assert 'start_time' in ctx
                mock_db.execute.assert_called_once()
                mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_shutdown(self):
        """Test worker shutdown handler."""
        ctx = {'start_time': asyncio.get_event_loop().time()}
        
        with patch('src.workers.arq_worker.redis_client') as mock_redis:
            mock_redis.close = AsyncMock()
            
            await WorkerSettings.on_shutdown(ctx)
            
            mock_redis.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_job_start(self):
        """Test job start handler."""
        ctx = {
            'job_id': 'test-job-123',
            'function': 'process_resume_task',
            'job_try': 1
        }
        
        await WorkerSettings.on_job_start(ctx)
        # Should log without error
    
    @pytest.mark.asyncio
    async def test_on_job_end_success(self):
        """Test job end handler for successful job."""
        ctx = {
            'job_id': 'test-job-123',
            'function': 'process_resume_task',
            'result': {'status': 'success'},
            'job_try': 1
        }
        
        await WorkerSettings.on_job_end(ctx)
        # Should log without error
    
    @pytest.mark.asyncio
    async def test_on_job_end_failure(self):
        """Test job end handler for failed job."""
        ctx = {
            'job_id': 'test-job-123',
            'function': 'process_resume_task',
            'result': Exception("Test error"),
            'job_try': 1
        }
        
        await WorkerSettings.on_job_end(ctx)
        # Should log without error


class TestArqPool:
    """Tests for ARQ pool management."""
    
    @pytest.mark.asyncio
    async def test_get_arq_pool_creates_pool(self):
        """Test that get_arq_pool creates a new pool."""
        with patch('src.workers.arq_worker.create_pool') as mock_create:
            mock_pool = AsyncMock()
            mock_create.return_value = mock_pool
            
            # Reset the global pool
            import src.workers.arq_worker as arq_module
            arq_module._arq_pool = None
            
            pool = await get_arq_pool()
            
            assert pool == mock_pool
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_arq_pool_returns_existing(self):
        """Test that get_arq_pool returns existing pool."""
        mock_pool = AsyncMock()
        
        import src.workers.arq_worker as arq_module
        arq_module._arq_pool = mock_pool
        
        pool = await get_arq_pool()
        
        assert pool == mock_pool


class TestEnqueueResumeProcessing:
    """Tests for enqueueing resume processing."""
    
    @pytest.mark.asyncio
    async def test_enqueue_success(self):
        """Test successful job enqueue."""
        mock_pool = AsyncMock()
        mock_job = MagicMock()
        mock_job.job_id = "job-123"
        mock_pool.enqueue_job = AsyncMock(return_value=mock_job)
        
        with patch('src.workers.arq_worker.get_arq_pool', return_value=mock_pool):
            job_id = await enqueue_resume_processing(1)
            
            assert job_id == "job-123"
            mock_pool.enqueue_job.assert_called_once_with(
                'process_resume_task',
                1,
                _queue_name='arq:queue',
                _expires=3600,
                _timeout=settings.WORKER_JOB_TIMEOUT
            )
    
    @pytest.mark.asyncio
    async def test_enqueue_failure(self):
        """Test failed job enqueue."""
        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock(return_value=None)
        
        with patch('src.workers.arq_worker.get_arq_pool', return_value=mock_pool):
            with pytest.raises(RuntimeError, match="Failed to enqueue"):
                await enqueue_resume_processing(1)


class TestGetJobStatus:
    """Tests for getting job status."""
    
    @pytest.mark.asyncio
    async def test_get_status_not_found(self):
        """Test status for non-existent job."""
        mock_pool = AsyncMock()
        mock_pool.job = MagicMock(return_value=None)
        
        with patch('src.workers.arq_worker.get_arq_pool', return_value=mock_pool):
            status = await get_job_status("nonexistent")
            
            assert status['exists'] is False
            assert status['status'] == 'not_found'
    
    @pytest.mark.asyncio
    async def test_get_status_complete(self):
        """Test status for completed job."""
        from arq.jobs import JobStatus
        
        mock_job = AsyncMock()
        mock_job.status = AsyncMock(return_value=JobStatus.complete)
        mock_job.info = AsyncMock(return_value=MagicMock(
            result={'status': 'success'},
            enqueue_time=MagicMock(isoformat=lambda: '2024-01-01T00:00:00'),
            start_time=MagicMock(isoformat=lambda: '2024-01-01T00:00:01'),
            finish_time=MagicMock(isoformat=lambda: '2024-01-01T00:00:02'),
            tries=1
        ))
        
        mock_pool = AsyncMock()
        mock_pool.job = MagicMock(return_value=mock_job)
        
        with patch('src.workers.arq_worker.get_arq_pool', return_value=mock_pool):
            status = await get_job_status("job-123")
            
            assert status['exists'] is True
            assert status['status'] == 'complete'
            assert status['result'] == {'status': 'success'}


class TestAbortJob:
    """Tests for aborting jobs."""
    
    @pytest.mark.asyncio
    async def test_abort_not_found(self):
        """Test aborting non-existent job."""
        mock_pool = AsyncMock()
        mock_pool.job = MagicMock(return_value=None)
        
        with patch('src.workers.arq_worker.get_arq_pool', return_value=mock_pool):
            result = await abort_job("nonexistent")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_abort_success(self):
        """Test successful abort."""
        mock_job = AsyncMock()
        mock_job.abort = AsyncMock()
        
        mock_pool = AsyncMock()
        mock_pool.job = MagicMock(return_value=mock_job)
        
        with patch('src.workers.arq_worker.get_arq_pool', return_value=mock_pool):
            result = await abort_job("job-123")
            assert result is True
            mock_job.abort.assert_called_once()
