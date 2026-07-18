"""Phase 6 — Human-in-the-Loop.

Approval gateway, escalation manager, and intervention handler
for pausing, approving, and resuming autonomous orchestration.
"""

import uuid
import time
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from src.core.config import settings

logger = logging.getLogger(__name__)

APPROVAL_KEY = "orch:approval:"
ESCALATION_KEY = "orch:escalation:"


@dataclass
class ApprovalRequest:
    approval_id: str
    session_uid: str
    action_type: str
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, approved, denied, expired
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolved_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


class ApprovalGateway:
    """Human-in-the-loop approval for autonomous actions."""

    async def request_approval(
        self,
        session_uid: str,
        action_type: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: int = 3600,
    ) -> ApprovalRequest:
        """Create an approval request and wait for resolution."""
        approval = ApprovalRequest(
            approval_id=str(uuid.uuid4()),
            session_uid=session_uid,
            action_type=action_type,
            description=description,
            metadata=metadata or {},
        )
        try:
            from src.db.redis import redis_client
            key = f"{APPROVAL_KEY}{approval.approval_id}"
            await redis_client.setex(key, ttl, json.dumps(approval.to_dict()))
            logger.info(f"Approval requested: {approval.approval_id} ({action_type})")
        except Exception as exc:
            logger.error(f"Approval request failed: {exc}")
        return approval

    async def approve(self, approval_id: str, approved_by: str = "system") -> Optional[ApprovalRequest]:
        """Approve a pending request."""
        try:
            from src.db.redis import redis_client
            key = f"{APPROVAL_KEY}{approval_id}"
            raw = await redis_client.get(key)
            if not raw:
                return None
            approval = ApprovalRequest(**json.loads(raw))
            if approval.status != "pending":
                return approval
            approval.status = "approved"
            approval.resolved_at = time.time()
            approval.resolved_by = approved_by
            await redis_client.setex(key, 3600, json.dumps(approval.to_dict()))
            return approval
        except Exception as exc:
            logger.error(f"Approval failed: {exc}")
            return None

    async def deny(self, approval_id: str, denied_by: str = "system", reason: str = "") -> Optional[ApprovalRequest]:
        """Deny a pending request."""
        try:
            from src.db.redis import redis_client
            key = f"{APPROVAL_KEY}{approval_id}"
            raw = await redis_client.get(key)
            if not raw:
                return None
            approval = ApprovalRequest(**json.loads(raw))
            approval.status = "denied"
            approval.resolved_at = time.time()
            approval.resolved_by = denied_by
            approval.metadata["deny_reason"] = reason
            await redis_client.setex(key, 3600, json.dumps(approval.to_dict()))
            return approval
        except Exception as exc:
            logger.error(f"Deny failed: {exc}")
            return None

    async def get_status(self, approval_id: str) -> Optional[ApprovalRequest]:
        try:
            from src.db.redis import redis_client
            raw = await redis_client.get(f"{APPROVAL_KEY}{approval_id}")
            if raw:
                return ApprovalRequest(**json.loads(raw))
        except Exception:
            pass
        return None

    async def list_pending(self) -> List[Dict[str, Any]]:
        try:
            from src.db.redis import redis_client
            cursor = 0
            pending = []
            while True:
                cursor, keys = await redis_client.scan(cursor, match=f"{APPROVAL_KEY}*")
                for key in keys:
                    raw = await redis_client.get(key)
                    if raw:
                        approval = json.loads(raw)
                        if approval.get("status") == "pending":
                            pending.append(approval)
                if cursor == 0:
                    break
            return pending
        except Exception:
            return []


class EscalationManager:
    """Manages escalation workflows for critical decisions."""

    async def escalate(
        self,
        session_uid: str,
        reason: str,
        severity: str = "high",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Escalate an orchestration issue for human review."""
        escalation_id = str(uuid.uuid4())
        try:
            from src.db.redis import redis_client
            key = f"{ESCALATION_KEY}{escalation_id}"
            payload = {
                "escalation_id": escalation_id,
                "session_uid": session_uid,
                "reason": reason,
                "severity": severity,
                "metadata": metadata or {},
                "status": "pending",
                "created_at": time.time(),
            }
            await redis_client.setex(key, 86400, json.dumps(payload))
            logger.warning(f"Escalation {escalation_id}: {reason}")
        except Exception as exc:
            logger.error(f"Escalation failed: {exc}")
        return escalation_id

    async def resolve_escalation(self, escalation_id: str, resolution: str) -> bool:
        try:
            from src.db.redis import redis_client
            key = f"{ESCALATION_KEY}{escalation_id}"
            raw = await redis_client.get(key)
            if not raw:
                return False
            payload = json.loads(raw)
            payload["status"] = "resolved"
            payload["resolution"] = resolution
            payload["resolved_at"] = time.time()
            await redis_client.setex(key, 86400, json.dumps(payload))
            return True
        except Exception:
            return False


class InterventionHandler:
    """Handles manual intervention in running orchestrations."""

    async def pause(self, session_uid: str) -> bool:
        """Pause a running orchestration."""
        try:
            from src.db.redis import redis_client
            key = f"orch:session:{session_uid}"
            raw = await redis_client.get(key)
            if raw:
                state = json.loads(raw)
                state["status"] = "paused"
                state["paused_at"] = time.time()
                await redis_client.setex(key, 3600, json.dumps(state))
            return True
        except Exception:
            return False

    async def resume(self, session_uid: str) -> bool:
        """Resume a paused orchestration."""
        try:
            from src.db.redis import redis_client
            key = f"orch:session:{session_uid}"
            raw = await redis_client.get(key)
            if not raw:
                return False
            state = json.loads(raw)
            if state.get("status") != "paused":
                return False
            state["status"] = "active"
            del state["paused_at"]
            await redis_client.setex(key, 3600, json.dumps(state))
            return True
        except Exception:
            return False

    async def override_governance(self, session_uid: str, reason: str) -> bool:
        """Override governance suppression for a session."""
        try:
            from src.db.redis import redis_client
            key = f"orch:session:{session_uid}"
            raw = await redis_client.get(key)
            if not raw:
                return False
            state = json.loads(raw)
            state["governance_overridden"] = True
            state["override_reason"] = reason
            await redis_client.setex(key, 3600, json.dumps(state))
            logger.warning(f"Governance override for {session_uid}: {reason}")
            return True
        except Exception:
            return False


# ── Singletons ───────────────────────────────────────────────────────

_gateway: Optional[ApprovalGateway] = None
_escalation: Optional[EscalationManager] = None
_intervention: Optional[InterventionHandler] = None


def get_approval_gateway() -> ApprovalGateway:
    global _gateway
    if _gateway is None:
        _gateway = ApprovalGateway()
    return _gateway


def get_escalation_manager() -> EscalationManager:
    global _escalation
    if _escalation is None:
        _escalation = EscalationManager()
    return _escalation


def get_intervention_handler() -> InterventionHandler:
    global _intervention
    if _intervention is None:
        _intervention = InterventionHandler()
    return _intervention
