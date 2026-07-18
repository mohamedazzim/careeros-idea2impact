# CareerOS AI - Backend

Production-grade Resume Infrastructure built with FastAPI, PostgreSQL, Redis, and Arq.

## Architecture

### Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI |
| Database | PostgreSQL 15 |
| Cache/Queue | Redis 7 |
| Vector DB | Qdrant |
| Task Queue | Arq |
| Storage | Local / S3 |
| Observability | LangSmith, Prometheus |

### Services

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│  PostgreSQL │
│  (Next.js)  │     │  (FastAPI)  │     │   (Resumes) │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
      ┌─────────┐    ┌─────────┐    ┌─────────┐
      │  Redis  │    │ Qdrant  │    │   S3    │
      │ (Queue) │    │(Vectors)│    │(Storage)│
      └────┬────┘    └─────────┘    └─────────┘
           │
           ▼
      ┌─────────┐
      │ Worker  │
      │  (Arq)  │
      └─────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+ (for local development)
- Node.js 20+ (for frontend)

### Environment Setup

```bash
cp .env.example .env
# Edit .env with your configuration
```

### Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f worker

# Run migrations
docker-compose exec backend alembic upgrade head
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start backend
uvicorn src.main:app --reload --port 8000

# Start worker (in another terminal)
python -m src.workers.arq_worker
```

## API Endpoints

### Health Checks

| Endpoint | Description |
|----------|-------------|
| `GET /api/health/live` | Liveness probe |
| `GET /api/health/ready` | Readiness probe (checks DB, Redis, Qdrant) |
| `GET /api/health/deep` | Deep health with all diagnostics |

### Resumes

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/resumes/upload` | Upload resume file |
| GET | `/api/v1/resumes/` | List user resumes |
| GET | `/api/v1/resumes/{id}` | Get resume details |
| GET | `/api/v1/resumes/{id}/versions` | Get version history |
| GET | `/api/v1/resumes/{id}/download` | Download original file |
| POST | `/api/v1/resumes/{id}/retry` | Retry failed processing |
| DELETE | `/api/v1/resumes/{id}` | Delete resume |
| GET | `/api/v1/resumes/task/{task_id}` | Check task status |

## Storage Configuration

### Local Storage (Development)

```env
STORAGE_TYPE=local
STORAGE_BASE_PATH=/tmp/careeros_storage
```

### S3 Storage (Production)

```env
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID=<aws-access-key-id>
AWS_SECRET_ACCESS_KEY=<aws-secret-access-key>
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket

# Optional: MinIO or other S3-compatible
S3_ENDPOINT_URL=http://localhost:9000
```

## Worker Configuration

Workers process resumes in the background:

```env
WORKER_MAX_JOBS=10          # Concurrent jobs
WORKER_JOB_TIMEOUT=300      # 5 minutes timeout
WORKER_RETRY_DELAY=60       # 1 minute between retries
WORKER_MAX_RETRIES=3        # Max retry attempts
```

### Monitoring Workers

```bash
# View worker logs
docker-compose logs -f worker

# Check queue status
redis-cli LLEN arq:queue
```

## Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View current version
alembic current
```

## Observability

### LangSmith Tracing

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<langsmith-api-key>
LANGCHAIN_PROJECT=careeros
```

### Prometheus Metrics

Metrics exposed at `/metrics`:

- `api_requests_total` - HTTP request count
- `api_latency_seconds` - Request latency
- `llm_token_usage` - LLM token consumption
- `llm_latency_seconds` - LLM latency

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_storage.py -v
```

## Production Deployment

### Checklist

- [ ] Change `SECRET_KEY` from default
- [ ] Configure S3 storage
- [ ] Set `ENVIRONMENT=production`
- [ ] Enable LangSmith tracing
- [ ] Configure backup for PostgreSQL
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure SSL/TLS
- [ ] Set resource limits in docker-compose

### Docker Compose Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Worker Not Processing

```bash
# Check worker is running
docker-compose ps worker

# Check Redis connection
docker-compose exec backend python -c "import asyncio; from src.db.redis import redis_client; asyncio.run(redis_client.ping())"

# Check for failed jobs in database
docker-compose exec db psql -U careeros -c "SELECT id, status, error_message FROM resumes WHERE status='failed';"
```

### Database Connection Issues

```bash
# Check database is healthy
docker-compose ps db

# View database logs
docker-compose logs db

# Run migrations manually
docker-compose exec backend alembic upgrade head
```

### Storage Issues

```bash
# Check storage type
docker-compose exec backend python -c "from src.core.config import settings; print(settings.STORAGE_TYPE)"

# Test storage connectivity
docker-compose exec backend python -c "
import asyncio
from src.services.storage import storage_client
async def test():
    await storage_client.save_file('test.txt', b'test')
    print('Storage OK')
asyncio.run(test())
"
```

## License

Proprietary - CareerOS AI Enterprise
