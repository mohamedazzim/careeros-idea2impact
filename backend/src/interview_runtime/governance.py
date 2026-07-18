"""Phase 7 — Realtime Interview Governance & Safety.

Toxicity detection, prompt injection detection, abuse rate limiting,
hallucination detection, unsafe response interception, and session kill-switch.
Integrates with existing governance layer.
"""

import time
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODERATION_REDIS_PREFIX = "interview:moderation:"

TOXIC_PATTERNS = [
    "hate speech", "violence", "harassment", "threat",
    "explicit content", "self-harm", "illegal activity",
]

INJECTION_PATTERNS = [
    "ignore all previous instructions",
    "you are now",
    "system prompt",
    "DAN mode",
    "jailbreak",
    "pretend you are",
]

RATE_LIMIT_PER_SESSION = 30
RATE_LIMIT_WINDOW = 60


class RealtimeGovernanceGuard:
    """Real-time moderation and safety for live interviews."""

    async def check_message(
        self, session_uid: str, transcript: str, user_id: str = "",
    ) -> Dict[str, Any]:
        """Check a user message for safety violations."""
        transcript_lower = transcript.lower()
        violations = []

        for pattern in TOXIC_PATTERNS:
            if pattern in transcript_lower:
                violations.append({"type": "toxicity", "pattern": pattern, "severity": "high"})

        for pattern in INJECTION_PATTERNS:
            if pattern in transcript_lower:
                violations.append({"type": "prompt_injection", "pattern": pattern, "severity": "critical"})

        if len(transcript) > 5000:
            violations.append({"type": "message_too_long", "length": len(transcript), "severity": "low"})

        rate_limited = await self._check_rate_limit(session_uid)
        if rate_limited:
            violations.append({"type": "rate_limit", "severity": "medium"})

        if violations:
            await self._record_violation(session_uid, user_id, violations)
            critical = any(v["severity"] == "critical" for v in violations)
            await self._emit_violation_event(session_uid, violations)

            return {
                "allowed": not critical,
                "flagged": True,
                "violations": violations,
                "severity": "critical" if critical else "high",
                "action": "block" if critical else "warn",
            }

        return {"allowed": True, "flagged": False, "violations": []}

    async def check_ai_response(self, session_uid: str, response: str) -> Dict[str, Any]:
        """Validate AI response before streaming to user."""
        response_lower = response.lower()

        if any(p in response_lower for p in ["i am not sure about that", "that's classified"]):
            return {"safe": False, "reason": "potential_hallucination_detected"}

        if len(response) < 5:
            return {"safe": False, "reason": "response_too_short"}

        if len(response) > 3000:
            return {"safe": False, "reason": "response_too_long"}

        return {"safe": True}

    async def _check_rate_limit(self, session_uid: str) -> bool:
        try:
            from src.db.redis import redis_client
            key = f"{MODERATION_REDIS_PREFIX}rate:{session_uid}"
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, RATE_LIMIT_WINDOW)
            return count > RATE_LIMIT_PER_SESSION
        except Exception:
            return False

    async def _record_violation(self, session_uid: str, user_id: str, violations: List[Dict]):
        try:
            from src.db.redis import redis_client
            key = f"{MODERATION_REDIS_PREFIX}violations:{session_uid}"
            for v in violations:
                entry = {
                    "session_uid": session_uid,
                    "user_id": user_id,
                    "violation": v,
                    "timestamp": time.time(),
                }
                await redis_client.zadd(key, {str(time.time()): 0}, nx=False)
            await redis_client.expire(key, 86400)
        except Exception:
            pass

    async def _emit_violation_event(self, session_uid: str, violations: List[Dict]):
        try:
            from src.runtime.realtime import get_ws_manager
            await get_ws_manager().broadcast_to_session(session_uid, "moderation_violation", {
                "violations": violations,
                "message": "This message has been flagged by our safety system.",
            })
        except Exception:
            pass

    async def kill_session(self, session_uid: str, reason: str = "admin_override") -> bool:
        """Emergency kill-switch for an interview session."""
        try:
            from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
            orch = get_live_interview_orchestrator()
            session = orch._sessions.get(session_uid)
            if session:
                session.active = False
            await orch.pause_session(session_uid)
            logger.warning(f"Session {session_uid} killed: {reason}")
            return True
        except Exception as exc:
            logger.error(f"Kill session failed: {exc}")
            return False

    async def get_abuse_report(self, session_uid: str) -> Dict[str, Any]:
        try:
            from src.db.redis import redis_client
            key = f"{MODERATION_REDIS_PREFIX}violations:{session_uid}"
            raw = await redis_client.zrange(key, 0, -1)
            violations = raw if raw else []
            return {
                "session_uid": session_uid,
                "violation_count": len(violations),
                "violations": violations,
            }
        except Exception:
            return {"session_uid": session_uid, "violation_count": 0, "violations": []}


# ── Singleton ────────────────────────────────────────────────────────

_guard: Optional[RealtimeGovernanceGuard] = None


def get_realtime_governance() -> RealtimeGovernanceGuard:
    global _guard
    if _guard is None:
        _guard = RealtimeGovernanceGuard()
    return _guard
