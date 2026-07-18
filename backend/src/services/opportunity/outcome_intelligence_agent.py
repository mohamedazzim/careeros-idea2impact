"""Structured post-call outcome classification."""

from __future__ import annotations

import asyncio

from src.schemas.outcome_intelligence import OutcomeClassification
from src.services.llm import get_reasoning_provider as get_llm_provider


class OutcomeIntelligenceAgent:
    async def classify(self, transcript: str) -> OutcomeClassification:
        provider = get_llm_provider()
        try:
            response = await asyncio.wait_for(
                provider.structured_generate(
                    system_prompt=(
                        "Classify a CareerOS opportunity call transcript. Return only JSON matching the requested schema. "
                        "Allowed outcomes: APPLYING, INTERESTED, MAYBE_LATER, NOT_INTERESTED, NOT_QUALIFIED, REQUEST_FOLLOWUP. "
                        "Ground every result in the transcript and do not invent facts."
                    ),
                    user_message=transcript[:18000],
                    output_schema=OutcomeClassification,
                    max_tokens=800,
                    temperature=0.0,
                    cache_key_hint="opportunity_call_outcome",
                ),
                timeout=20.0,
            )
            parsed = response.get("parsed")
            if parsed:
                return parsed
        except Exception:
            pass
        return self._deterministic_fallback(transcript)

    @staticmethod
    def _deterministic_fallback(transcript: str) -> OutcomeClassification:
        text = transcript.lower()
        if any(x in text for x in ("i will apply", "i'm applying", "send the application", "apply now")):
            outcome, interest, followup = "APPLYING", "HIGH", False
        elif any(x in text for x in ("not interested", "no thanks", "do not call")):
            outcome, interest, followup = "NOT_INTERESTED", "LOW", False
        elif any(x in text for x in ("call me later", "follow up", "another time")):
            outcome, interest, followup = "REQUEST_FOLLOWUP", "MEDIUM", True
        elif any(x in text for x in ("interested", "sounds good", "tell me more")):
            outcome, interest, followup = "INTERESTED", "HIGH", True
        else:
            outcome, interest, followup = "MAYBE_LATER", "UNKNOWN", False
        concern = next((name for name, words in CONCERN_WORDS.items() if any(w in text for w in words)), None)
        return OutcomeClassification(
            outcome=outcome, interest_level=interest, primary_concern=concern,
            followup_required=followup, summary="Deterministic transcript classification fallback.", confidence=0.55,
        )


CONCERN_WORDS = {
    "SALARY_CONCERN": ("salary", "compensation", "pay"),
    "LOCATION_CONCERN": ("location", "relocate", "commute"),
    "EXPERIENCE_CONCERN": ("experience", "years required"),
    "TECHNOLOGY_CONCERN": ("technology", "tech stack", "framework"),
    "TIMING_CONCERN": ("timing", "notice period", "immediate"),
    "WORK_AUTHORIZATION_CONCERN": ("visa", "work authorization", "sponsorship"),
    "REMOTE_PREFERENCE": ("remote", "work from home"),
    "HYBRID_PREFERENCE": ("hybrid",),
}


def get_outcome_intelligence_agent() -> OutcomeIntelligenceAgent:
    return OutcomeIntelligenceAgent()
