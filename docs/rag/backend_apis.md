# Backend API Surface

Last verified from source code: 2026-06-14

## API organization

The backend is split into router modules under `backend/src/api/v1/endpoints`.
Each module owns a domain boundary and exposes async endpoints for the frontend and background systems.

## Important routers

- `auth.py`
- `jobs.py`
- `knowledge.py`
- `opportunities_api.py`
- `interview.py`
- `orchestration.py`
- `approvals.py`
- `readiness.py`
- `evaluation.py`
- `realtime.py`
- `mcp.py`
- `health.py`

## Representative endpoints

| Domain | Endpoint examples |
| --- | --- |
| Auth | `POST /api/v1/auth/login`, `GET /api/v1/auth/me` |
| Jobs | `GET /api/v1/jobs`, `POST /api/v1/jobs/refresh` |
| Knowledge | `POST /api/v1/knowledge/upload`, `POST /api/v1/knowledge/{doc_id}/analyze` |
| Opportunities | `POST /api/v1/opportunities/discover`, `GET /api/v1/opportunities/list` |
| Interview | `POST /api/v1/interview/start`, `POST /api/v1/interview/respond` |
| Orchestration | `POST /api/v1/orchestration/trigger`, `GET /api/v1/orchestration/history` |
| Approvals | `POST /api/v1/approvals/{approval_id}/approve`, `POST /api/v1/approvals/{approval_id}/reject` |
| Demo RAG | `POST /api/v1/demo-rag/chat` |
| Health | `GET /api/health/live`, `GET /api/health/ready`, `GET /api/health/deep` |

## Source anchors

- `backend/src/api/v1/endpoints`
- `backend/src/main.py`
