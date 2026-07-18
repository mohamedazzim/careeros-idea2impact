"""
Interview persistence service — production-safe Redis + PostgreSQL interview storage.

Replaces volatile in-memory SessionState with:
- Redis-backed active session state (TTL-governed, distributed-safe)
- PostgreSQL interview history (durable, queryable, recoverable)
- Session restoration from Redis + PostgreSQL fallback
- Resumable session recovery after service restart
- Distributed-safe session isolation

Phase 4D Hardening: Persistence boundaries.
"""
import json
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from src.db.redis import redis_client
from src.db.session import async_session
from src.core.config import settings
from src.models.interview import InterviewSession as InterviewSessionModel
from src.models.interview import InterviewQuestion as InterviewQuestionModel
from src.models.interview import InterviewWeaknessHistory
from src.observability.metrics import INTERVIEW_CONCURRENCY_PRESSURE

logger = logging.getLogger(__name__)

REDIS_PREFIX = settings.INTERVIEW_REDIS_KEY_PREFIX
SESSION_TTL = settings.INTERVIEW_SESSION_TTL
ORPHAN_TTL = settings.INTERVIEW_ORPHAN_TTL


@dataclass
class SessionState:
    session_id: str
    interview_type: str
    difficulty_level: str = "intermediate"
    questions: List[Dict[str, Any]] = field(default_factory=list)
    current_question_index: int = 0
    total_score: float = 0.0
    confidence_progression: List[float] = field(default_factory=list)
    weakness_tracker: Dict[str, int] = field(default_factory=dict)
    adaptation_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    created_at: float = field(default_factory=time.time)
    db_id: Optional[int] = None


