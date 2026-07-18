"""Enhanced Application Lifecycle Service with full state machine and audit trail."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.outcome_intelligence import (
    ApplicationLifecycle,
    ApplicationLifecycleAudit,
)
from src.observability.langsmith import traceable

VALID_STATES = [
    "DISCOVERED", "CONTACTED", "INTERESTED", "APPLYING", "APPLIED",
    "ASSESSMENT", "INTERVIEW", "FINAL_ROUND", "OFFER",
    "REJECTED", "HIRED", "WITHDRAWN",
]

STATE_TRANSITIONS = {
    "DISCOVERED": ["CONTACTED", "INTERESTED", "WITHDRAWN"],
    "CONTACTED": ["INTERESTED", "APPLYING", "REJECTED", "WITHDRAWN"],
    "INTERESTED": ["APPLYING", "ASSESSMENT", "WITHDRAWN"],
    "APPLYING": ["APPLIED", "WITHDRAWN"],
    "APPLIED": ["ASSESSMENT", "INTERVIEW", "REJECTED", "WITHDRAWN"],
    "ASSESSMENT": ["INTERVIEW", "REJECTED", "WITHDRAWN"],
    "INTERVIEW": ["FINAL_ROUND", "OFFER", "REJECTED", "WITHDRAWN"],
    "FINAL_ROUND": ["OFFER", "REJECTED", "WITHDRAWN"],
    "OFFER": ["HIRED", "WITHDRAWN"],
    "REJECTED": [],
    "HIRED": [],
    "WITHDRAWN": [],
}


class EnhancedApplicationLifecycleService:
    """Full lifecycle management with state machine validation and audit trail."""

    @traceable(name="lifecycle_transition")
    async def transition(
        self,
        db: AsyncSession,
        *,
        candidate_id: str,
        job_id: int,
        new_state: str,
        reason: str,
        actor: str = "system",
        confidence: float = 0.8,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if new_state not in VALID_STATES:
            raise ValueError(f"Invalid state: {new_state}. Valid: {VALID_STATES}")

        row = (await db.execute(select(ApplicationLifecycle).where(
            ApplicationLifecycle.candidate_id == candidate_id,
            ApplicationLifecycle.job_id == job_id,
        ))).scalar_one_or_none()

        from_state = row.state if row else None

        if from_state and new_state not in STATE_TRANSITIONS.get(from_state, []):
            raise ValueError(
                f"Invalid transition: {from_state} -> {new_state}. "
                f"Allowed: {STATE_TRANSITIONS.get(from_state, [])}"
            )

        if not row:
            row = ApplicationLifecycle(
                candidate_id=candidate_id,
                job_id=job_id,
                state=new_state,
                reason=reason,
                confidence=confidence,
            )
            db.add(row)
        else:
            row.state = new_state
            row.reason = reason
            row.confidence = confidence
            row.updated_at = datetime.utcnow()

        audit = ApplicationLifecycleAudit(
            candidate_id=candidate_id,
            job_id=job_id,
            from_state=from_state,
            to_state=new_state,
            reason=reason,
            confidence=confidence,
            actor=actor,
            metadata_json=metadata_json,
        )
        db.add(audit)
        await db.flush()

        return {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "from_state": from_state,
            "to_state": new_state,
            "actor": actor,
            "audit_id": audit.id,
        }

    @traceable(name="lifecycle_get_history")
    async def get_history(
        self,
        db: AsyncSession,
        *,
        candidate_id: str,
        job_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(ApplicationLifecycleAudit)
            .where(ApplicationLifecycleAudit.candidate_id == candidate_id)
        )
        if job_id:
            stmt = stmt.where(ApplicationLifecycleAudit.job_id == job_id)
        stmt = stmt.order_by(desc(ApplicationLifecycleAudit.created_at)).limit(limit)

        rows = (await db.execute(stmt)).scalars().all()
        return [
            {
                "id": r.id,
                "job_id": r.job_id,
                "from_state": r.from_state,
                "to_state": r.to_state,
                "reason": r.reason,
                "confidence": r.confidence,
                "actor": r.actor,
                "created_at": r.created_at.isoformat(),
                "metadata": r.metadata_json,
            }
            for r in rows
        ]

    @traceable(name="lifecycle_get_current")
    async def get_current(
        self,
        db: AsyncSession,
        *,
        candidate_id: str,
        job_id: int,
    ) -> Optional[Dict[str, Any]]:
        row = (await db.execute(select(ApplicationLifecycle).where(
            ApplicationLifecycle.candidate_id == candidate_id,
            ApplicationLifecycle.job_id == job_id,
        ))).scalar_one_or_none()
        if not row:
            return None
        return {
            "job_id": row.job_id,
            "state": row.state,
            "reason": row.reason,
            "confidence": row.confidence,
            "updated_at": row.updated_at.isoformat(),
            "created_at": row.created_at.isoformat(),
            "valid_next_states": STATE_TRANSITIONS.get(row.state, []),
        }

    @traceable(name="lifecycle_list_all")
    async def list_all(
        self,
        db: AsyncSession,
        *,
        candidate_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        stmt = (
            select(ApplicationLifecycle)
            .where(ApplicationLifecycle.candidate_id == candidate_id)
            .order_by(desc(ApplicationLifecycle.updated_at))
            .offset(offset)
            .limit(limit)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return {
            "items": [
                {
                    "job_id": r.job_id,
                    "state": r.state,
                    "reason": r.reason,
                    "confidence": r.confidence,
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in rows
            ],
            "total": len(rows),
        }


def get_enhanced_lifecycle_service() -> EnhancedApplicationLifecycleService:
    return EnhancedApplicationLifecycleService()
