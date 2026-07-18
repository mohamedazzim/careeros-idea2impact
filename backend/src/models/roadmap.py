"""Phase 17.5 — Career Roadmap Models.

Tables: roadmaps, roadmap_goals, roadmap_tasks
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, DateTime, Float, Integer, String, Text, Boolean, ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Roadmap(Base):
    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    roadmap_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="Career Roadmap")
    target_role: Mapped[Optional[str]] = mapped_column(String(256))
    target_salary: Mapped[Optional[str]] = mapped_column(String(128))
    target_location: Mapped[Optional[str]] = mapped_column(String(256))
    target_timeline: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    recommendations: Mapped[Optional[list]] = mapped_column(JSON)
    velocity_history: Mapped[Optional[list]] = mapped_column(JSON)
    trace_id: Mapped[Optional[str]] = mapped_column(String(128))
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    goals: Mapped[list] = relationship("RoadmapGoal", back_populates="roadmap", cascade="all, delete-orphan")


class RoadmapGoal(Base):
    __tablename__ = "roadmap_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    roadmap_id: Mapped[int] = mapped_column(Integer, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), default="skill")
    priority: Mapped[int] = mapped_column(Integer, default=1)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    roadmap: Mapped["Roadmap"] = relationship(back_populates="goals")
    tasks: Mapped[list] = relationship("RoadmapTask", back_populates="goal", cascade="all, delete-orphan")


class RoadmapTask(Base):
    __tablename__ = "roadmap_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    goal_id: Mapped[int] = mapped_column(Integer, ForeignKey("roadmap_goals.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    due_date: Mapped[Optional[str]] = mapped_column(String(64))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    goal: Mapped["RoadmapGoal"] = relationship(back_populates="tasks")
