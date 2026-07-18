"""
Tests for health check endpoints.
"""
import inspect
import pytest
import httpx
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from src.main import app


# Starlette TestClient passes `app=` to httpx.Client on older Starlette.
# httpx>=0.28 removed this kwarg, so patch locally for test compatibility.
if "app" not in inspect.signature(httpx.Client.__init__).parameters:
    _httpx_client_init = httpx.Client.__init__

    def _patched_httpx_client_init(self, *args, app=None, **kwargs):
        return _httpx_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = _patched_httpx_client_init


client = TestClient(app)


class TestHealthLive:
    """Tests for liveness probe."""
    
    def test_live_endpoint(self):
        """Test liveness endpoint returns 200."""
        response = client.get("/api/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert 'timestamp' in data
        assert 'service' in data
    
    def test_live_no_dependencies(self):
        """Test liveness doesn't check dependencies."""
        # Should work even if DB is down
        response = client.get("/api/health/live")
        assert response.status_code == 200


class TestHealthReady:
    """Tests for readiness probe."""
    
    @pytest.mark.asyncio
    async def test_ready_all_healthy(self):
        """Test readiness when all dependencies are healthy."""
        with patch('src.api.health.check_database', new_callable=AsyncMock) as mock_db:
            mock_db.return_value = {'status': 'healthy', 'latency_ms': 5.0}
            
            with patch('src.api.health.check_redis', new_callable=AsyncMock) as mock_redis:
                mock_redis.return_value = {'status': 'healthy', 'latency_ms': 2.0}
                
                with patch('src.api.health.check_qdrant', new_callable=AsyncMock) as mock_qdrant:
                    mock_qdrant.return_value = {'status': 'healthy', 'latency_ms': 3.0}
                    
                    response = client.get("/api/health/ready")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data['status'] == 'ok'
                    assert data['dependencies']['database']['status'] == 'healthy'
                    assert data['dependencies']['redis']['status'] == 'healthy'
                    assert data['dependencies']['qdrant']['status'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_ready_unhealthy(self):
        """Test readiness when dependencies are unhealthy."""
        with patch('src.api.health.check_database', new_callable=AsyncMock) as mock_db:
            mock_db.return_value = {'status': 'unhealthy', 'error': 'Connection failed'}
            
            with patch('src.api.health.check_redis', new_callable=AsyncMock) as mock_redis:
                mock_redis.return_value = {'status': 'healthy', 'latency_ms': 2.0}
                
                with patch('src.api.health.check_qdrant', new_callable=AsyncMock) as mock_qdrant:
                    mock_qdrant.return_value = {'status': 'healthy', 'latency_ms': 3.0}
                    
                    response = client.get("/api/health/ready")
                    
                    assert response.status_code == 503
                    data = response.json()
                    assert 'degraded' in str(data)


class TestHealthDeep:
    """Tests for deep health check."""
    
    @pytest.mark.asyncio
    async def test_deep_all_healthy(self):
        """Test deep health when all services are healthy."""
        with patch('src.api.health.check_database', new_callable=AsyncMock) as mock_db:
            mock_db.return_value = {'status': 'healthy', 'latency_ms': 5.0, 'tables': 10}
            
            with patch('src.api.health.check_redis', new_callable=AsyncMock) as mock_redis:
                mock_redis.return_value = {'status': 'healthy', 'latency_ms': 2.0, 'test_value': True}
                
                with patch('src.api.health.check_qdrant', new_callable=AsyncMock) as mock_qdrant:
                    mock_qdrant.return_value = {'status': 'healthy', 'latency_ms': 3.0, 'collections': 3}
                    
                    with patch('src.api.health.check_storage', new_callable=AsyncMock) as mock_storage:
                        mock_storage.return_value = {
                            'status': 'healthy', 
                            'latency_ms': 1.0, 
                            'storage_type': 'local',
                            'read_write_ok': True
                        }
                        
                        response = client.get("/api/health/deep")
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data['status'] == 'healthy'
                        assert data['summary']['healthy'] == 4
                        assert data['summary']['total'] == 4
                        assert 'services' in data
                        assert 'configuration' in data


class TestDatabaseCheck:
    """Tests for database health check."""
    
    @pytest.mark.asyncio
    async def test_database_healthy(self):
        """Test healthy database check."""
        from src.api.health import check_database
        
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        
        with patch('src.api.health.async_session') as mock_session:
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            
            result = await check_database()
            
            assert result['status'] == 'healthy'
            assert 'latency_ms' in result
            assert result['tables'] == 10
    
    @pytest.mark.asyncio
    async def test_database_unhealthy(self):
        """Test unhealthy database check."""
        from src.api.health import check_database
        
        with patch('src.api.health.async_session') as mock_session:
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock(side_effect=Exception("Connection refused"))
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            
            result = await check_database()
            
            assert result['status'] == 'unhealthy'
            assert 'error' in result


class TestRedisCheck:
    """Tests for Redis health check."""
    
    @pytest.mark.asyncio
    async def test_redis_healthy(self):
        """Test healthy Redis check."""
        from src.api.health import check_redis
        
        with patch('src.api.health.redis_client') as mock_redis:
            mock_redis.ping = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_redis.get = AsyncMock(return_value="healthy")
            mock_redis.delete = AsyncMock()
            
            result = await check_redis()
            
            assert result['status'] == 'healthy'
            assert 'latency_ms' in result
            assert result['test_value'] is True
    
    @pytest.mark.asyncio
    async def test_redis_unhealthy(self):
        """Test unhealthy Redis check."""
        from src.api.health import check_redis
        
        with patch('src.api.health.redis_client') as mock_redis:
            mock_redis.ping = AsyncMock(side_effect=Exception("Connection refused"))
            
            result = await check_redis()
            
            assert result['status'] == 'unhealthy'
            assert 'error' in result
