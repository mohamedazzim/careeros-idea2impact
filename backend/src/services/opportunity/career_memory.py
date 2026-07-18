"""RC3.1 Career Memory — Preference learning from real user actions.

Learns from: applied jobs, viewed jobs, voice session outcomes, notification interactions.
Never hallucinates preferences — only learns from actual user behavior.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jobs import (
    CareerMemory,
    Job,
    VoiceSession,
)

# Preference dimensions
PREF_ROLE = "preferred_roles"
PREF_DOMAIN = "preferred_domains"
PREF_LOCATION = "preferred_locations"
PREF_SALARY = "preferred_salary_bands"
PREF_NOTIFICATION_TIME = "preferred_notification_time"
PREF_CHANNEL = "preferred_channels"
PREF_COMPANY = "preferred_company_types"

ALL_PREFS = [
    PREF_ROLE, PREF_DOMAIN, PREF_LOCATION, PREF_SALARY,
    PREF_NOTIFICATION_TIME, PREF_CHANNEL, PREF_COMPANY,
]


class CareerMemoryService:
    async def learn_from_application(
        self, db: AsyncSession, *, user_id: str, job_id: int
    ) -> List[CareerMemory]:
        learned = []
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return learned

        if job.title:
            learned.append(await self._upsert_preference(
                db, user_id=user_id, dimension=PREF_ROLE,
                value=_extract_role_family(job.title),
                evidence=f"Applied to: {job.title}",
                source_table="application_timeline_events", source_id=str(job_id),
            ))
        if job.source_provider:
            learned.append(await self._upsert_preference(
                db, user_id=user_id, dimension=PREF_COMPANY,
                value=job.source_provider,
                evidence=f"Applied via provider: {job.source_provider}",
                source_table="application_timeline_events", source_id=str(job_id),
            ))
        if job.location:
            loc = _normalize_location(job.location)
            if loc:
                learned.append(await self._upsert_preference(
                    db, user_id=user_id, dimension=PREF_LOCATION,
                    value=loc,
                    evidence=f"Applied to location: {job.location}",
                    source_table="application_timeline_events", source_id=str(job_id),
                ))
        if job.salary_range:
            band = _normalize_salary_band(job.salary_range)
            if band:
                learned.append(await self._upsert_preference(
                    db, user_id=user_id, dimension=PREF_SALARY,
                    value=band,
                    evidence=f"Applied to salary range: {job.salary_range}",
                    source_table="application_timeline_events", source_id=str(job_id),
                ))
        return learned

    async def learn_from_voice_outcome(
        self, db: AsyncSession, *, user_id: str, voice_session_id: int, outcome: str
    ) -> List[CareerMemory]:
        learned = []
        if outcome not in ("USER_INTERESTED", "USER_NOT_INTERESTED"):
            return learned

        result = await db.execute(select(VoiceSession).where(VoiceSession.id == voice_session_id))
        session = result.scalar_one_or_none()
        if not session or not session.job_id:
            return learned

        job_result = await db.execute(select(Job).where(Job.id == session.job_id))
        job = job_result.scalar_one_or_none()
        if not job:
            return learned

        if outcome == "USER_INTERESTED":
            if job.title:
                learned.append(await self._upsert_preference(
                    db, user_id=user_id, dimension=PREF_ROLE,
                    value=_extract_role_family(job.title),
                    evidence=f"Expressed interest via voice: {job.title}",
                    source_table="voice_sessions", source_id=str(voice_session_id),
                ))
        elif outcome == "USER_NOT_INTERESTED":
            if job.title:
                learned.append(await self._negate_preference(
                    db, user_id=user_id, dimension=PREF_ROLE,
                    value=_extract_role_family(job.title),
                    evidence=f"Not interested via voice: {job.title}",
                    source_table="voice_sessions", source_id=str(voice_session_id),
                ))
        return learned

    async def learn_from_notification_interaction(
        self, db: AsyncSession, *, user_id: str, channel: str, opened: bool
    ) -> Optional[CareerMemory]:
        if opened:
            return await self._upsert_preference(
                db, user_id=user_id, dimension=PREF_CHANNEL,
                value=channel,
                evidence=f"Opened notification on {channel}",
                source_table="opportunity_outcome_events", source_id="interaction",
            )
        return None

    async def learn_from_voice_salary_inquiry(
        self, db: AsyncSession, *, user_id: str, salary_range: str
    ) -> Optional[CareerMemory]:
        band = _normalize_salary_band(salary_range)
        if not band:
            return None
        return await self._upsert_preference(
            db, user_id=user_id, dimension=PREF_SALARY,
            value=band,
            evidence=f"Asked about salary range via voice: {salary_range}",
            source_table="voice_sessions", source_id="voice_inquiry",
        )

    async def learn_preferred_notification_time(
        self, db: AsyncSession, *, user_id: str, hour_of_day: int
    ) -> Optional[CareerMemory]:
        time_label = _normalize_notification_time(hour_of_day)
        return await self._upsert_preference(
            db, user_id=user_id, dimension=PREF_NOTIFICATION_TIME,
            value=time_label,
            evidence=f"User active/engaged at hour {hour_of_day}",
            source_table="opportunity_outcome_events", source_id="timing",
        )

    async def get_preferences(
        self, db: AsyncSession, *, user_id: str
    ) -> Dict[str, Any]:
        result = await db.execute(
            select(CareerMemory)
            .where(
                CareerMemory.user_id == user_id,
                CareerMemory.event_type == "preference",
            )
            .order_by(desc(CareerMemory.created_at))
        )
        rows = result.scalars().all()
        prefs: Dict[str, Any] = {}
        for row in rows:
            dim = (row.data or {}).get("dimension")
            if dim and dim not in prefs:
                prefs[dim] = {
                    "value": row.title,
                    "confidence": (row.data or {}).get("confidence", 0.5),
                    "source": row.source_table,
                    "updated_at": row.created_at.isoformat() if row.created_at else None,
                }
        return prefs

    async def _upsert_preference(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        dimension: str,
        value: str,
        evidence: str,
        source_table: str,
        source_id: str,
    ) -> CareerMemory:
        existing_result = await db.execute(
            select(CareerMemory).where(
                CareerMemory.user_id == user_id,
                CareerMemory.event_type == "preference",
                CareerMemory.title == f"{dimension}:{value}",
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            data = existing.data or {}
            data["confidence"] = min(1.0, data.get("confidence", 0.5) + 0.1)
            data["evidence"] = evidence
            data["update_count"] = data.get("update_count", 0) + 1
            existing.data = data
            existing.created_at = __import__("datetime").datetime.utcnow()
            await db.flush()
            return existing

        memory = CareerMemory(
            user_id=user_id,
            event_type="preference",
            source_table=source_table,
            source_id=source_id,
            title=f"{dimension}:{value}",
            data={
                "dimension": dimension,
                "value": value,
                "confidence": 0.6,
                "evidence": evidence,
                "update_count": 1,
            },
        )
        db.add(memory)
        await db.flush()
        return memory

    async def _negate_preference(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        dimension: str,
        value: str,
        evidence: str,
        source_table: str,
        source_id: str,
    ) -> CareerMemory:
        memory = CareerMemory(
            user_id=user_id,
            event_type="preference_negative",
            source_table=source_table,
            source_id=source_id,
            title=f"{dimension}:{value}:negative",
            data={
                "dimension": dimension,
                "value": value,
                "confidence": 0.6,
                "evidence": evidence,
                "negation": True,
            },
        )
        db.add(memory)
        await db.flush()
        return memory


def _extract_role_family(title: str) -> str:
    title_lower = title.lower()
    families = {
        "engineer": ["engineer", "developer", "swe", "software"],
        "data": ["data", "analytics", "analyst", "ml", "machine learning"],
        "ai": ["ai", "artificial intelligence", "ml engineer", "deep learning"],
        "devops": ["devops", "sre", "infrastructure", "platform"],
        "product": ["product", "pm", "program manager"],
        "design": ["design", "ux", "ui", "figma"],
        "manager": ["manager", "director", "lead", "head"],
        "security": ["security", "cyber", "infosec"],
        "cloud": ["cloud", "aws", "azure", "gcp"],
    }
    for family, keywords in families.items():
        if any(kw in title_lower for kw in keywords):
            return family
    return title.split()[0].lower() if title else "unknown"


def _normalize_location(location: str) -> Optional[str]:
    location_lower = location.lower()
    if "remote" in location_lower:
        return "remote"
    if "hybrid" in location_lower:
        return "hybrid"
    if "onsite" in location_lower or "on-site" in location_lower or "on site" in location_lower:
        return "onsite"
    parts = [p.strip() for p in location.replace(",", " ").split()]
    if len(parts) >= 2:
        return parts[-1]
    return None


def _normalize_salary_band(salary_range: str) -> Optional[str]:
    import re
    numbers = re.findall(r"[\d,]+", salary_range.replace(",", ""))
    values = []
    for n in numbers:
        try:
            v = float(n.replace(",", ""))
            values.append(v)
        except ValueError:
            continue
    if not values:
        return None
    avg = sum(values) / len(values)
    if avg < 50000:
        return "under_50k"
    elif avg < 80000:
        return "50k_80k"
    elif avg < 120000:
        return "80k_120k"
    elif avg < 160000:
        return "120k_160k"
    elif avg < 200000:
        return "160k_200k"
    else:
        return "200k_plus"


def _normalize_notification_time(hour_of_day: int) -> str:
    if 6 <= hour_of_day < 9:
        return "early_morning"
    elif 9 <= hour_of_day < 12:
        return "morning"
    elif 12 <= hour_of_day < 14:
        return "midday"
    elif 14 <= hour_of_day < 17:
        return "afternoon"
    elif 17 <= hour_of_day < 20:
        return "evening"
    elif 20 <= hour_of_day < 23:
        return "night"
    else:
        return "late_night"


def get_career_memory_service() -> CareerMemoryService:
    return CareerMemoryService()
