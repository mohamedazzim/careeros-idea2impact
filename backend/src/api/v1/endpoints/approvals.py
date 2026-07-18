"""Phase 17.7 — Human Approval Center Endpoints (Enterprise).

Uses ApprovalRepository for persistence. JWT auth on all endpoints.
No in-memory stores. No demo_user defaults. No query-param auth.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.api.deps import get_current_user_id
from src.db.repositories.domain_repositories import (
    ApprovalRepository, ApprovalItemRepository,
    ApprovalCommentRepository, ApprovalNotificationRepository,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/approvals", tags=["Approvals"])


class ApprovalItemSchema(BaseModel):
    id: int = 0
    approval_id: int = 0
    item_type: str = ""
    content: Optional[Dict[str, Any]] = None
    order_index: int = 0


class ApprovalResponse(BaseModel):
    id: int = 0
    approval_uid: str = ""
    user_id: str = ""
    title: str = ""
    channel: str = "linkedin"
    status: str = "pending"
    draft_content: Optional[Dict[str, Any]] = None
    final_content: Optional[Dict[str, Any]] = None
    auto_generated: bool = False
    confidence: Optional[float] = None
    execution_status: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    items: List[Dict[str, Any]] = []
    comments: List[Dict[str, Any]] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ApprovalStatsResponse(BaseModel):
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    executed: int = 0


class CommentRequest(BaseModel):
    comment_text: str = Field(..., min_length=1)


class CreateApprovalRequest(BaseModel):
    title: str = Field(..., min_length=1)
    channel: str = "linkedin"
    draft_content: Optional[Dict[str, Any]] = None


class EditApprovalRequest(BaseModel):
    draft_content: Dict[str, Any] = Field(...)


def _serialize_approval(a) -> dict:
    return {
        "id": a.id,
        "approval_uid": a.approval_uid,
        "user_id": a.user_id,
        "title": a.title,
        "channel": a.channel,
        "status": a.status,
        "draft_content": a.draft_content,
        "final_content": a.final_content,
        "auto_generated": getattr(a, "auto_generated", False),
        "confidence": a.confidence,
        "execution_status": getattr(a, "execution_status", None),
        "execution_result": getattr(a, "execution_result", None),
        "items": [],
        "comments": [],
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": getattr(a, "updated_at", None) and a.updated_at.isoformat() if hasattr(a, 'updated_at') else None,
    }


@router.get("")
async def list_approvals(
    status: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ApprovalRepository(db)
    approvals, total = await repo.find_by_user(user_id, status=status, limit=limit, offset=offset)

    # Apply channel filter in Python (add to repository if high volume)
    if channel:
        approvals = [a for a in approvals if a.channel == channel]

    return {
        "approvals": [_serialize_approval(a) for a in approvals],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats", response_model=ApprovalStatsResponse)
async def approval_stats(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ApprovalRepository(db)
    return await repo.get_stats(user_id)


@router.get("/notifications")
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    notif_repo = ApprovalNotificationRepository(db)
    notifications = await notif_repo.find_by_user(user_id)
    return {
        "notifications": [
            {
                "id": n.id,
                "user_id": n.user_id,
                "notification_type": n.notification_type,
                "title": n.title,
                "body": n.body,
                "read": n.read,
                "related_approval_id": n.related_approval_id,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
    }


@router.post("/notifications/read")
async def mark_notifications_read(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    notif_repo = ApprovalNotificationRepository(db)
    count = await notif_repo.mark_all_read(user_id)
    return {"status": "ok", "marked_read": count}


@router.get("/{approval_id}")
async def get_approval(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ApprovalRepository(db)
    approval = await repo.get_by_uid(approval_id)
    if not approval:
        try:
            approval = await repo.get_by_id(int(approval_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=404, detail="Approval not found")
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    item_repo = ApprovalItemRepository(db)
    items = await item_repo.find_by_approval(approval.id)

    comment_repo = ApprovalCommentRepository(db)
    comments = await comment_repo.find_by_approval(approval.id)

    result = _serialize_approval(approval)
    result["items"] = [
        {"id": i.id, "item_type": i.item_type, "content": i.content, "order_index": i.order_index}
        for i in items
    ]
    result["comments"] = [
        {"id": c.id, "user_id": c.user_id, "comment_text": c.comment_text,
         "created_at": c.created_at.isoformat() if c.created_at else None}
        for c in comments
    ]
    return result


@router.post("/{approval_id}/comment")
async def add_comment(
    approval_id: str,
    req: CommentRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ApprovalRepository(db)
    approval = await repo.get_by_uid(approval_id)
    if not approval:
        try:
            approval = await repo.get_by_id(int(approval_id))
        except (ValueError, TypeError):
            pass
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    comment_repo = ApprovalCommentRepository(db)
    comment = await comment_repo.create(
        approval_id=approval.id,
        user_id=user_id,
        comment_text=req.comment_text,
    )
    return {
        "status": "ok",
        "comment": {
            "id": comment.id,
            "user_id": comment.user_id,
            "comment_text": comment.comment_text,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
        },
    }


@router.post("/{approval_id}/approve")
async def approve(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ApprovalRepository(db)
    approval = await repo.get_by_uid(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to approve this item")
    await repo.update(approval.id, status="approved", updated_at=datetime.utcnow())
    return {"status": "approved", "approval_uid": approval_id}


@router.post("/{approval_id}/reject")
async def reject(
    approval_id: str,
    reason: str = Query(""),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ApprovalRepository(db)
    approval = await repo.get_by_uid(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to reject this item")
    await repo.update(approval.id, status="rejected", updated_at=datetime.utcnow())
    if reason:
        comment_repo = ApprovalCommentRepository(db)
        await comment_repo.create(
            approval_id=approval.id,
            user_id=user_id,
            comment_text=f"Rejected: {reason}",
        )
    return {"status": "rejected", "approval_uid": approval_id, "reason": reason}


@router.post("/{approval_id}/execute")
async def execute(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ApprovalRepository(db)
    approval = await repo.get_by_uid(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to execute this item")
    if approval.status != "approved":
        raise HTTPException(status_code=400, detail="Only approved items can be executed")

    content = approval.draft_content or {}
    is_alert_action = content.get("generated_by") == "alert_action_service"

    execution_result: Dict[str, Any] = {}
    if is_alert_action:
        execution_result = {"sent_at": datetime.utcnow().isoformat(), "delivered": False}
        from src.services.opportunity.alert_action_service import get_alert_action_service
        try:
            delivery = await get_alert_action_service().execute_approved_action(
                approval_id=approval.id,
                dry_run=False,
            )
            execution_result = {
                "sent_at": datetime.utcnow().isoformat(),
                "delivered": delivery.get("status") == "executed",
                "delivery_status": delivery.get("delivery_status"),
                "decision": delivery.get("decision"),
            }
        except Exception as exc:
            logger.warning("Alert action execution failed for %s: %s", approval_id, exc)
            execution_result = {
                "sent_at": datetime.utcnow().isoformat(),
                "delivered": False,
                "error": str(exc)[:256],
            }
    else:
        execution_result = {
            "sent_at": datetime.utcnow().isoformat(),
            "delivered": True,
        }

    await repo.update(
        approval.id,
        status="executed",
        execution_status="success" if execution_result.get("delivered") else "failed",
        execution_result=execution_result,
        updated_at=datetime.utcnow(),
    )
    return {"status": "executed", "approval_uid": approval_id, "result": execution_result}


@router.post("/{approval_id}/edit")
async def edit(
    approval_id: str,
    req: EditApprovalRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ApprovalRepository(db)
    approval = await repo.get_by_uid(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this item")
    await repo.update(approval.id, draft_content=req.draft_content, updated_at=datetime.utcnow())
    return {"status": "edited", "approval_uid": approval_id}


@router.post("")
async def create_approval(
    req: CreateApprovalRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ApprovalRepository(db)
    approval = await repo.create(
        user_id=user_id,
        title=req.title,
        channel=req.channel,
        status="pending",
        draft_content=req.draft_content,
        auto_generated=False,
    )
    return _serialize_approval(approval)
