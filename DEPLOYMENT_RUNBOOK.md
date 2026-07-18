# CareerOS Deployment Runbook

Date: 2026-07-18

## Scope

This runbook prepares CareerOS for a VPS-style Docker deployment. The public repository is history-free and deployment credentials must be supplied only through an ignored `.env` file or the selected hosting provider's encrypted secret manager.

## Production Prerequisites

- Linux VPS with Docker and Docker Compose installed.
- Public DNS record pointing to the VPS.
- TLS termination through Caddy, Nginx, Traefik, or equivalent.
- Firewall allowing only SSH, HTTP, and HTTPS from the public internet.
- Provider credentials supplied through a trusted secret manager or ignored `.env` file.
- A production `.env` file stored outside version control.

## Required Environment

Create a production environment file with placeholders replaced by real values:

```bash
ENVIRONMENT=production
SECRET_KEY=<strong-random-secret>

DATABASE_URL=postgresql+asyncpg://<user>:<password>@db:5432/careeros
POSTGRES_USER=<user>
POSTGRES_PASSWORD=<password>
POSTGRES_DB=careeros

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_URL=redis://redis:6379/0

QDRANT_URL=http://qdrant:6333

BACKEND_CORS_ORIGINS=https://<domain>
NEXT_PUBLIC_API_URL=https://<domain>/api/v1
NEXT_PUBLIC_WS_URL=wss://<domain>/api/v1/realtime

NVIDIA_API_KEY=<provider-key>

TWILIO_ACCOUNT_SID=<twilio-account-sid>
TWILIO_AUTH_TOKEN=<twilio-auth-token>
TWILIO_PHONE_NUMBER=<twilio-from-number>
TWILIO_TEST_PHONE_NUMBER=<mentor-safe-test-number>

ELEVENLABS_API_KEY=<optional>
LANGCHAIN_API_KEY=<optional>
AWS_ACCESS_KEY_ID=<optional>
AWS_SECRET_ACCESS_KEY=<optional>
AWS_REGION=<optional>
S3_BUCKET_NAME=<optional>
STORAGE_TYPE=<local-or-s3>

CALL_ALERT_DRY_RUN=true
OUTBOUND_CALL_DRY_RUN=true
RAG_USE_MAKE=false
JOB_AUTO_REFRESH_ENABLED=false
SEED_DEMO_EMAIL=<fictional-demo-user-email>
SEED_DEMO_PASSWORD=<secret-manager-value>
SEED_DEMO_NAME=CareerOS Demo User
SEED_DEMO_ROLE=User
```

Never commit this file.

## Pre-Deployment Blockers

Complete these before public exposure:

1. Remove hardcoded secrets from `docker-compose.yml`.
2. Remove hardcoded provider keys from tracked scripts.
3. Rotate all exposed keys and tokens.
4. Store temporary non-admin demo-user credentials outside Git.
5. Replace localhost frontend URLs with production HTTPS/WSS URLs.
6. Restrict PostgreSQL, Redis, and Qdrant to private Docker networking or localhost bindings.
7. Confirm logs redact secrets and sensitive identifiers.

## Build And Start Sequence

From the repository root:

```bash
git status --short
docker compose config --quiet
docker compose build
docker compose up -d db redis qdrant
docker compose ps
```

Wait for `db`, `redis`, and `qdrant` to report healthy.

Run migrations:

```bash
docker compose run --rm backend alembic upgrade head
```

Start application services:

```bash
docker compose up -d backend worker frontend
docker compose ps
```

Verify migration state:

```bash
docker compose exec -T backend alembic current
docker compose exec -T backend alembic heads
```

Expected migration head:

```text
033_schema_contract_alignment (head)
```

## Reverse Proxy

Route public traffic through HTTPS.

Recommended public routes:

- `https://<domain>/` -> frontend container port `3000`
- `https://<domain>/api/` -> backend container port `8000`
- `wss://<domain>/api/v1/realtime` -> backend websocket endpoint

Proxy requirements:

- Preserve `Host`, `X-Forwarded-For`, `X-Forwarded-Proto`, and websocket upgrade headers.
- Do not log authorization headers.
- Do not log sensitive query strings.
- Redirect HTTP to HTTPS.

## Firewall

Publicly allow:

- `22/tcp` for SSH, restricted by key and source IP if possible.
- `80/tcp` for HTTP challenge or redirect.
- `443/tcp` for HTTPS.

Do not publicly expose:

- PostgreSQL `5432`
- Redis `6379`
- Qdrant `6333` or `6334`
- Backend `8000` directly, unless behind a private proxy boundary.
- Frontend `3000` directly, unless behind a private proxy boundary.

## Smoke Tests

Run after deployment:

```bash
curl -fsS https://<domain>/api/health/live
curl -fsS https://<domain>/api/health/ready
curl -fsS https://<domain>/
```

Application checks:

- Register or log in with a fictional non-admin demo user.
- Open dashboard without browser console errors.
- Generate an application package.
- Confirm the package completes even if the LLM provider is unavailable.
- Confirm fallback packages are marked `DEMO_GENERATED`.
- Download the generated package.
- Regenerate the package.
- Open orchestration/agent activity and confirm workflow events appear.
- Keep Twilio and outbound call paths in dry-run mode for public judging unless a human explicitly approves one safe live test.

## Twilio Verification

Do not claim live call success unless all are true:

- The Twilio API returns success.
- A call SID is captured.
- The target number is approved for the demo.
- Logs are redacted before sharing.

If Twilio returns HTTP 401, state:

```text
The MCP path reached Twilio's live API, but live call placement is blocked by credentials.
```

## Package Generation Verification

Expected behavior:

- AI provider succeeds: generated package uses provider output.
- AI provider fails or times out: deterministic fallback package is generated.
- Fallback package is marked `DEMO_GENERATED`.
- UI does not show a package failure during the mentor demo path.

## Rollback

If a deployment fails:

```bash
docker compose logs --tail=200 backend
docker compose logs --tail=200 worker
docker compose logs --tail=200 frontend
docker compose down
```

Restore the previous known-good image or commit, then:

```bash
docker compose build
docker compose up -d db redis qdrant
docker compose run --rm backend alembic upgrade head
docker compose up -d backend worker frontend
docker compose ps
```

Do not roll back database migrations unless a tested downgrade path exists.

## Production Acceptance Criteria

CareerOS is VPS-ready only when:

- No hardcoded secrets remain in tracked files.
- All exposed credentials are rotated.
- `ENVIRONMENT=production` and `DEBUG=False`.
- Public API and websocket URLs use HTTPS/WSS.
- CORS is restricted to production origins.
- Demo credentials are temporary, non-admin, and stored outside Git.
- Migrations run successfully.
- Internal services are not publicly exposed.
- Logs are redacted.
- Package, orchestration, and Twilio smoke tests pass with production configuration.

