"""Phase 17.5 — Approvals Models.

Tables: approvals, approval_items, approval_comments, approval_notifications
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON, DateTime, Float, Integer, String, Text, Index, Boolean, ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False, default="linkedin")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    draft_content: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    final_content: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    execution_status: Mapped[Optional[str]] = mapped_column(String(32))
    execution_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list] = relationship("ApprovalItem", back_populates="approval", cascade="all, delete-orphan")
    comments: Mapped[list] = relationship("ApprovalComment", back_populates="approval", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_approvals_user_status", "user_id", "status"),
        Index("ix_approvals_channel", "channel"),
    )


class ApprovalItem(Base):
    __tablename__ = "approval_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_id: Mapped[int] = mapped_column(Integer, ForeignKey("approvals.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    approval: Mapped["Approval"] = relationship(back_populates="items")


class ApprovalComment(Base):
    __tablename__ = "approval_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_id: Mapped[int] = mapped_column(Integer, ForeignKey("approvals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    approval: Mapped["Approval"] = relationship(back_populates="comments")


class ApprovalNotification(Base):
    __tablename__ = "approval_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    related_approval_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("approvals.id", ondelete="SET NULL"), index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_approval_notif_user_read", "user_id", "read"),
    )
