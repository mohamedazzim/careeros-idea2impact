# Troubleshooting Guide

This guide describes how to verify the integration stack, check API provider authentication, and debug compile or test suite failures.

## 1. Stack Service Verification

Verify PostgreSQL, Redis, and Qdrant database services are active and reachable:

### PostgreSQL Connection
Run the following from the root directory or inside the backend environment to verify connection:
```powershell
# From backend directory
poetry run python -c "
import asyncio, asyncpg, os
from src.core.config import settings
async def check():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    print('Postgres connection SUCCESS:', await conn.fetchval('SELECT version();'))
    await conn.close()
asyncio.run(check())
"
```

### Redis Connection
Confirm Redis is running and responding to pings:
```powershell
poetry run python -c "
import redis
r = redis.Redis(host='127.0.0.1', port=6379, db=0)
print('Redis ping SUCCESS:', r.ping())
"
```

### Qdrant Vector DB Connection
Validate that Qdrant is responsive on port `6333`:
```powershell
poetry run python -c "
import httpx
res = httpx.get('http://127.0.0.1:6333/healthz')
print('Qdrant Health SUCCESS:', res.json())
"
```

### Alembic Schema Gate

Validate a fresh schema and model contract:

```bash
docker compose up -d db redis qdrant backend
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
docker compose exec backend alembic check
```

Expected current revision:

```text
033_schema_contract_alignment (head)
```

Expected Alembic check result:

```text
No new upgrade operations detected.
```

---

## 2. API Providers Validation

### Gemini API Access
Verify that the Gemini model is accessible and correctly authenticated:
```powershell
poetry run python -c "
import asyncio
from src.services.intelligence.gemini_service import GeminiV2Service
async def check():
    svc = GeminiV2Service()
    res = await svc.reason_text('Hello, testing API access.')
    print('Gemini API access SUCCESS:', res)
asyncio.run(check())
"
```

### NVIDIA Embeddings (Vector Dimension: 4096)
Validate that real NVIDIA embeddings are operating on the correct dimension size (`4096`):
```powershell
poetry run python -c "
import asyncio
from src.services.embedding.nvembed_service import NVEmbedV1Service
async def check():
    svc = NVEmbedV1Service()
    vec = await svc.embed_query('Test query')
    print('NVIDIA Embedding Dimension SUCCESS:', len(vec) == 4096, 'Dimension:', len(vec))
asyncio.run(check())
"
```

---

## 3. Frontend Compilation & Test Validation

### Install Dependencies
Run package installations cleanly using npm:
```bash
cd frontend
npm install --legacy-peer-deps
```

### Compile Static Assets
Run a production build of the Next.js frontend to verify code compilation and asset generation:
```bash
npm run build
```

### Run Vitest Suite
Run the frontend unit test suite:
```bash
npm test
```
This runs Vitest in a simulated `jsdom` environment.

---

## 4. Demo-Safe Runtime Checks

For public review, keep live external actions disabled unless explicitly testing a provider:

```bash
JOB_AUTO_REFRESH_ENABLED=false
CALL_ALERT_DRY_RUN=true
OUTBOUND_CALL_DRY_RUN=true
RAG_USE_MAKE=false
```

The synthetic golden path should validate:

- user registration and login,
- synthetic resume upload and analysis,
- fictional opportunity seeding,
- local Qdrant indexing and retrieval,
- docs-RAG answer with citations,
- skill-gap analysis,
- non-admin API blocking,
- no live phone call, webhook dispatch, or job application.

---

## 5. Live Idea2Impact Deployment Checks

Current public URLs:

- Frontend: `https://careeros-idea2impact-azzim.koreacentral.cloudapp.azure.com`
- Backend API: `https://careeros-idea2impact-azzim.koreacentral.cloudapp.azure.com/api`
- Liveness: `https://careeros-idea2impact-azzim.koreacentral.cloudapp.azure.com/api/health/live`
- Readiness: `https://careeros-idea2impact-azzim.koreacentral.cloudapp.azure.com/api/health/ready`
- Docs-RAG health: `https://careeros-idea2impact-azzim.koreacentral.cloudapp.azure.com/api/v1/demo-rag/health`

Expected production status:

- Liveness, readiness, and Docs-RAG health return `200`.
- Demo credentials authenticate a `User` role, not an administrator.
- Unauthenticated opportunity access returns `401`.
- Docs-RAG indexing reports 18 files, 127 chunks, and 0 failed chunks.
- Qdrant collection `careeros_rag_docs` contains 127 points after indexing.
- Twilio, Make.com, Pipedream, and automatic external application actions remain dry-run or blocked.
- Deepgram is unavailable/disabled in the public demo.

If Nginx returns `502` after backend or frontend containers are rebuilt, check whether it cached a stale Docker upstream IP. The production Nginx config uses Docker DNS resolver-based upstreams to prevent this; recreate only the Nginx container after updating that config:

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --no-deps --force-recreate nginx
```

Do not use this troubleshooting step against unrelated deployments.
