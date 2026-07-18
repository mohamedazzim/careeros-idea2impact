# Operations, Security, and Observability

Last verified from source code: 2026-06-14

## Authentication and session handling

- JWT-based auth uses `careeros_token`
- Public routes are limited to login and password recovery
- Protected routes are role-gated through the RBAC helper

## Security controls

- Async API design
- Security headers
- CORS middleware
- Rate limiting and retry controls
- Governance gates before autonomous outbound actions

## MCP governance

Voice and message delivery are routed through the MCP layer, which provides governance checks, audit logging, retry handling, and observability.

## Health and operational endpoints

- Live and readiness health checks
- Detailed dependency health checks
- Troubleshoot circuits and audit logs
- Rerank health and stats
- MCP test trace endpoint
- Provider health endpoints for Twilio, ElevenLabs, Pipedream, and TheirStack

## Source anchors

- `backend/src/core/config.py`
- `backend/src/main.py`
- `backend/src/services/mcp`
- `backend/src/agents/orchestration_governance_agent.py`
- `frontend/src/lib/auth-session.ts`
- `frontend/src/lib/rbac.ts`
- `frontend/src/components/SessionMonitor.tsx`
- `frontend/src/hooks/useWebSocket.ts`
