"""Phase 2 outcome intelligence API and agent schemas."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

Outcome = Literal["APPLYING", "INTERESTED", "MAYBE_LATER", "NOT_INTERESTED", "NOT_QUALIFIED", "REQUEST_FOLLOWUP"]


class OutcomeClassification(BaseModel):
    outcome: Outcome
    interest_level: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    primary_concern: Optional[str] = None
    followup_required: bool = False
    summary: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)


class ProcessConversationRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=128)
