"""Phase 7 — Live AI Interview Orchestrator.

Real-time interview engine that coordinates:
- speech-to-text → AI reasoning → text-to-speech pipeline
- dynamic question generation with resume awareness
- real-time rubric evaluation
- interruption handling
- WebSocket event streaming
- interview memory persistence

Built on top of existing interview services (evaluation, rubric, governance, etc.)
"""

import uuid
import time
import json
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

from src.interview_runtime import (
    InterviewStage, InterviewState, get_interview_state_machine,
)

logger = logging.getLogger(__name__)


@dataclass
class LiveInterviewSession:
    session_uid: str
    user_id: str
    interview_type: str
    state: InterviewState
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    evaluations: List[Dict[str, Any]] = field(default_factory=list)
    audio_context: List[bytes] = field(default_factory=list)
    active: bool = True
    created_at: float = field(default_factory=time.time)


class InterviewMode(Enum):
    HR = "hr"
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    SYSTEM_DESIGN = "system_design"
    CODING = "coding"
    STRESS = "stress"
    FAANG = "faang"
    MOCK_RECRUITER = "mock_recruiter"


QUESTION_TEMPLATES = {
    InterviewMode.HR: [
        "Tell me about yourself and your background.",
        "Why are you interested in this role?",
        "Where do you see yourself in 5 years?",
        "What are your salary expectations?",
        "Why should we hire you?",
    ],
    InterviewMode.BEHAVIORAL: [
        "Tell me about a time you had to resolve a conflict with a coworker.",
        "Describe a project where you had to meet a tight deadline.",
        "Give me an example of a time you showed leadership.",
        "Tell me about a failure and what you learned from it.",
        "How do you handle receiving critical feedback?",
    ],
    InterviewMode.TECHNICAL: [
        "Explain the difference between a process and a thread.",
        "What is the CAP theorem and why is it important?",
        "How would you design a distributed rate limiter?",
        "Explain event sourcing and CQRS.",
        "What are the trade-offs between monolithic and microservice architectures?",
    ],
    InterviewMode.SYSTEM_DESIGN: [
        "Design a real-time chat application like Slack.",
        "Design a URL shortener like bit.ly.",
        "Design a ride-sharing service like Uber.",
        "Design a social media news feed.",
        "Design a distributed job scheduler.",
    ],
    InterviewMode.CODING: [
        "Implement a LRU cache with O(1) get and put.",
        "Design a rate limiter.",
        "Implement a task scheduler with dependencies.",
        "Build a key-value store with TTL support.",
        "Implement a concurrent message queue.",
    ],
    InterviewMode.STRESS: [
        "Why should we hire you over someone with more experience?",
        "What is your biggest professional weakness?",
        "Tell me about a time you completely failed at something important.",
        "How do you handle working under extreme pressure?",
        "What do you think you could have done better in your last role?",
    ],
    InterviewMode.FAANG: [
        "Design a distributed key-value store with strong consistency.",
        "How would you scale a system to handle 1 billion daily active users?",
        "Implement a concurrent least-recently-used cache.",
        "Explain how you would debug a 10x latency regression in a microservice.",
        "How would you reduce cloud infrastructure costs by 50% without affecting reliability?",
    ],
    InterviewMode.MOCK_RECRUITER: [
        "Walk me through your resume and highlight your most relevant experience.",
        "What attracted you to this company?",
        "Tell me about your compensation expectations and timeline.",
        "Are you actively interviewing elsewhere? How do we stack up?",
        "What questions do you have for me about the role?",
    ],
}


