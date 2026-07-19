# CareerOS Publication Readiness

## Public Repository Hygiene

- The current public source tree was scanned for committed credentials.
- No active credentials are included in the repository.
- Environment-specific values are provided through `.env.example`.
- Private candidate data is not included.
- Demonstration assets use fictional and synthetic data.

## Verification Summary

- Backend application import and startup validation completed.
- Backend full test gate completed: `1090` collected, `1042` passed, `48` skipped, `0` failed, `199` warnings.
- Backend integration marker completed: `1` passed, `14` skipped, `1075` deselected, `0` failed.
- Fresh PostgreSQL migration completed to `034_resume_updated_at_default`.
- Alembic metadata comparison completed with `0` detected upgrade operations.
- Frontend type checking completed.
- Frontend lint completed with no errors and `211` warnings.
- Frontend Vitest suite completed: `1` real CareerOS test file, `10` tests passed.
- Frontend production build completed.
- Docker Compose configurations were validated.
- PostgreSQL, Redis and Qdrant were exercised in isolated and deployed environments.
- A synthetic end-to-end CareerOS workflow was validated locally and against the public Azure deployment.

## Synthetic Demonstration Flow

The public demo uses fictional data to validate:

1. User authentication
2. Resume ingestion
3. Candidate-profile analysis
4. Document chunking and vector storage
5. Opportunity matching
6. Explainable match evidence
7. Skill-gap analysis
8. Preparation-action generation
9. PostgreSQL persistence
10. Qdrant retrieval health

## Security and Privacy

- Secrets must be supplied through environment variables.
- Real candidate resumes must not be committed.
- Synthetic examples use reserved example identifiers.
- Production credentials must be rotated and managed outside Git.
- Users should not upload sensitive information into untrusted deployments.

## Current Validation Status

| Area | Status |
|---|---|
| Current-tree credential scan | Passed |
| Current-tree privacy review | Passed |
| Frontend type checking | Passed |
| Frontend lint | Passed with no errors; 211 warnings |
| Frontend automated test suite | Passed; 1 file, 10 tests |
| Frontend production build | Passed |
| Docker Compose parsing | Passed |
| Production Docker image build | Passed |
| Fresh Alembic upgrade | Passed; deployed head `034_resume_updated_at_default` |
| Alembic metadata comparison | Passed; 0 detected upgrade operations |
| Synthetic end-to-end workflow | Passed |
| Complete backend test suite | Passed; 1042 passed, 48 skipped, 0 failed |
| Integration marker suite | Passed; 1 passed, 14 skipped |
| Public hosting deployment | Passed on Azure Ubuntu VPS |
| Public liveness/readiness | Passed |
| Docs-RAG indexing | Passed; 18 files, 127 chunks, 127 Qdrant points |
| Persistence restart check | Passed for PostgreSQL records and Qdrant vectors |
| Dependency audit | 2 moderate Next/PostCSS-chain advisories |

## Live Deployment

| Endpoint | URL |
|---|---|
| Frontend | `https://careeros-idea2impact-azzim.koreacentral.cloudapp.azure.com` |
| Backend API | `https://careeros-idea2impact-azzim.koreacentral.cloudapp.azure.com/api` |
| Liveness | `https://careeros-idea2impact-azzim.koreacentral.cloudapp.azure.com/api/health/live` |
| Readiness | `https://careeros-idea2impact-azzim.koreacentral.cloudapp.azure.com/api/health/ready` |
| Docs-RAG health | `https://careeros-idea2impact-azzim.koreacentral.cloudapp.azure.com/api/v1/demo-rag/health` |

Deployment architecture:

- Azure Ubuntu VPS
- Docker Compose services: Nginx, Next.js frontend, FastAPI backend, ARQ worker, PostgreSQL, Redis, Qdrant
- Nginx HTTPS edge with Docker DNS service resolution
- Persistent PostgreSQL and Qdrant volumes
- Gemini for grounded answer generation
- NVIDIA embeddings for vector search
- Non-admin fictional demo user

## Known Limitations

- Some integration tests require external services or optional local dependencies.
- Frontend automated coverage is intentionally small and does not replace browser E2E testing.
- The current dependency audit reports moderate Next/PostCSS-chain advisories; the recommended forced fix would downgrade Next across a breaking major line, so it is not applied automatically.
- Provider-backed voice, live job ingestion, webhooks and speech-to-text require trusted credentials and explicit operator approval outside the public repository.
- The public deployment uses a temporary Azure hostname for hackathon judging.
- Deepgram speech-to-text remains unavailable/disabled in the public demo.
- Twilio, Make.com, Pipedream, and automatic external application actions remain dry-run or blocked.

## Responsible Demo Usage

The included demo data is fictional. The application must be configured with valid external-provider credentials only in trusted environments.
