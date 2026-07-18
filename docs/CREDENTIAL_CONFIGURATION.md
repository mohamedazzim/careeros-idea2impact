# CareerOS Credential Configuration

Last verified from source code: 2026-07-18

CareerOS reads provider credentials from environment variables. Populated `.env` files must stay outside Git.

## Public Default Posture

| Provider area | Public default | Reason |
|---|---|---|
| PostgreSQL, Redis, Qdrant | Local Docker services | Enables local review without cloud credentials. |
| Gemini | Unconfigured until supplied | Required for live LLM generation. |
| NVIDIA embeddings | Unconfigured until supplied | Required for real embedding generation; fallback paths are for offline development only. |
| TheirStack job ingestion | Disabled by default | Prevents automatic external job-provider calls in public demo setup. |
| Learning web search | Disabled by default | Seeded resources remain available without external search keys. |
| GitHub discovery | Disabled by default | Seeded project guidance remains available without a GitHub token. |
| Twilio and ElevenLabs | Dry-run by default | Prevents real phone calls unless explicitly approved and configured. |
| Deepgram | Unconfigured by default | Speech-to-text is labelled unavailable when no key is supplied. |
| Make.com and Pipedream | Unconfigured by default | Prevents webhook dispatch in the public demo stack. |
| LangSmith | Disabled and fail-open by default | Business workflows continue if tracing is unavailable. |

## Required Local Values

| Variable | Purpose | Public template |
|---|---|---|
| `SECRET_KEY` | JWT and application signing secret | Placeholder only; replace locally. |
| `POSTGRES_PASSWORD` | Local PostgreSQL password | Placeholder only; replace locally. |
| `GEMINI_API_KEY` | LLM answer generation | Blank. |
| `NVIDIA_API_KEY` | Real embeddings/reranking | Blank. |
| `QDRANT_URL` | Vector database URL | `http://qdrant:6333`. |
| `QDRANT_API_KEY` | Qdrant Cloud API key when using cloud | Blank. |

## Optional Provider Variables

| Variable group | Feature enabled when populated |
|---|---|
| `THEIRSTACK_API_KEY`, `THEIRSTACK_API_KEY_1` ... `THEIRSTACK_API_KEY_15` | Live job ingestion. |
| `TWILIO_*`, `ELEVENLABS_*` | Live outbound/conversational voice workflows. |
| `MAKE_RAG_WEBHOOK_URL`, `MAKE_RAG_API_KEY` | Make.com RAG relay mode. |
| `PIPEDREAM_WEBHOOK_URL` | Pipedream delivery integration. |
| `DEEPGRAM_API_KEY` | Realtime speech-to-text provider. |
| `BRAVE_SEARCH_API_KEY`, `SERPAPI_API_KEY`, `TAVILY_API_KEY`, `GOOGLE_CSE_API_KEY`, `YOUTUBE_API_KEY` | Dynamic learning-resource discovery. |
| `GITHUB_TOKEN` | GitHub repository and issue discovery. |
| `AWS_*`, `S3_*` | S3-backed document storage. |

## Verified Demo-Safe Overrides

The isolated publication E2E used these safe runtime conditions:

| Setting | Verified value |
|---|---|
| `JOB_AUTO_REFRESH_ENABLED` | `false` |
| `CALL_ALERT_DRY_RUN` | `true` |
| `OUTBOUND_CALL_DRY_RUN` | `true` |
| `RAG_USE_MAKE` | `false` |
| `PIPEDREAM_WEBHOOK_URL` | Empty after stripping whitespace |
| `MAKE_RAG_WEBHOOK_URL` | Empty after stripping whitespace |
| TheirStack key slots | Empty after stripping whitespace |
| `QDRANT_URL` | Local Compose service |

The reviewer workflow verified real NVIDIA and Gemini configuration through safe boolean checks only. No key values were printed or committed.

## Credential Reuse Status

For local validation, existing provider credentials may be temporarily reused by the operator in the ignored root `.env`. That reuse is an operator decision and is not represented in the repository.

Before any public or long-lived deployment:

- rotate any previously exposed provider credentials,
- supply secrets through the deployment platform or a secret manager,
- keep `.env` out of Git,
- avoid sharing logs that include provider payloads or tokens,
- keep live outbound calls disabled until a human approves the exact test recipient.