class LiveInterviewOrchestrator:
    """Orchestrates live AI interview sessions end-to-end."""

    def __init__(self):
        self.sm = get_interview_state_machine()
        self._sessions: Dict[str, LiveInterviewSession] = {}
        self._evaluation_semaphore = asyncio.Semaphore(5)
        self._lock = asyncio.Lock()
        self._stt_ready = False

    async def _ensure_stt(self):
        if self._stt_ready:
            return
        try:
            from src.services.realtime_stt import get_stt_orchestrator, STTProvider
            stt = get_stt_orchestrator()
            await stt.start(STTProvider.DEEPGRAM)
            self._stt_ready = True
        except Exception:
            pass

    async def create_session(self, user_id: str, interview_type: str,
                              resume_context: Optional[Dict[str, Any]] = None,
                              mode: str = "voice") -> LiveInterviewSession:
        """Create and initialize a new interview session backed by LangGraph InterviewGraph."""
        session_uid = str(uuid.uuid4())
        interview_state = self.sm.create_session(
            session_uid=session_uid,
            interview_type=interview_type,
            total_questions=5,
            mode=mode,
            metadata={"resume_context": resume_context or {}, "user_id": user_id},
        )
        session = LiveInterviewSession(
            session_uid=session_uid,
            user_id=user_id,
            interview_type=interview_type,
            state=interview_state,
        )
        async with self._lock:
            self._sessions[session_uid] = session

        # Initialize InterviewGraph for authoritative state tracking
        try:
            from src.graphs.interview_graph import get_interview_graph
            graph = get_interview_graph()
            initial_state = {
                "session_uid": session_uid,
                "user_id": user_id,
                "interview_type": interview_type,
                "question_index": 0,
                "total_questions": 5,
                "scores": [],
                "follow_up_depth": 0,
                "completed": False,
            }
            await graph.ainvoke(initial_state, config={"configurable": {"thread_id": session_uid}})
        except Exception as e:
            logger.warning(f"InterviewGraph init skipped: {e}")

        await self._broadcast_event(session_uid, "interview_created", {
            "session_uid": session_uid,
            "interview_type": interview_type,
            "mode": mode,
        })
        self.sm.transition(session_uid, InterviewStage.WELCOME)
        return session

    async def start_interview(self, session_uid: str) -> Optional[str]:
        """Start the interview flow — deliver first question."""
        session = self._sessions.get(session_uid)
        if not session:
            return None

        welcome_message = f"Welcome to your {session.interview_type} interview. I'll be your AI interviewer today. Let's begin."
        self.sm.transition(session_uid, InterviewStage.INTRO)
        await self._broadcast_event(session_uid, "AI_SPEAKING", {
            "message": welcome_message, "stage": "intro",
        })

        question = await self._generate_question(session)
        if question:
            self.sm.transition(session_uid, InterviewStage.QUESTION_DELIVERY)
            session.state.current_question = question
            await self._broadcast_event(session_uid, "QUESTION_DELIVERED", {
                "question": question,
                "index": session.state.current_question_index,
                "total": session.state.total_questions,
            })
        return question

    async def process_user_response(
        self, session_uid: str, transcript: str = "", audio_bytes: bytes = None
    ) -> Dict[str, Any]:
        """Process a user's spoken/written response.

        Accepts either a pre-transcribed text (transcript) or raw audio bytes
        for real-time STT integration via Deepgram/Whisper.
        """
        session = self._sessions.get(session_uid)
        if not session:
            return {"status": "error", "reason": "session_not_found"}

        # Audio path: run STT if raw bytes provided
        if audio_bytes and not transcript:
            try:
                from src.services.realtime_stt import get_stt_orchestrator
                stt = get_stt_orchestrator()
                stt.on_transcript(lambda r: self._on_stt_partial(session, r))
                await stt.send_audio(audio_bytes, session_uid)
                transcript = "[transcribing]"
            except Exception:
                pass

        session.state.last_user_transcript = transcript
        session.transcript.append({
            "speaker": "user",
            "text": transcript,
            "timestamp": time.time(),
            "question_index": session.state.current_question_index,
        })

        self.sm.transition(session_uid, InterviewStage.USER_SPEAKING)
        self.sm.transition(session_uid, InterviewStage.AI_THINKING)
        await self._broadcast_event(session_uid, "AI_THINKING", {
            "message": "Let me evaluate your response...",
        })

        evaluation = await self._evaluate_response(session, transcript)
        session.evaluations.append(evaluation)
        session.state.scores.append(evaluation.get("overall_score", 0.0))

        # Stream live feedback
        strengths = evaluation.get("strengths", [])
        improvements = evaluation.get("improvements", [])
        if strengths or improvements:
            await self._broadcast_event(session_uid, "FEEDBACK_UPDATE", {
                "strengths": strengths[:3],
                "improvements": improvements[:3],
                "overall_score": evaluation.get("overall_score", 0),
                "dimension_scores": evaluation.get("dimension_scores", {}),
            })

        should_follow_up = evaluation.get("should_follow_up", False) and \
            session.state.follow_up_depth < session.state.max_follow_ups

        if should_follow_up:
            self.sm.transition(session_uid, InterviewStage.FOLLOW_UP)
            follow_up = evaluation.get("follow_up_question", "")
            session.state.follow_up_depth += 1
            session.state.last_ai_response = follow_up
            await self._broadcast_event(session_uid, "AI_SPEAKING", {
                "message": follow_up, "stage": "follow_up", "follow_up_depth": session.state.follow_up_depth,
            })
            return {"status": "follow_up", "question": follow_up, "evaluation": evaluation}
        else:
            session.state.follow_up_depth = 0
            self.sm.transition(session_uid, InterviewStage.EVALUATION)
            session.state.current_question_index += 1

            if session.state.current_question_index >= session.state.total_questions:
                return await self._close_interview(session)

            self.sm.transition(session_uid, InterviewStage.TRANSITIONING)
            next_question = await self._generate_question(session)
            self.sm.transition(session_uid, InterviewStage.QUESTION_DELIVERY)
            session.state.current_question = next_question
            await self._broadcast_event(session_uid, "QUESTION_DELIVERED", {
                "question": next_question,
                "index": session.state.current_question_index,
                "total": session.state.total_questions,
                "score": evaluation.get("overall_score", 0.0),
            })
            return {
                "status": "next_question",
                "question": next_question,
                "evaluation": evaluation,
                "next_index": session.state.current_question_index,
            }

    async def handle_interruption(self, session_uid: str) -> Dict[str, Any]:
        """Handle user interruption mid-response."""
        session = self._sessions.get(session_uid)
        if not session:
            return {"status": "error"}

        self.sm.interrupt(session_uid)
        await self._broadcast_event(session_uid, "interrupted", {
            "message": "I stopped speaking. Go ahead.",
            "interruption_count": session.state.interruption_count,
        })

        # Stop TTS for this session
        try:
            from src.services.realtime_tts import get_tts_engine
            await get_tts_engine().stop_stream(session_uid)
        except Exception:
            pass

        return {"status": "interrupted", "count": session.state.interruption_count}

    async def _generate_question(self, session: LiveInterviewSession) -> str:
        """Generate a context-aware interview question."""
        mode = InterviewMode(session.interview_type) if session.interview_type in \
            [m.value for m in InterviewMode] else InterviewMode.TECHNICAL

        templates = QUESTION_TEMPLATES.get(mode, QUESTION_TEMPLATES[InterviewMode.TECHNICAL])
        idx = session.state.current_question_index

        if idx < len(templates):
            question = templates[idx]
        else:
            # Use Claude for dynamic questions via existing reasoning pipeline
            try:
                from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
                pipeline = get_reasoning_pipeline()
                context = {
                    "interview_type": session.interview_type,
                    "question_index": idx,
                    "resume": session.state.metadata.get("resume_context", {}),
                    "previous_answers": [t["text"] for t in session.transcript if t["speaker"] == "user"],
                }
                result = await pipeline.run({
                    "query": f"Generate a {session.interview_type} interview question (question #{idx+1})",
                    "context": json.dumps(context),
                    "instructions": "Generate a single, clear interview question. No preamble.",
                })
                question = result.get("response", f"Tell me about your experience with {session.interview_type} concepts.")
            except Exception:
                question = f"Let's talk about a key {session.interview_type} concept. What do you think is most important?"
        return question

    async def _evaluate_response(self, session: LiveInterviewSession, transcript: str) -> Dict[str, Any]:
        """Evaluate user response using existing interview evaluation services."""
        async with self._evaluation_semaphore:
            try:
                from src.services.interview.technical_interview_service import get_technical_interview_service
                technical_service = get_technical_interview_service()
                result = await technical_service.evaluate_answer(
                    question=session.state.current_question or "",
                    answer=transcript,
                    difficulty=getattr(session.state, "difficulty", "intermediate") or "intermediate",
                    domain=session.interview_type or "backend_engineering",
                    rubric_context=f"question_index={session.state.current_question_index}; interview_type={session.interview_type}",
                    candidate_context=json.dumps(session.state.metadata.get("resume_context", {}), default=str),
                )
                payload = result.model_dump() if hasattr(result, "model_dump") else (result or {})
                score = payload.get("overall_score", 0.7) if payload else 0.7
                return {
                    "overall_score": round(score * 100),
                    "dimension_scores": payload.get("dimension_scores", {}) if payload else {},
                    "strengths": payload.get("strengths", []) if payload else [],
                    "improvements": payload.get("improvements", []) if payload else [],
                    "should_follow_up": score < 0.7,
                    "follow_up_question": payload.get("follow_up", "") if payload else "",
                    "confidence": payload.get("confidence", 0.8) if payload else 0.8,
                }
            except Exception as exc:
                logger.error(f"Evaluation error: {exc}")
                return {
                    "overall_score": 70,
                    "dimension_scores": {},
                    "strengths": ["Response received"],
                    "improvements": ["Automatic scoring unavailable"],
                    "should_follow_up": False,
                    "confidence": 0.5,
                }

    async def _close_interview(self, session: LiveInterviewSession) -> Dict[str, Any]:
        """Close the interview and compute final scores."""
        self.sm.transition(session.session_uid, InterviewStage.CLOSING)

        scores = session.state.scores
        avg_score = sum(scores) / len(scores) if scores else 0.0

        closing = {
            "status": "completed",
            "session_uid": session.session_uid,
            "total_questions": len(scores),
            "average_score": round(avg_score, 1),
            "scores": scores,
            "evaluations": session.evaluations,
            "transcript": session.transcript,
        }

        await self._broadcast_event(session.session_uid, "INTERVIEW_COMPLETED", closing)
        self.sm.transition(session.session_uid, InterviewStage.COMPLETED)
        session.active = False

        # Persist interview
        await self._persist_interview(session, closing)
        return closing

    async def _on_stt_partial(self, session: LiveInterviewSession, result: Any):
        """Handle partial STT transcript result — stream transcript + live analysis to frontend."""
        try:
            event_type = "USER_TRANSCRIPT_PARTIAL" if result.is_partial else "USER_TRANSCRIPT_FINAL"
            await self._broadcast_event(session.session_uid, event_type, {
                "transcript": result.transcript,
                "confidence": result.confidence,
                "is_partial": result.is_partial,
                "words": getattr(result, 'words', []),
            })

            # Run live evaluation on the transcript
            from src.services.interview.live_evaluation import analyze_live_response
            analysis = analyze_live_response(result.transcript)

            await self._broadcast_event(session.session_uid, "LIVE_ANALYSIS_UPDATE", {
                "word_count": analysis.word_count,
                "speaking_pace_wpm": analysis.speaking_pace_wpm,
                "filler_count": analysis.filler_count,
                "filler_words_found": analysis.filler_words_found,
                "star_score": analysis.star_score,
                "confidence_score": analysis.confidence_score,
                "communication_score": analysis.communication_score,
                "technical_depth_score": analysis.technical_depth_score,
            })
        except Exception:
            pass

    async def pause_session(self, session_uid: str) -> bool:
        session = self._sessions.get(session_uid)
        if not session:
            return False
        self.sm.pause(session_uid)
        await self._broadcast_event(session_uid, "interview_paused", {})
        return True

    async def resume_session(self, session_uid: str) -> bool:
        return self.sm.resume(session_uid)

    async def get_status(self, session_uid: str) -> Optional[Dict[str, Any]]:
        session = self._sessions.get(session_uid)
        if not session:
            return None
        return {
            "session_uid": session.session_uid,
            "user_id": session.user_id,
            "interview_type": session.interview_type,
            "stage": session.state.stage.value,
            "current_question": session.state.current_question,
            "question_index": session.state.current_question_index,
            "total_questions": session.state.total_questions,
            "interruption_count": session.state.interruption_count,
            "active": session.active,
            "scores": session.state.scores,
        }

    async def _broadcast_event(self, session_uid: str, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all WebSocket subscribers for this session."""
        try:
            from src.runtime.realtime import get_ws_manager
            await get_ws_manager().broadcast_to_session(session_uid, event_type, data)
        except Exception:
            pass
        try:
            from src.runtime.streaming import get_stream_manager
            await get_stream_manager().publish(session_uid, f"interview_{event_type}", data)
        except Exception:
            pass

    async def _persist_interview(self, session: LiveInterviewSession, result: Dict[str, Any]):
        """Persist completed interview to Redis + PostgreSQL."""
        try:
            from src.db.redis import redis_client
            key = f"interview:session:{session.session_uid}"
            await redis_client.setex(key, 86400, json.dumps(result, default=str))
        except Exception:
            pass
        try:
            from src.services.interview import persistence_service
            await persistence_service.save_interview_session(session.session_uid, {
                "user_id": session.user_id,
                "interview_type": session.interview_type,
                "scores": session.state.scores,
                "average_score": result.get("average_score", 0),
                "total_score": result.get("average_score", 0),
                "evaluations": session.evaluations,
                "questions": [
                    {"question": t.get("text", "") if isinstance(t, dict) else str(t), "answer": session.transcript[i*2+1].get("text", "") if i*2+1 < len(session.transcript) else "", "score": session.state.scores[i] if i < len(session.state.scores) else 0}
                    for i, t in enumerate(session.transcript[::2])
                ],
            })
        except Exception as exc:
            logger.error(f"Interview persistence failed: {exc}")

    async def recover_session(self, session_uid: str) -> Optional[Dict[str, Any]]:
        """Redis-backed session recovery — restores active or completed interview state."""
        try:
            from src.db.redis import redis_client
            raw = await redis_client.get(f"interview:session:{session_uid}")
            if not raw:
                return None
            data = json.loads(raw)
            if data.get("status") == "completed":
                return data

            # Rebuild in-memory session from Redis data
            session = LiveInterviewSession(
                session_uid=session_uid,
                user_id=data.get("user_id", "unknown"),
                interview_type=data.get("interview_type", "technical"),
                state=self.sm.get_state(session_uid) or self.sm.create_session(
                    session_uid=session_uid,
                    interview_type=data.get("interview_type", "technical"),
                    total_questions=data.get("total_questions", 5),
                ),
                transcript=data.get("transcript", []),
                evaluations=data.get("evaluations", []),
                active=True,
            )
            async with self._lock:
                self._sessions[session_uid] = session
            await self._broadcast_event(session_uid, "INTERVIEW_RECOVERED", {
                "session_uid": session_uid,
                "question_index": data.get("question_index", 0),
            })
            return {"status": "recovered", "session_uid": session_uid}
        except Exception as exc:
            logger.error(f"Session recovery failed: {exc}")
            return None

    async def get_replay(self, session_uid: str) -> Optional[Dict[str, Any]]:
        """Get full interview replay data."""
        session = self._sessions.get(session_uid)
        if session:
            return {
                "session_uid": session.session_uid,
                "interview_type": session.interview_type,
                "stage": session.state.stage.value,
                "transcript": session.transcript,
                "evaluations": session.evaluations,
                "scores": session.state.scores,
                "transition_history": self.sm.get_transition_history(session_uid),
                "duration_seconds": time.time() - session.created_at,
            }
        try:
            from src.db.redis import redis_client
            raw = await redis_client.get(f"interview:session:{session_uid}")
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    async def shutdown(self):
        for sid, session in list(self._sessions.items()):
            if session.active:
                session.active = False
                await self._broadcast_event(sid, "interview_closed", {
                    "reason": "system_shutdown",
                })
        self._sessions.clear()


# ── Singleton ────────────────────────────────────────────────────────

_orchestrator: Optional[LiveInterviewOrchestrator] = None


def get_live_interview_orchestrator() -> LiveInterviewOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = LiveInterviewOrchestrator()
    return _orchestrator
