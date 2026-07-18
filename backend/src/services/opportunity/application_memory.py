"""Application Memory System.

Tracks job application status per user.
Prevents duplicate alerts for applied jobs.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jobs import Job, OpportunityNotification


class ApplicationStatus(str, Enum):
    NOT_APPLIED = "NOT_APPLIED"
    APPLIED = "APPLIED"
    INTERVIEWING = "INTERVIEWING"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


# Statuses that should suppress alerts
ALERT_SUPPRESSED_STATUSES = {
    ApplicationStatus.APPLIED,
    ApplicationStatus.INTERVIEWING,
    ApplicationStatus.OFFER,
}


class ApplicationMemoryService:
    """Track and manage job application status."""

    async def get_application_status(
        self,
        db: AsyncSession,
        user_id: str,
        job_id: int,
    ) -> ApplicationStatus:
        """Get application status for a user+job pair."""
        result = await db.execute(
            select(OpportunityNotification).where(
                OpportunityNotification.user_id == user_id,
                OpportunityNotification.job_id == job_id,
            )
        )
        notification = result.scalar_one_or_none()

        if not notification:
            return ApplicationStatus.NOT_APPLIED

        if notification.applied_at:
            # Check if there's interview/offer status in metadata
            metadata = notification.metadata_ or {}
            app_status = metadata.get("application_status")
            if app_status:
                try:
                    return ApplicationStatus(app_status)
                except ValueError:
                    pass
            return ApplicationStatus.APPLIED

        return ApplicationStatus.NOT_APPLIED

    async def update_application_status(
        self,
        db: AsyncSession,
        user_id: str,
        job_id: int,
        status: ApplicationStatus,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update application status for a user+job pair."""
        now = datetime.utcnow()

        # Get or create notification record
        result = await db.execute(
            select(OpportunityNotification).where(
                OpportunityNotification.user_id == user_id,
                OpportunityNotification.job_id == job_id,
            )
        )
        notification = result.scalar_one_or_none()

        if not notification:
            # Create new record
            notification = OpportunityNotification(
                user_id=user_id,
                job_id=job_id,
                channel="dashboard",
                status="active",
                metadata_={"application_status": status.value, "notes": notes, "updated_at": now.isoformat()},
            )
            if status == ApplicationStatus.APPLIED:
                notification.applied_at = now
            db.add(notification)
        else:
            # Update existing record
            metadata = notification.metadata_ or {}
            metadata["application_status"] = status.value
            metadata["notes"] = notes
            metadata["updated_at"] = now.isoformat()
            notification.metadata_ = metadata

            if status == ApplicationStatus.APPLIED:
                notification.applied_at = now

        # Also update Job lifecycle_state
        lifecycle_map = {
            ApplicationStatus.NOT_APPLIED: "NEW",
            ApplicationStatus.APPLIED: "APPLIED",
            ApplicationStatus.INTERVIEWING: "INTERVIEWING",
            ApplicationStatus.OFFER: "OFFERED",
            ApplicationStatus.REJECTED: "REJECTED",
            ApplicationStatus.WITHDRAWN: "WITHDRAWN",
        }

        await db.execute(
            update(Job).where(Job.id == job_id).values(
                lifecycle_state=lifecycle_map.get(status, "NEW"),
                updated_at=now,
            )
        )

        from src.services.opportunity.phase2_opportunity_intelligence import get_phase2_opportunity_intelligence_service
        await get_phase2_opportunity_intelligence_service().record_application_event(
            db,
            user_id,
            job_id,
            status.value,
            notes,
            {"source": "application_memory", "notification_id": notification.id if notification else None},
        )

        await db.commit()

        return {
            "user_id": user_id,
            "job_id": job_id,
            "status": status.value,
            "updated_at": now.isoformat(),
        }

    async def should_suppress_alert(
        self,
        db: AsyncSession,
        user_id: str,
        job_id: int,
    ) -> bool:
        """Check if alert should be suppressed for this user+job."""
        status = await self.get_application_status(db, user_id, job_id)
        return status in ALERT_SUPPRESSED_STATUSES

    async def get_user_applications(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all applications for a user."""
        result = await db.execute(
            select(OpportunityNotification, Job)
            .join(Job, OpportunityNotification.job_id == Job.id)
            .where(
                OpportunityNotification.user_id == user_id,
                OpportunityNotification.applied_at.is_not(None),
            )
        )
        rows = result.all()

        applications = []
        for notification, job in rows:
            metadata = notification.metadata_ or {}
            applications.append({
                "job_id": job.id,
                "job_title": job.title,
                "company": job.company,
                "applied_at": notification.applied_at.isoformat() if notification.applied_at else None,
                "status": metadata.get("application_status", "APPLIED"),
                "notes": metadata.get("notes"),
            })

        return applications


_application_memory: Optional[ApplicationMemoryService] = None


def get_application_memory() -> ApplicationMemoryService:
    global _application_memory
    if _application_memory is None:
        _application_memory = ApplicationMemoryService()
    return _application_memory
