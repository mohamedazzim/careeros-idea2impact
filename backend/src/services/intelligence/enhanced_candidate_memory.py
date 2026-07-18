"""Enhanced candidate memory extraction with expanded preference learning."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.outcome_intelligence import (
    CandidatePreferenceMemory,
    CandidatePreferenceHistory,
)
from src.observability.langsmith import traceable


# Expanded keyword patterns for preference extraction
LOCATION_PATTERNS = {
    "remote": ["remote", "work from home", "wfh", "work remotely"],
    "bangalore": ["bangalore", "bengaluru"],
    "mumbai": ["mumbai", "bombay"],
    "delhi": ["delhi", "noida", "gurgaon", "gurugram"],
    "hyderabad": ["hyderabad"],
    "chennai": ["chennai"],
    "pune": ["pune"],
    "hybrid": ["hybrid", "partially remote", "flexible location"],
    "onsite": ["onsite", "on-site", "in-office", "in office"],
}

SALARY_PATTERNS = {
    "20+ LPA": [r"20\+?\s*lpa", r"20\s*lakh", r"20,00,000"],
    "15-20 LPA": [r"1[5-9]\s*lpa", r"15\s*to\s*20", r"15-20\s*lpa"],
    "10-15 LPA": [r"1[0-4]\s*lpa", r"10\s*to\s*15", r"10-15\s*lpa"],
    "100k+ USD": [r"100k\+?", r"100,000\+?", r"\$100k", r"100k\s*usd"],
    "150k+ USD": [r"150k\+?", r"150,000\+?"],
    "50-100k USD": [r"[5-9]0k", r"50\s*to\s*100k"],
}

ROLE_PATTERNS = {
    "ai_engineering": ["ai engineer", "artificial intelligence", "machine learning engineer", "ml engineer", "deep learning"],
    "software_engineering": ["software engineer", "swe", "developer", "full stack", "fullstack", "backend engineer", "frontend engineer"],
    "data_science": ["data scientist", "data analyst", "analytics", "data engineer"],
    "devops": ["devops", "sre", "site reliability", "platform engineer", "infrastructure"],
    "product": ["product manager", "pm", "program manager"],
    "design": ["ux designer", "ui designer", "product designer", "graphic designer"],
}

COMPANY_PATTERNS = {
    "startup": ["startup", "early stage", "series a", "series b", "seed round"],
    "big_tech": ["faang", "big tech", "google", "meta", "amazon", "microsoft", "apple"],
    "enterprise": ["enterprise", "fortune 500", "large company", "corporation"],
    "remote_first": ["remote first", "remote-first", "distributed"],
}


class EnhancedCandidateMemoryAgent:
    """Enhanced agent that extracts richer preference signals from transcripts."""

    @traceable(name="enhanced_memory_extract_preferences")
    async def extract_preferences_from_transcript(
        self,
        db: AsyncSession,
        *,
        candidate_id: str,
        conversation_id: str,
        transcript: str,
        job_title: str = "",
        company: str = "",
    ) -> list[dict]:
        text = transcript.lower()
        extracted = []

        for pref_type, patterns in LOCATION_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    evidence = self._find_evidence_line(transcript, pattern)
                    extracted.append({
                        "preference_type": "PREFERRED_LOCATION",
                        "preference_value": pref_type,
                        "confidence": 0.7,
                        "evidence": evidence or f"Transcript mentions: {pattern}",
                        "source": "transcript",
                    })
                    break

        for pref_type, patterns in SALARY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    evidence = self._find_evidence_line(transcript, pref_type.split()[0])
                    extracted.append({
                        "preference_type": "PREFERRED_SALARY",
                        "preference_value": pref_type,
                        "confidence": 0.7,
                        "evidence": evidence or f"Transcript mentions salary: {pattern}",
                        "source": "transcript",
                    })
                    break

        for pref_type, patterns in ROLE_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    evidence = self._find_evidence_line(transcript, pattern)
                    extracted.append({
                        "preference_type": "PREFERRED_ROLE",
                        "preference_value": pref_type,
                        "confidence": 0.75,
                        "evidence": evidence or f"Transcript mentions role: {pattern}",
                        "source": "transcript",
                    })
                    break

        for pref_type, patterns in COMPANY_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    evidence = self._find_evidence_line(transcript, pattern)
                    extracted.append({
                        "preference_type": "PREFERRED_COMPANY_TYPE",
                        "preference_value": pref_type,
                        "confidence": 0.65,
                        "evidence": evidence or f"Transcript mentions: {pattern}",
                        "source": "transcript",
                    })
                    break

        for needle, pref in [("remote", ("REMOTE_PREFERENCE", "remote")), ("hybrid", ("REMOTE_PREFERENCE", "hybrid")),
                              ("relocation", ("RELOCATION_PREFERENCE", "open_to_relocation"))]:
            if needle in text:
                extracted.append({
                    "preference_type": pref[0],
                    "preference_value": pref[1],
                    "confidence": 0.7,
                    "evidence": f"Transcript mentions: {needle}",
                    "source": "transcript",
                })

        seen = set()
        unique = []
        for e in extracted:
            key = (e["preference_type"], e["preference_value"])
            if key not in seen:
                seen.add(key)
                unique.append(e)

        persisted = []
        for pref in unique:
            result = await self._upsert_preference(
                db, candidate_id=candidate_id, conversation_id=conversation_id, **pref
            )
            persisted.append(result)
        await db.flush()
        return persisted

    async def _upsert_preference(
        self,
        db: AsyncSession,
        *,
        candidate_id: str,
        conversation_id: str,
        preference_type: str,
        preference_value: str,
        confidence: float,
        evidence: str,
        source: str,
    ) -> dict:
        existing = (await db.execute(select(CandidatePreferenceMemory).where(
            CandidatePreferenceMemory.candidate_id == candidate_id,
            CandidatePreferenceMemory.preference_type == preference_type,
            CandidatePreferenceMemory.preference_value == preference_value,
        ))).scalar_one_or_none()

        if existing:
            if existing.source_conversation_id != conversation_id:
                existing.confidence = min(1.0, existing.confidence + 0.1)
                existing.evidence = evidence
                existing.source_conversation_id = conversation_id
                action = "increased"
            else:
                action = "unchanged"
        else:
            existing = CandidatePreferenceMemory(
                candidate_id=candidate_id,
                preference_type=preference_type,
                preference_value=preference_value,
                confidence=max(0.6, confidence),
                evidence=evidence,
                source_conversation_id=conversation_id,
            )
            db.add(existing)
            action = "created"

        history = CandidatePreferenceHistory(
            candidate_id=candidate_id,
            preference_type=preference_type,
            preference_value=preference_value,
            confidence=confidence,
            evidence=evidence,
            source_conversation_id=conversation_id,
            action=action,
        )
        db.add(history)

        return {
            "preference_type": preference_type,
            "preference_value": preference_value,
            "confidence": existing.confidence,
            "action": action,
        }

    def _find_evidence_line(self, transcript: str, needle: str) -> str | None:
        for line in transcript.splitlines():
            if needle.lower() in line.lower():
                return line.strip()[:500]
        return None


def get_enhanced_candidate_memory_agent() -> EnhancedCandidateMemoryAgent:
    return EnhancedCandidateMemoryAgent()
