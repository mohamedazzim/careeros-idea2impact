"""Authenticated endpoint for autonomous opportunity alert decisions."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.session import get_db
from src.schemas.opportunity_alert import OpportunityAlertRequest, OpportunityAlertResponse
from src.services.opportunity_alert_agent import get_opportunity_alert_agent_service

router = APIRouter(tags=["Opportunity Alert Agent"])
logger = logging.getLogger(__name__)


@router.post("/opportunity-alert", response_model=OpportunityAlertResponse)
async def evaluate_opportunity_alert(
    request: OpportunityAlertRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OpportunityAlertResponse:
    if request.candidate_id != user["sub"]:
        raise HTTPException(status_code=403, detail="candidate_id must match the authenticated user")
    try:
        return await get_opportunity_alert_agent_service().evaluate(request, db)
    except Exception as exc:
        await db.rollback()
        logger.exception(
            "Opportunity alert evaluation failed",
            extra={"operation": "opportunity_alert_decision", "candidate_id": request.candidate_id},
        )
        raise HTTPException(status_code=503, detail="Opportunity alert evaluation failed") from exc
