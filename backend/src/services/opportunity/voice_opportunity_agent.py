"""RC3.1 Voice Opportunity Agent — Conversational Voice Session Lifecycle.

Converts CareerOS intelligence into delivery-ready speech.
Tracks full session lifecycle with conversation states.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jobs import (
    VoiceConversation,
    VoiceOutcome,
    VoiceSession,
)

VOICE_SESSION_STATES = {
    "PENDING", "INITIATED", "CONNECTED", "COMPLETED",
    "FAILED", "MISSED", "USER_INTERESTED", "USER_NOT_INTERESTED",
    "FOLLOW_UP_REQUIRED",
}

VOICE_TRANSITIONS = {
    "PENDING": {"INITIATED", "FAILED"},
    "INITIATED": {"CONNECTED", "MISSED", "FAILED"},
    "CONNECTED": {"COMPLETED", "USER_INTERESTED", "USER_NOT_INTERESTED", "FOLLOW_UP_REQUIRED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "MISSED": {"FOLLOW_UP_REQUIRED"},
    "USER_INTERESTED": {"FOLLOW_UP_REQUIRED"},
    "USER_NOT_INTERESTED": set(),
    "FOLLOW_UP_REQUIRED": {"INITIATED"},
}


class VoiceOpportunityAgent:
    LANGUAGE_ALIASES = {
        "ta": "tamil",
        "tam": "tamil",
        "tamil": "tamil",
        "தமிழ்": "tamil",
        "en": "english",
        "eng": "english",
        "english": "english",
        "en-us": "english",
        "en-gb": "english",
    }

    def _normalize_language(self, intelligence: Dict[str, Any]) -> str:
        raw = (
            intelligence.get("response_language")
            or intelligence.get("preferred_language")
            or intelligence.get("language")
            or intelligence.get("language_preferences", {}).get("preferred_language")
            or intelligence.get("language_preferences", {}).get("language_code")
            or "english"
        )
        raw_text = str(raw).strip().lower()
        if raw_text.startswith("ta"):
            return "tamil"
        if raw_text.startswith("en"):
            return "english"
        return self.LANGUAGE_ALIASES.get(raw_text, "english")

    def _is_tamil(self, intelligence: Dict[str, Any]) -> bool:
        return self._normalize_language(intelligence) == "tamil"

    @staticmethod
    def _join_nonempty(parts: List[str]) -> str:
        return " ".join(part.strip() for part in parts if part and part.strip())

    def build_script(self, intelligence: Dict[str, Any]) -> str:
        job = intelligence.get("job", {})
        match = intelligence.get("match_intelligence", {})
        urgency = intelligence.get("urgency_intelligence", {})
        salary = intelligence.get("salary_intelligence", {})
        deadline = intelligence.get("deadline_intelligence", {})
        skill_gap = intelligence.get("skill_gap_intelligence", {})
        missing = skill_gap.get("missing_skills") or match.get("missing_skills") or []
        language = self._normalize_language(intelligence)
        title = job.get("title", "this role")
        company = job.get("company", "the company")
        match_score = match.get("match_score", 0)

        if language == "tamil":
            parts = [
                "வணக்கம்! CareerOS-இல் இருந்து ஒரு தொழில்முறை வேலை வாய்ப்பு குறித்து அழைக்கிறேன்.",
                f"{company}-இல் உள்ள {title} பணி உங்கள் profile-க்கு {match_score} சதவீதம் பொருந்துகிறது.",
            ]
        else:
            parts = [
                "Hello! This is CareerOS calling about an opportunity that matches your profile.",
                f"{title} at {company} matches your career profile at {match_score} percent.",
            ]

        if urgency.get("deadline"):
            if language == "tamil":
                parts.append(f"காலக்கெடு தகவல்: {urgency.get('deadline')}.")
            else:
                parts.append(f"Deadline intelligence: {urgency.get('deadline')}.")
        elif urgency.get("application_urgency"):
            if language == "tamil":
                parts.append(f"விண்ணப்பத்தின் அவசர நிலை: {urgency.get('application_urgency', 'normal')}.")
            else:
                parts.append(f"Application urgency is {urgency.get('application_urgency', 'normal')}.")

        if salary.get("salary_range"):
            if language == "tamil":
                parts.append(f"சம்பள வரம்பு: {salary.get('salary_range')}.")
            else:
                parts.append(f"Salary signal: {salary.get('salary_range')}.")

        if deadline.get("deadline_source") and deadline.get("deadline_source") != "unknown":
            if language == "tamil":
                parts.append(
                    f"காலக்கெடு மூலம்: {deadline.get('deadline_source')} "
                    f"({deadline.get('deadline_confidence', 0):.0%} நம்பிக்கை)."
                )
            else:
                parts.append(f"Deadline source: {deadline.get('deadline_source')} with {deadline.get('deadline_confidence', 0):.0%} confidence.")

        if missing:
            missing_text = ", ".join(str(x) for x in missing[:3])
            if language == "tamil":
                parts.append(f"கற்றுக்கொள்ள வேண்டிய சில திறன்கள்: {missing_text}.")
                parts.append("இதற்கான ஒரு சிறிய செயல் திட்டத்தையும் நான் தெரிவிக்கலாம்.")
            else:
                parts.append(f"Skills to develop: {missing_text}.")
                parts.append("I can also help you focus on the fastest way to close those gaps.")

        if language == "tamil":
            if missing:
                parts.append("நீங்கள் விரும்பினால், salary, location, deadline அல்லது தேவையான skill gap details-ஐ மீண்டும் சொல்லலாம்.")
            else:
                parts.append("வேண்டுமெனில், salary, location, deadline அல்லது application guidance-ஐ மீண்டும் சொல்லலாம்.")
            parts.append("முழு விவரங்களும் CareerOS dashboard-இல் இருக்கும்.")
        else:
            if missing:
                parts.append("If you'd like, I can repeat the salary, location, deadline, or skill gap details.")
            else:
                parts.append("If you'd like, I can repeat the salary, location, deadline, or application details.")
            parts.append("The full breakdown will stay ready in your CareerOS dashboard.")
        return self._join_nonempty(parts)

    def build_follow_up_script(self, intelligence: Dict[str, Any], user_intent: str) -> str:
        match = intelligence.get("match_intelligence", {})
        job = intelligence.get("job", {})
        skill_gap = intelligence.get("skill_gap_intelligence", {})
        language = self._normalize_language(intelligence)
        title = job.get("title", "this role")
        company = job.get("company", "the company")
        matched_skills = match.get("matched_skills", [])[:5]
        gaps = skill_gap.get("missing_skills", [])[:5]

        if language == "tamil":
            if user_intent == "match_reasoning":
                strengths = ", ".join(str(s) for s in matched_skills) or "உங்கள் profile details"
                return self._join_nonempty([
                    f"இந்த {title} பணி {company}-இல் இருக்கிறது.",
                    f"உங்கள் {strengths} போன்ற skills இந்த வாய்ப்புடன் நன்றாக பொருந்துகிறது.",
                    "Salary, location, deadline அல்லது apply steps குறித்து மேலும் சொல்ல வேண்டுமா?",
                ])
            if user_intent == "application_guidance":
                return self._join_nonempty([
                    f"{title} at {company}-க்கு apply செய்ய CareerOS dashboard-இல் உள்ள direct link-ஐப் பயன்படுத்தலாம்.",
                    "நான் சுருக்கமாக அடுத்த படிகளைச் சொல்ல வேண்டுமா?",
                ])
            if user_intent == "skill_gaps":
                gap_text = ", ".join(str(g) for g in gaps) or "சில சிறிய skill gaps"
                return self._join_nonempty([
                    f"முக்கிய skill gaps: {gap_text}.",
                    "இதனை short courses அல்லது projects மூலம் விரைவில் close செய்யலாம்.",
                    "ஒரு action plan வேண்டுமா?",
                ])
            return self._join_nonempty([
                "இந்த வாய்ப்பில் matching details, application help, அல்லது skill gap summary-ஐ நான் சொல்லலாம்.",
                "எது வேண்டும் என்று சொல்லுங்கள்.",
            ])

        if user_intent == "match_reasoning":
            strengths = ", ".join(str(s) for s in matched_skills) or "your current profile"
            return self._join_nonempty([
                f"Here's why {title} at {company} matches:",
                f"your skills in {strengths} line up with the role requirements.",
                f"Your match score of {match.get('match_score', 0)} percent reflects this fit.",
                "Would you like salary, location, or deadline details next?",
            ])
        if user_intent == "application_guidance":
            return self._join_nonempty([
                f"To apply for {title} at {company}, use the CareerOS dashboard link.",
                "I can keep it brief or walk you through the next steps if you want.",
            ])
        if user_intent == "skill_gaps":
            gap_text = ", ".join(str(g) for g in gaps) or "a few small gaps"
            return self._join_nonempty([
                f"The main skill gaps are: {gap_text}.",
                "Targeted courses or a small project can close them quickly.",
                "Do you want me to repeat any part of this in Tamil or English?",
            ])
        return self._join_nonempty([
            "I can explain the match, application steps, or the skill gaps.",
            "Tell me what you want next, and I’ll keep it concise.",
        ])

    @staticmethod
    def _stringify_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, (list, tuple, set)):
            return ", ".join(str(item) for item in value if item is not None and str(item).strip())
        if isinstance(value, dict):
            pieces = []
            for key, item in value.items():
                if item is None:
                    continue
                text = str(item).strip()
                if text:
                    pieces.append(f"{key}: {text}")
            return ", ".join(pieces)
        return str(value).strip()

    def build_dynamic_variables(
        self,
        *,
        user_name: str = "",
        opportunity: Dict[str, Any],
        intelligence: Dict[str, Any],
    ) -> Dict[str, str]:
        job = intelligence.get("job", {})
        match = intelligence.get("match_intelligence", {})
        urgency = intelligence.get("urgency_intelligence", {})
        salary = intelligence.get("salary_intelligence", {})
        company_intelligence = intelligence.get("company_intelligence", {})
        application = intelligence.get("application_intelligence", {})
        resume = intelligence.get("resume_intelligence", {})

        dynamic_variables = {
            "user_name": user_name or opportunity.get("user_name") or "there",
            "job_title": self._stringify_value(job.get("title") or opportunity.get("title")),
            "company": self._stringify_value(job.get("company") or opportunity.get("company")),
            "company_description": self._stringify_value(company_intelligence.get("company_description") or opportunity.get("company_description")),
            "job_description": self._stringify_value(job.get("description") or opportunity.get("description")),
            "location": self._stringify_value(job.get("location") or opportunity.get("location")),
            "employment_type": self._stringify_value(job.get("employment_type") or opportunity.get("employment_type")),
            "experience_level": self._stringify_value(job.get("experience_level") or opportunity.get("experience_level")),
            "salary_range": self._stringify_value(salary.get("salary_range") or opportunity.get("salary_range")),
            "match_score": self._stringify_value(match.get("match_score") or opportunity.get("overall_score")),
            "matching_skills": self._stringify_value(match.get("matched_skills") or opportunity.get("matched_skills") or opportunity.get("skills_required")),
            "missing_skills": self._stringify_value(match.get("missing_skills") or opportunity.get("missing_skills") or opportunity.get("resume_gaps")),
            "recommended_skills": self._stringify_value(resume.get("interview_focus_areas") or opportunity.get("recommended_skills") or opportunity.get("interview_focus_areas")),
            "deadline": self._stringify_value(urgency.get("deadline") or application.get("deadline") or opportunity.get("deadline")),
            "application_url": self._stringify_value(application.get("application_url") or opportunity.get("apply_url") or opportunity.get("source_url")),
            "urgency_score": self._stringify_value(urgency.get("urgency_score") or opportunity.get("urgency_score")),
            "opportunity_priority_score": self._stringify_value(application.get("opportunity_priority_score") or opportunity.get("opportunity_priority_score")),
            "resume_strengths": self._stringify_value(resume.get("resume_strengths") or opportunity.get("resume_strengths") or opportunity.get("strengths")),
            "resume_gaps": self._stringify_value(resume.get("resume_gaps") or opportunity.get("resume_gaps") or opportunity.get("gaps")),
            "interview_focus_areas": self._stringify_value(resume.get("interview_focus_areas") or opportunity.get("interview_focus_areas")),
        }
        return dynamic_variables

    def build_conversation_prompt(self) -> str:
        return (
            "You are Alex, a CareerOS opportunity advisor.\n\n"
            "You are calling the user about one specific job opportunity.\n"
            "Start with a short intro: role, company, and why it matches.\n\n"
            "Then ask one question and wait for the user.\n\n"
            "You must listen to the user’s reply.\n"
            "If the user asks about salary, location, skills, experience, deadline, company, apply link, or match reason, answer using the dynamic variables.\n"
            "If information is missing, say that it is not available yet and offer to send it later.\n"
            "Do not end the call immediately after the first message.\n"
            "Only end the call when:\n"
            "- user says they are not interested,\n"
            "- user says goodbye,\n"
            "- user asks to stop calling,\n"
            "- max duration is reached,\n"
            "- repeated silence timeout is reached.\n\n"
            "If user is interested, ask whether they want:\n"
            "- apply link sent,\n"
            "- follow-up call,\n"
            "- save opportunity,\n"
            "- mark as interested.\n\n"
            "Keep responses short and conversational."
        )

    def build_conversation_first_message(self, dynamic_variables: Dict[str, str]) -> str:
        title = dynamic_variables.get("job_title") or "this role"
        company = dynamic_variables.get("company") or "the company"
        match_score = dynamic_variables.get("match_score") or "a strong"
        return (
            f"Hi, this is Alex from CareerOS. I'm calling about the {title} opportunity at {company} "
            f"because it looks like a {match_score} match for you. Do you have a minute for a quick overview?"
        )

    async def start_session(
        self,
        db: AsyncSession,
        *,
        communication_request_id: int,
        user_id: str,
        job_id: int | None,
        intelligence: Dict[str, Any],
        mode: str = "notification_tts",
        provider: str = "elevenlabs",
        conversation_id: str | None = None,
        call_sid: str | None = None,
        agent_id: str | None = None,
        agent_phone_number_id: str | None = None,
        dynamic_variables: Optional[Dict[str, Any]] = None,
        prompt: str | None = None,
        first_message: str | None = None,
    ) -> tuple[VoiceSession, str]:
        mode = (mode or "notification_tts").lower()
        if mode != "conversation_agent":
            raise ValueError("Opportunity calls must use conversation_agent mode")
        script = self.build_script(intelligence) if mode == "notification_tts" else (first_message or "")
        payload_metadata = {
            "mode": mode,
            "provider": provider,
            "call_sid": call_sid,
            "conversation_id": conversation_id,
            "agent_id": agent_id,
            "agent_phone_number_id": agent_phone_number_id,
            "dynamic_variables": dynamic_variables or {},
            "prompt": prompt,
            "first_message": first_message,
            "role": "conversational" if mode == "conversation_agent" else "notification_tts",
            "does_matching": False,
            "does_scoring": False,
            "transcript_summary": "",
            "extracted_user_intent": None,
            "response_language": self._normalize_language(intelligence),
            "extracted_objections": [],
            "follow_up_recommendations": [],
            "transcript_status": "pending",
        }
        session = VoiceSession(
            communication_request_id=communication_request_id,
            user_id=user_id,
            job_id=job_id,
            status="STARTED",
            voice_provider=provider,
            voice_metadata=payload_metadata,
        )
        db.add(session)
        await db.flush()

        if script:
            db.add(VoiceConversation(
                voice_session_id=session.id,
                role="agent",
                content=script,
                intelligence_snapshot={
                    "match_score": intelligence.get("match_intelligence", {}).get("match_score"),
                    "missing_skills": intelligence.get("skill_gap_intelligence", {}).get("missing_skills", []),
                    "response_language": self._normalize_language(intelligence),
                    "mode": mode,
                },
            ))
            await db.flush()
        return session, script

    def can_transition(self, current: str, target: str) -> bool:
        return target in VOICE_TRANSITIONS.get(current, set())

    async def transition_session(
        self,
        db: AsyncSession,
        *,
        voice_session_id: int,
        target_state: str,
        metadata_update: Optional[Dict[str, Any]] = None,
    ) -> VoiceSession:
        result = await db.execute(select(VoiceSession).where(VoiceSession.id == voice_session_id))
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Voice session {voice_session_id} not found")
        if not self.can_transition(session.status, target_state):
            raise ValueError(f"Invalid transition: {session.status} -> {target_state}")

        session.status = target_state
        session.updated_at = datetime.utcnow()
        if metadata_update:
            existing = session.voice_metadata or {}
            existing.update(metadata_update)
            session.voice_metadata = existing

        await db.flush()
        return session

    async def add_conversation_turn(
        self,
        db: AsyncSession,
        *,
        voice_session_id: int,
        role: str,
        content: str,
        intelligence_snapshot: Optional[Dict[str, Any]] = None,
    ) -> VoiceConversation:
        turn = VoiceConversation(
            voice_session_id=voice_session_id,
            role=role,
            content=content,
            intelligence_snapshot=intelligence_snapshot,
        )
        db.add(turn)
        await db.flush()
        return turn

    async def record_outcome(
        self,
        db: AsyncSession,
        *,
        voice_session_id: int,
        outcome: str,
        provider_status: str | None,
        call_sid: str | None,
        data: Dict[str, Any],
    ) -> VoiceOutcome:
        entry = VoiceOutcome(
            voice_session_id=voice_session_id,
            outcome=outcome,
            provider_status=provider_status,
            call_sid=call_sid,
            data=data,
        )
        db.add(entry)

        session = await self.get_session(db, voice_session_id)
        if session:
            turns = await self.get_session_conversations(db, voice_session_id)
            intelligence = self._extract_session_intelligence(turns, outcome, data)
            meta = session.voice_metadata or {}
            meta["transcript_summary"] = intelligence["transcript_summary"]
            meta["extracted_user_intent"] = intelligence["user_intent"]
            meta["extracted_objections"] = intelligence["objections"]
            meta["follow_up_recommendations"] = intelligence["follow_ups"]
            session.voice_metadata = meta

        await db.flush()
        return entry

    def _extract_session_intelligence(
        self,
        turns: list,
        outcome: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        user_turns = [t.content for t in turns if t.role == "user"]
        agent_turns = [t.content for t in turns if t.role == "agent"]
        language = "english"

        transcript_parts = []
        for t in turns:
            prefix = "User" if t.role == "user" else "Agent"
            transcript_parts.append(f"{prefix}: {t.content[:200]}")
        transcript_summary = " | ".join(transcript_parts[-6:]) if transcript_parts else ""

        user_intent = "unknown"
        if user_turns:
            combined = " ".join(user_turns).lower()
            if any(w in combined for w in ["interested", "yes", "apply", "let's go", "sounds good", "ஆம்", "சரி", "okay", "ok"]):
                user_intent = "interested"
            elif any(w in combined for w in ["not interested", "no thanks", "skip", "pass", "not now", "வேண்டாம்", "இல்லை"]):
                user_intent = "not_interested"
            elif any(w in combined for w in ["tell me more", "explain", "details", "what about", "more details", "மேலும்", "சொல்லு", "விவரம்"]):
                user_intent = "requesting_info"
            elif any(w in combined for w in ["skill", "gap", "missing", "learn", "course", "திறன்", "skills", "skill gap"]):
                user_intent = "skill_gap_inquiry"
            elif any(w in combined for w in ["salary", "pay", "compensation", "range", "சம்பளம்", "pay scale"]):
                user_intent = "salary_inquiry"
            elif any(w in combined for w in ["deadline", "when", "hurry", "urgent", "இறுதி", "காலக்கெடு"]):
                user_intent = "deadline_inquiry"
            elif any(w in combined for w in ["tamil", "தமிழ்", "தமிழில்", "in tamil", "say in tamil"]):
                user_intent = "language_request"
                language = "tamil"
            elif any(w in combined for w in ["english", "in english", "say in english"]):
                user_intent = "language_request"
                language = "english"

        objections = []
        if user_turns:
            combined = " ".join(user_turns).lower()
            if "location" in combined and ("far" in combined or "wrong" in combined or "not" in combined):
                objections.append("location_concern")
            if "salary" in combined and ("low" in combined or "too little" in combined or "not enough" in combined):
                objections.append("salary_concern")
            if "skill" in combined and ("don't have" in combined or "missing" in combined or "can't" in combined):
                objections.append("skill_gap_concern")
            if "remote" in combined and ("need" in combined or "want" in combined):
                objections.append("remote_preference")
            if "not ready" in combined or "too early" in combined:
                objections.append("timing_concern")
            if "tamil" in combined or "தமிழ்" in combined:
                objections.append("language_request_tamil")
                language = "tamil"

        follow_ups = []
        if outcome in ("USER_INTERESTED", "CONNECTED", "COMPLETED"):
            follow_ups.append("send_application_guidance")
            if "skill_gap_concern" in objections or "salary_inquiry" in [ui for ui in [user_intent]]:
                follow_ups.append("prepare_skill_development_plan")
        elif outcome == "USER_NOT_INTERESTED":
            follow_ups.append("update_career_memory_negative")
        elif outcome == "MISSED":
            follow_ups.append("retry_call_later")
        elif outcome == "FOLLOW_UP_REQUIRED":
            follow_ups.append("schedule_follow_up")
            if "salary_inquiry" == user_intent:
                follow_ups.append("send_salary_intelligence_report")
        if not follow_ups:
            follow_ups.append("no_action_required")

        return {
            "transcript_summary": transcript_summary,
            "user_intent": user_intent,
            "response_language": language,
            "objections": objections,
            "follow_ups": follow_ups,
        }

    async def get_session(self, db: AsyncSession, voice_session_id: int) -> Optional[VoiceSession]:
        result = await db.execute(select(VoiceSession).where(VoiceSession.id == voice_session_id))
        return result.scalar_one_or_none()

    async def get_user_sessions(
        self, db: AsyncSession, user_id: str, limit: int = 20
    ) -> List[VoiceSession]:
        result = await db.execute(
            select(VoiceSession)
            .where(VoiceSession.user_id == user_id)
            .order_by(VoiceSession.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_session_conversations(
        self, db: AsyncSession, voice_session_id: int
    ) -> List[VoiceConversation]:
        result = await db.execute(
            select(VoiceConversation)
            .where(VoiceConversation.voice_session_id == voice_session_id)
            .order_by(VoiceConversation.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_session_outcomes(
        self, db: AsyncSession, voice_session_id: int
    ) -> List[VoiceOutcome]:
        result = await db.execute(
            select(VoiceOutcome)
            .where(VoiceOutcome.voice_session_id == voice_session_id)
            .order_by(VoiceOutcome.created_at.asc())
        )
        return list(result.scalars().all())


def get_voice_opportunity_agent() -> VoiceOpportunityAgent:
    return VoiceOpportunityAgent()