class InterviewPersistenceService:
    """Production-safe interview persistence.

    Active sessions live in Redis with TTL governance.
    Closed sessions + questions are persisted to PostgreSQL.
    Sessions can be restored from Redis (active) or PostgreSQL (historical).
    """

    # ── Redis Active Session Operations ────────────────────────────

    def _session_key(self, session_id: str) -> str:
        return f"{REDIS_PREFIX}session:{session_id}"

    def _questions_key(self, session_id: str) -> str:
        return f"{REDIS_PREFIX}questions:{session_id}"

    def _sessions_index_key(self) -> str:
        return f"{REDIS_PREFIX}sessions:active"

    async def save_session(self, session: SessionState) -> None:
        key = self._session_key(session.session_id)
        data = {
            "session_id": session.session_id,
            "interview_type": session.interview_type,
            "difficulty_level": session.difficulty_level,
            "current_question_index": session.current_question_index,
            "total_score": session.total_score,
            "confidence_progression": json.dumps(session.confidence_progression),
            "weakness_tracker": json.dumps(session.weakness_tracker),
            "adaptation_history": json.dumps(session.adaptation_history),
            "metadata": json.dumps(session.metadata),
            "status": session.status,
            "created_at": session.created_at,
            "db_id": session.db_id,
        }
        await redis_client.hset(key, mapping=data)
        await redis_client.expire(key, SESSION_TTL)
        await redis_client.sadd(self._sessions_index_key(), session.session_id)
        await redis_client.expire(self._sessions_index_key(), SESSION_TTL)
        INTERVIEW_CONCURRENCY_PRESSURE.observe(await self.active_session_count())

    async def load_session(self, session_id: str) -> Optional[SessionState]:
        key = self._session_key(session_id)
        data = await redis_client.hgetall(key)
        if not data:
            return await self._restore_from_db(session_id)
        return self._deserialize_session(data)

    async def _restore_from_db(self, session_id: str) -> Optional[SessionState]:
        try:
            async with async_session() as db:
                from sqlalchemy import select
                result = await db.execute(
                    select(InterviewSessionModel).where(
                        InterviewSessionModel.session_uid == session_id,
                        InterviewSessionModel.status == "active",
                    )
                )
                model = result.scalar_one_or_none()
                if not model:
                    return None

                session = SessionState(
                    session_id=model.session_uid,
                    interview_type=model.interview_type,
                    difficulty_level=model.difficulty_level,
                    current_question_index=model.current_question_index,
                    total_score=model.total_score,
                    confidence_progression=model.confidence_progression or [],
                    weakness_tracker=model.metadata_.get("weakness_tracker", {}),
                    adaptation_history=model.adaptation_history or [],
                    metadata=model.metadata_ or {},
                    status=model.status,
                    db_id=model.id,
                )
                # Re-hydrate into Redis for fast access
                await self.save_session(session)
                logger.info("session_restored_from_db", extra={"session_id": session_id})
                return session
        except Exception as e:
            logger.error("session_restore_failed", extra={"session_id": session_id, "error": str(e)})
            return None

    async def delete_session(self, session_id: str) -> None:
        await redis_client.delete(self._session_key(session_id))
        await redis_client.delete(self._questions_key(session_id))
        await redis_client.srem(self._sessions_index_key(), session_id)

    async def active_session_count(self) -> int:
        try:
            return await redis_client.scard(self._sessions_index_key())
        except Exception:
            return 0

    async def list_active_sessions(self) -> List[str]:
        try:
            return list(await redis_client.smembers(self._sessions_index_key()))
        except Exception:
            return []

    # ── Redis Question Storage ─────────────────────────────────────

    async def save_questions(self, session_id: str, questions: List[Dict[str, Any]]) -> None:
        key = self._questions_key(session_id)
        pipe = redis_client.pipeline()
        for q in questions:
            pipe.rpush(key, json.dumps(q, default=str))
        await pipe.execute()
        await redis_client.expire(key, SESSION_TTL)

    async def load_questions(self, session_id: str) -> List[Dict[str, Any]]:
        key = self._questions_key(session_id)
        raw = await redis_client.lrange(key, 0, -1)
        questions = []
        for r in raw:
            try:
                questions.append(json.loads(r))
            except json.JSONDecodeError:
                questions.append({"raw": r})
        if not questions:
            questions = await self._restore_questions_from_db(session_id)
        return questions

    async def _restore_questions_from_db(self, session_id: str) -> List[Dict[str, Any]]:
        try:
            async with async_session() as db:
                from sqlalchemy import select
                session_result = await db.execute(
                    select(InterviewSessionModel).where(
                        InterviewSessionModel.session_uid == session_id
                    )
                )
                session_model = session_result.scalar_one_or_none()
                if not session_model:
                    return []

                result = await db.execute(
                    select(InterviewQuestionModel)
                    .where(InterviewQuestionModel.session_id == session_model.id)
                    .order_by(InterviewQuestionModel.question_index)
                )
                models = result.scalars().all()
                questions = []
                for m in models:
                    questions.append({
                        "question": m.question_text,
                        "answer": m.answer_text,
                        "difficulty_level": m.difficulty_level,
                        "score": m.score,
                        "confidence": m.confidence,
                        "rubric_scores": m.rubric_scores or {},
                        "contradictions_detected": m.contradictions_detected > 0,
                        "strengths": m.strengths or [],
                        "weaknesses": m.weaknesses or [],
                        "improvement_suggestions": m.improvement_suggestions or [],
                        "critique": m.critique or {},
                        "citations": m.citations or [],
                        "governance_flags": m.governance_flags or {},
                        "trace": m.trace or {},
                    })
                return questions
        except Exception as e:
            logger.error("questions_restore_failed", extra={"session_id": session_id, "error": str(e)})
            return []

    # ── PostgreSQL Persistence ──────────────────────────────────────

    async def persist_session_to_db(self, session: SessionState) -> int:
        async with async_session() as db:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            user_id = session.metadata.get("user_id") if session.metadata else None

            if session.db_id:
                from sqlalchemy import update
                await db.execute(
                    update(InterviewSessionModel)
                    .where(InterviewSessionModel.id == session.db_id)
                    .values(
                        user_id=user_id,
                        status=session.status,
                        difficulty_level=session.difficulty_level,
                        current_question_index=session.current_question_index,
                        total_score=session.total_score,
                        confidence_progression=session.confidence_progression,
                        adaptation_history=session.adaptation_history,
                        metadata_={**session.metadata, "weakness_tracker": session.weakness_tracker},
                    )
                )
                await db.commit()
                return session.db_id

            stmt = pg_insert(InterviewSessionModel).values(
                session_uid=session.session_id,
                user_id=user_id,
                interview_type=session.interview_type,
                status=session.status,
                difficulty_level=session.difficulty_level,
                current_question_index=session.current_question_index,
                total_score=session.total_score,
                confidence_progression=session.confidence_progression,
                adaptation_history=session.adaptation_history,
                metadata_={**session.metadata, "weakness_tracker": session.weakness_tracker},
            ).on_conflict_do_update(
                index_elements=["session_uid"],
                set_={
                    "user_id": user_id,
                    "status": session.status,
                    "total_score": session.total_score,
                    "current_question_index": session.current_question_index,
                    "metadata": {**session.metadata, "weakness_tracker": session.weakness_tracker},
                }
            ).returning(InterviewSessionModel.id)
            result = await db.execute(stmt)
            await db.commit()
            db_id = result.scalar_one()
            session.db_id = db_id
            return db_id

    async def save_interview_session(
        self, session_uid: str, data: Dict[str, Any]
    ) -> Optional[int]:
        """Save interview session and questions to PostgreSQL from orchestrator data."""
        session_state = SessionState(
            session_id=session_uid,
            interview_type=data.get("interview_type", "technical"),
            difficulty_level=data.get("difficulty_level", "intermediate"),
            current_question_index=len(data.get("scores", [])),
            total_score=float(data.get("average_score") or data.get("total_score") or 0),
            status="completed",
            metadata={"user_id": data.get("user_id", "unknown"), "job_title": data.get("job_title", "")},
        )
        db_id = await self.persist_session_to_db(session_state)
        # Persist questions
        questions = data.get("questions") or data.get("evaluations") or []
        for i, q in enumerate(questions):
            await self.persist_question_to_db(db_id, q if isinstance(q, dict) else {"answer": str(q), "score": data.get("scores", [0]*len(questions))[i] if i < len(data.get("scores", [])) else 0}, i)
        return db_id

    async def persist_question_to_db(
        self, db_session_id: int, question: Dict[str, Any], question_index: int
    ) -> None:
        async with async_session() as db:
            existing_check = await db.execute(
                __import__("sqlalchemy").select(InterviewQuestionModel.session_id).where(
                    InterviewQuestionModel.session_id == db_session_id,
                    InterviewQuestionModel.question_index == question_index,
                ).limit(1)
            )
            if existing_check.scalar_one_or_none():
                return

            model = InterviewQuestionModel(
                session_id=db_session_id,
                question_index=question_index,
                question_text=question.get("question", ""),
                answer_text=question.get("answer", ""),
                difficulty_level=question.get("difficulty_level", "intermediate"),
                score=question.get("score", 0.0),
                confidence=question.get("confidence", 0.5),
                rubric_scores=question.get("rubric_scores", {}) or {},
                contradictions_detected=1 if question.get("contradictions_detected") else 0,
                strengths=question.get("strengths", []) or [],
                weaknesses=question.get("weaknesses", []) or [],
                improvement_suggestions=question.get("improvement_suggestions", []) or [],
                critique=question.get("critique", {}) or {},
                citations=question.get("citations", []) or [],
                governance_flags=question.get("governance_flags", {}) or {},
                trace=question.get("trace", {}) or {},
            )
            db.add(model)
            await db.commit()

    async def close_session_in_db(self, session_id: str, summary: Dict[str, Any]) -> None:
        from datetime import datetime, timezone
        async with async_session() as db:
            from sqlalchemy import update
            await db.execute(
                update(InterviewSessionModel)
                .where(InterviewSessionModel.session_uid == session_id)
                .values(
                    status="completed",
                    closed_at=datetime.now(timezone.utc),
                    total_score=summary.get("average_score", 0.0),
                    current_question_index=summary.get("questions_asked", 0),
                    difficulty_level=summary.get("final_difficulty", "intermediate"),
                    adaptation_history=summary.get("adaptation_history", []),
                )
            )
            await db.commit()

    async def persist_weakness_history(
        self, user_id: Optional[str], session_id: str,
        weaknesses: Dict[str, int], severity: str,
        classification_map: Dict[str, str]
    ) -> None:
        async with async_session() as db:
            for w_type, count in weaknesses.items():
                model = InterviewWeaknessHistory(
                    user_id=user_id,
                    weakness_type=w_type,
                    session_uid=session_id,
                    occurrences=count,
                    severity=severity,
                    pattern_classification=classification_map.get(w_type),
                )
                db.add(model)
            await db.commit()

    async def get_weakness_history(self, user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        async with async_session() as db:
            from sqlalchemy import select
            query = select(InterviewWeaknessHistory)
            if user_id:
                query = query.where(InterviewWeaknessHistory.user_id == user_id)
            query = query.order_by(InterviewWeaknessHistory.created_at.desc()).limit(limit)
            result = await db.execute(query)
            models = result.scalars().all()
            return [
                {
                    "weakness_type": m.weakness_type,
                    "session_uid": m.session_uid,
                    "occurrences": m.occurrences,
                    "severity": m.severity,
                    "pattern_classification": m.pattern_classification,
                    "created_at": str(m.created_at),
                }
                for m in models
            ]

    # ── Orphan Session Cleanup ─────────────────────────────────────

    async def cleanup_orphaned_sessions(self) -> int:
        active = await self.list_active_sessions()
        cleaned = 0
        now = time.time()
        for sid in active:
            key = self._session_key(sid)
            created_raw = await redis_client.hget(key, "created_at")
            if created_raw:
                created = float(created_raw)
                if now - created > ORPHAN_TTL:
                    await self.delete_session(sid)
                    cleaned += 1
        return cleaned

    # ── Deserialization Helpers ────────────────────────────────────

    def _deserialize_session(self, data: Dict[str, str]) -> SessionState:
        return SessionState(
            session_id=data.get("session_id", ""),
            interview_type=data.get("interview_type", "technical"),
            difficulty_level=data.get("difficulty_level", "intermediate"),
            current_question_index=int(data.get("current_question_index", 0)),
            total_score=float(data.get("total_score", 0.0)),
            confidence_progression=self._json_list(data.get("confidence_progression", "[]")),
            weakness_tracker=self._json_dict(data.get("weakness_tracker", "{}")),
            adaptation_history=self._json_list(data.get("adaptation_history", "[]")),
            metadata=self._json_dict(data.get("metadata", "{}")),
            status=data.get("status", "active"),
            created_at=float(data.get("created_at", time.time())),
            db_id=int(data["db_id"]) if data.get("db_id") and data["db_id"] != "None" else None,
        )

    @staticmethod
    def _json_list(raw: str) -> List[Any]:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    @staticmethod
    def _json_dict(raw: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}


_svc: InterviewPersistenceService | None = None


def get_interview_persistence_service() -> InterviewPersistenceService:
    global _svc
    if _svc is None:
        _svc = InterviewPersistenceService()
    return _svc


def reset_interview_persistence_service() -> None:
    global _svc
    _svc = None


def __getattr__(name: str):
    if name == "interview_persistence_service":
        return get_interview_persistence_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
