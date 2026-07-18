# CareerOS Environment Configuration

This guide documents the environment variables needed for local development, Docker, and optional external providers. Copy `.env.example` to `.env` and populate values locally. Never commit `.env`.

## Required for the core stack

| Variable | Requirement | Service | Purpose | Safe example |
|---|---|---|---|---|
| `ENV_FILE` | Optional Compose selector | Backend, worker | File injected into application containers | `.env.example` for public-safe validation |
| `SECRET_KEY` | Required outside throwaway local development | Backend | Signs JWT access and refresh tokens | `replace-with-a-long-random-value` |
| `BACKEND_CORS_ORIGINS` | Required for browser access | Backend | JSON list of allowed frontend origins | `["http://localhost:3000"]` |
| `POSTGRES_USER` | Required | PostgreSQL, backend | Database user | `careeros` |
| `POSTGRES_PASSWORD` | Required | PostgreSQL, backend | Database password | `change-me-local-only` |
| `POSTGRES_DB` | Required | PostgreSQL, backend | Database name | `careeros_db` |
| `DATABASE_URL` | Required when not supplied by Compose | Backend, migrations | Async SQLAlchemy connection URL | `postgresql+asyncpg://careeros:change-me-local-only@db:5432/careeros_db` |
| `REDIS_URL` | Required | Backend, worker | Cache, ARQ queue, locks, and event transport | `redis://redis:6379/0` |
| `QDRANT_URL` | Required for vector features | Backend | Qdrant endpoint | `http://qdrant:6333` |
| `QDRANT_API_KEY` | Required only for secured/cloud Qdrant | Backend | Qdrant authentication | blank for local Qdrant |
| `NEXT_PUBLIC_API_URL` | Required outside same-origin proxy deployments | Frontend | Browser-visible API v1 base URL | `http://localhost:8000/api/v1` |
| `NEXT_PUBLIC_WS_URL` | Required for realtime browser features | Frontend | Browser-visible realtime WebSocket base URL | `ws://localhost:8000/api/v1/realtime` |

## AI and retrieval

At least one usable LLM provider must be configured for generated analysis. Deterministic and seeded fallbacks do not replace every AI workflow.

| Variable | Requirement | Service | Purpose | Safe example |
|---|---|---|---|---|
| `GEMINI_API_KEY` | Conditionally required | Backend | Primary Gemini generation | blank |
| `GEMINI_PRIMARY_MODEL` | Optional | Backend | Primary Gemini model | `gemini-2.5-flash` |
| `GEMINI_REASONING_MODEL` | Optional | Backend | Reasoning model | `gemini-2.5-flash` |
| `NVIDIA_API_KEY` | Conditionally required | Backend | NVIDIA embedding/fallback access | blank |
| `NVIDIA_NIM_BASE_URL` | Optional | Backend | NVIDIA API base URL | `https://integrate.api.nvidia.com/v1` |
| `DEEPSEEK_MODEL` | Optional | Backend | Configured fallback model identifier | `meta/llama-3.3-70b-instruct` |
| `QDRANT_RAG_DOCS_COLLECTION` | Optional | Backend | Docs-RAG collection | `careeros_rag_docs` |
| `RAG_EMBEDDING_MODEL` | Optional | Backend | Docs-RAG embedding model | `nvidia/nv-embed-v1` |
| `RAG_LLM_MODEL` | Optional | Backend | Docs-RAG answer model | `gemini-2.5-flash` |
| `RAG_USE_MAKE` | Optional | Backend | Route docs-RAG through Make.com | `false` |
| `MAKE_RAG_WEBHOOK_URL` | Required only when `RAG_USE_MAKE=true` | Backend | Make.com relay URL | blank |
| `MAKE_RAG_API_KEY` | Optional but recommended with Make relay | Backend | Relay authentication | blank |

## Jobs and learning providers

| Variable | Requirement | Service | Purpose | Safe example |
|---|---|---|---|---|
| `THEIRSTACK_API_KEY` / `THEIRSTACK_API_KEY_1..15` | Required for live TheirStack ingestion | Backend, worker | Job provider key rotation slots | blank |
| `THEIRSTACK_API_URL_1..15` | Optional | Backend, worker | Per-slot TheirStack endpoint override | blank |
| `THEIRSTACK_MAX_QUERIES_PER_REFRESH` | Optional | Backend, worker | Refresh query cap | `5` |
| `JOB_AUTO_REFRESH_ENABLED` | Optional | Worker | Scheduled job refresh | `true` |
| `TAVILY_API_KEY` | Conditionally required | Backend | Learning-resource web search | blank |
| `YOUTUBE_API_KEY` | Conditionally required | Backend | YouTube learning-resource discovery | blank |
| `GITHUB_TOKEN` | Optional | Backend | Higher GitHub discovery rate limits | blank |
| `BRAVE_SEARCH_API_KEY` | Optional | Backend | Alternative web search | blank |
| `SERPAPI_API_KEY` | Optional | Backend | Alternative search provider | blank |
| `GOOGLE_CSE_API_KEY` / `GOOGLE_CSE_CX` | Optional | Backend | Google custom search | blank |
| `UDEMY_CLIENT_ID` / `UDEMY_CLIENT_SECRET` | Optional | Backend | Udemy discovery integration | blank |

