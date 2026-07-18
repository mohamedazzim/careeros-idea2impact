"""API contracts for autonomous opportunity alert decisions."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class OpportunityAlertRequest(BaseModel):
    candidate_id: str = Field(..., min_length=1, max_length=128)
    phone_number: str = Field(..., min_length=7, max_length=32)
    job_title: str = Field(..., min_length=1, max_length=512)
    company: str = Field(..., min_length=1, max_length=256)
    match_score: float = Field(..., ge=0, le=100)
    salary_range: Optional[str] = Field(None, max_length=128)
    job_posted_at: datetime
    application_url: HttpUrl

    @field_validator("candidate_id", "phone_number", "job_title", "company")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class OpportunityAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: int
    action: str
    reason: str
    match_score: float
    hours_since_posted: float
    called: bool
    call_sid: Optional[str] = None
    webhook_status: Optional[str] = None
