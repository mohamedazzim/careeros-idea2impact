"""Phase 17.7 — Troubleshooting & Ops Center Endpoints (hardened).

Uses CircuitStateRepository, AuditLogRepository, PendingJobRepository.
No in-memory stores, no demo data, no hardcoded fallbacks.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.db.repositories.troubleshoot_repository import (
    CircuitStateRepository, AuditLogRepository, PendingJobRepository,
)
from src.api.deps import require_role
from src.observability.logger import structured_logger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/troubleshoot", tags=["Troubleshooting"])


class CircuitToggleRequest(BaseModel):
    circuit_name: str
    action: str = "toggle"


@router.get("/circuits")
async def list_circuits(db: AsyncSession = Depends(get_db)):
    """List all circuit breaker states."""
    repo = CircuitStateRepository(db)
    circuits = await repo.get_all(limit=100)
    return {
        "circuits": [
            {
                "name": c.name,
                "service": c.service,
                "state": c.state,
                "failure_count": c.failure_count,
                "last_failure": c.last_failure.isoformat() if c.last_failure else None,
                "last_success": c.last_success.isoformat() if c.last_success else None,
            }
            for c in circuits
        ],
        "total": len(circuits),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/circuits/toggle")
async def toggle_circuit(req: CircuitToggleRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("Admin"))):
    """Toggle circuit breaker state. Admin only."""
    repo = CircuitStateRepository(db)
    circuits = await repo.find_by_service(req.circuit_name)
    circuit = circuits[0] if circuits else None
    if not circuit:
        raise HTTPException(status_code=404, detail=f"Circuit '{req.circuit_name}' not found")

    new_state = "open" if req.action == "open" else ("closed" if req.action == "close" else ("open" if circuit.state == "closed" else "closed"))
    await repo.update(circuit.id, state=new_state, failure_count=0 if new_state == "closed" else circuit.failure_count)

    structured_logger.info(f"Circuit {req.circuit_name} toggled to {new_state}", extra={
        "service": "troubleshoot", "circuit": req.circuit_name, "new_state": new_state,
    })
    return {"name": req.circuit_name, "state": new_state}


@router.get("/audit")
async def audit_logs(
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Security audit log with search."""
    repo = AuditLogRepository(db)
    logs, total = await repo.find_paginated(limit=limit, offset=offset, order_by=None)
    if search:
        logs = [l for l in logs if search.lower() in str(l.action).lower() or search.lower() in str(l.resource).lower()]
        total = len(logs)

    return {
        "logs": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "action": l.action,
                "resource": l.resource,
                "resource_id": l.resource_id,
                "details": l.details,
                "severity": l.severity,
                "timestamp": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/pending")
async def pending_jobs(db: AsyncSession = Depends(get_db)):
    """List pending/degraded background jobs."""
    repo = PendingJobRepository(db)
    jobs = await repo.find_pending(limit=100)
    return {
        "jobs": [
            {
                "job_id": j.job_uid,
                "type": j.job_type,
                "status": j.status,
                "priority": j.priority,
                "attempts": j.retry_count,
                "max_attempts": j.max_retries,
                "error": j.error_message,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ],
        "total": len(jobs),
    }