## Voice and communications

Public/demo setups must retain `OUTBOUND_CALL_DRY_RUN=true` and `CALL_ALERT_DRY_RUN=true` until a human explicitly approves a real recipient test.

| Variable | Requirement | Service | Purpose | Safe example |
|---|---|---|---|---|
| `TWILIO_ACCOUNT_SID` | Required for Twilio actions | Backend, worker | Twilio account identifier | blank |
| `TWILIO_AUTH_TOKEN` | Required for Twilio actions | Backend, worker | Twilio credential | blank |
| `TWILIO_PHONE_NUMBER` | Required for Twilio outbound use | Backend, worker | Provider sender number | blank |
| `ELEVENLABS_API_KEY` | Required for ElevenLabs | Backend, worker | ElevenLabs API credential | blank |
| `ELEVENLABS_CONVAI_AGENT_ID` | Required for conversational calls | Backend, worker | ConvAI agent identifier | blank |
| `ELEVENLABS_CONVAI_PHONE_NUMBER_ID` | Required for conversational calls | Backend, worker | ElevenLabs phone-number resource identifier | blank |
| `OUTBOUND_TEST_TO_NUMBER` | Optional, human-approved testing only | Backend, worker | Explicit recipient for one test call | blank |
| `OUTBOUND_CALL_DRY_RUN` | Required safety default | Backend, worker | Prevent real provider calls | `true` |
| `CALL_ALERT_DRY_RUN` | Required safety default | Backend, worker | Prevent automatic real call alerts | `true` |
| `DEEPGRAM_API_KEY` | Required for Deepgram STT | Backend | Realtime transcription | blank |

## Storage, observability, and demo seed

| Variable | Requirement | Service | Purpose | Safe example |
|---|---|---|---|---|
| `STORAGE_TYPE` | Optional | Backend | `local` or S3-compatible storage | `local` |
| `STORAGE_BASE_PATH` | Required for local storage | Backend | Local upload path | `/tmp/careeros_storage` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Required only for S3 | Backend | S3 credentials | blank |
| `S3_BUCKET_NAME` | Required only for S3 | Backend | Storage bucket | blank |
| `LANGSMITH_ENABLED` | Optional | Backend, worker | LangSmith tracing switch | `false` |
| `LANGSMITH_FAIL_OPEN` | Recommended | Backend, worker | Keep workflows running if tracing fails | `true` |
| `LANGCHAIN_API_KEY` | Required only for LangSmith | Backend, worker | LangSmith credential | blank |
| `SEED_ADMIN_EMAIL` | Optional | Backend startup | Create one local admin only when DB has no users | blank |
| `SEED_ADMIN_PASSWORD` | Required with seed email | Backend startup | Local seeded admin password | blank |
| `SEED_ADMIN_NAME` | Optional | Backend startup | Seeded admin display name | `CareerOS Demo Administrator` |

## Deployment-only variables

Production Compose variants additionally reference the variables below. Replace every placeholder before deployment and review the selected Compose file with `docker compose --env-file .env.example -f <file> config --quiet`. No production credentials or deployment URLs are committed.

| Variable | Requirement | Service | Purpose | Safe example |
|---|---|---|---|---|
| `REGISTRY` | Required for image-based production Compose | Backend, worker, frontend | Container registry hostname/path | `example.invalid` |
| `BACKEND_VERSION` | Required for image-based deployment | Backend | Backend image tag | `latest` |
| `WORKER_VERSION` | Required for image-based deployment | Worker | Worker image tag | `latest` |
| `FRONTEND_VERSION` | Required for image-based deployment | Frontend | Frontend image tag | `latest` |
| `DOMAIN` | Required for public ingress | Frontend | Public DNS name used in browser API/WS URLs | `your-domain.example.com` |
| `DEBUG` | Optional; must remain false publicly | Backend, worker | Debug mode | `false` |
| `LOG_LEVEL` | Optional | Backend, worker | Application log level | `INFO` |
| `ALLOWED_HOSTS` | Required for public ingress | Backend | Accepted host names | `your-domain.example.com` |
| `REDIS_PASSWORD` | Recommended for non-local Redis | Redis, backend, worker | Redis authentication | blank in the public template |

## Source anchors

- Backend defaults and aliases: `backend/src/core/config.py`
- Local stack: `docker-compose.yml`
- Production variants: `docker-compose.prod.yml`, `docker-compose.production.yml`
- Frontend public variables: `frontend/src/hooks/useCareerOS.ts`, `frontend/src/lib/resilience.ts`, `frontend/src/hooks/useWebSocket.ts`
