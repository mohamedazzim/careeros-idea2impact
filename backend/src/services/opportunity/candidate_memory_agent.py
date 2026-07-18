"""Evidence-based concern extraction and candidate preference learning."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.outcome_intelligence import CandidateConcern, CandidatePreferenceMemory
from src.schemas.outcome_intelligence import OutcomeClassification
from src.services.opportunity.outcome_intelligence_agent import CONCERN_WORDS
from src.observability.langsmith import traceable


class CandidateMemoryAgent:
    @traceable(name="candidate_concern_extraction")
    async def extract_concerns(
        self, db: AsyncSession, *, candidate_id: str, conversation_id: str, transcript: str,
    ) -> list[CandidateConcern]:
        text = transcript.lower()
        rows = []
        for concern_type, keywords in CONCERN_WORDS.items():
            evidence = next((line.strip() for line in transcript.splitlines() if any(k in line.lower() for k in keywords)), None)
            if not evidence:
                continue
            existing = (await db.execute(select(CandidateConcern).where(
                CandidateConcern.conversation_id == conversation_id, CandidateConcern.concern_type == concern_type
            ))).scalar_one_or_none()
            if existing:
                rows.append(existing)
                continue
            row = CandidateConcern(candidate_id=candidate_id, conversation_id=conversation_id,
                                   concern_type=concern_type, confidence=0.75, evidence=evidence[:1000])
            db.add(row)
            rows.append(row)
        await db.flush()
        return rows

    @traceable(name="candidate_memory_update")
    async def update_memory(
        self, db: AsyncSession, *, candidate_id: str, conversation_id: str, transcript: str,
        outcome: OutcomeClassification, job_title: str, company: str,
    ) -> list[CandidatePreferenceMemory]:
        candidates = []
        text = transcript.lower()
        if outcome.outcome in {"APPLYING", "INTERESTED"}:
            candidates.extend([("PREFERRED_JOB_TITLE", job_title, outcome.summary), ("PREFERRED_COMPANY", company, outcome.summary)])
        mappings = {
            "REMOTE_PREFERENCE": ("REMOTE_PREFERENCE", "remote"),
            "HYBRID_PREFERENCE": ("REMOTE_PREFERENCE", "hybrid"),
            "RELOCATION_PREFERENCE": ("RELOCATION_PREFERENCE", "open_to_relocation"),
        }
        for needle, pref in mappings.items():
            if needle.lower().replace("_", " ") in text or pref[1].replace("_", " ") in text:
                candidates.append((pref[0], pref[1], f"Transcript evidence: {needle}"))
        rows = []
        for pref_type, value, evidence in candidates:
            existing = (await db.execute(select(CandidatePreferenceMemory).where(
                CandidatePreferenceMemory.candidate_id == candidate_id,
                CandidatePreferenceMemory.preference_type == pref_type,
                CandidatePreferenceMemory.preference_value == value,
            ))).scalar_one_or_none()
            if existing:
                if existing.source_conversation_id != conversation_id:
                    existing.confidence = min(1.0, existing.confidence + 0.1)
                    existing.evidence = evidence
                    existing.source_conversation_id = conversation_id
                rows.append(existing)
            else:
                row = CandidatePreferenceMemory(candidate_id=candidate_id, preference_type=pref_type,
                    preference_value=value, confidence=max(0.6, outcome.confidence), evidence=evidence,
                    source_conversation_id=conversation_id)
                db.add(row)
                rows.append(row)
        await db.flush()
        return rows


def get_candidate_memory_agent() -> CandidateMemoryAgent:
    return CandidateMemoryAgent()
