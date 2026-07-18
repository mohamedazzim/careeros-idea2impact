"""Phase 17.7 — User Preferences Endpoint (Enterprise).

Uses PreferencesRepository for persistence. JWT auth required.
No in-memory stores. No demo_user defaults.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.api.deps import get_current_user_id
from src.db.repositories.domain_repositories import PreferencesRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["User Preferences"])


class PreferencesUpdateRequest(BaseModel):
    notification_email: Optional[str] = None
    alert_threshold: Optional[int] = Field(None, ge=50, le=100)
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    extra: Optional[dict] = None


@router.get("/preferences")
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = PreferencesRepository(db)
    prefs = await repo.get_by_user(user_id)
    if not prefs:
        prefs = await repo.upsert(user_id, alert_threshold=75, theme="system", language="en")
    return {
        "user_id": prefs.user_id,
        "notification_email": prefs.notification_email,
        "alert_threshold": prefs.alert_threshold,
        "quiet_hours_start": prefs.quiet_hours_start,
        "quiet_hours_end": prefs.quiet_hours_end,
        "theme": prefs.theme,
        "language": prefs.language,
        "extra": prefs.extra or {},
        "updated_at": prefs.updated_at.isoformat() if prefs.updated_at else None,
    }


@router.put("/preferences")
async def update_preferences(
    req: PreferencesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    repo = PreferencesRepository(db)
    prefs = await repo.upsert(user_id, **update_data)
    return {
        "user_id": prefs.user_id,
        "notification_email": prefs.notification_email,
        "alert_threshold": prefs.alert_threshold,
        "quiet_hours_start": prefs.quiet_hours_start,
        "quiet_hours_end": prefs.quiet_hours_end,
        "theme": prefs.theme,
        "language": prefs.language,
        "extra": prefs.extra or {},
        "updated_at": prefs.updated_at.isoformat() if prefs.updated_at else None,
    }
