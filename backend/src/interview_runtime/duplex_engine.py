"""Phase 8 — Duplex Conversation Engine.

Bidirectional conversational engine with:
- Simultaneous speak/listen (duplex)
- Barge-in detection and interruption
- Turn management with backchannel support
- Adaptive pacing based on user behavior
- Silence timeout detection
- Realtime transcript memory with context stitching
"""

import time
import uuid
import logging
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


logger = logging.getLogger(__name__)


class TurnRole(str, Enum):
    AI = "ai"
    USER = "user"
    SYSTEM = "system"


class ConversationSignal(str, Enum):
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    BARGE_IN = "barge_in"
    SILENCE_TIMEOUT = "silence_timeout"
    AI_START_SPEAKING = "ai_start_speaking"
    AI_STOP_SPEAKING = "ai_stop_speaking"
    TURN_TAKEN = "turn_taken"
    TURN_RELEASED = "turn_released"


@dataclass
class ConversationTurn:
    turn_id: str
    role: TurnRole
    sequence: int
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    transcript: str = ""
    is_partial: bool = False
    was_interrupted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationState:
    session_uid: str
    current_speaker: TurnRole = TurnRole.SYSTEM
    turns: List[ConversationTurn] = field(default_factory=list)
    turn_sequence: int = 0
    ai_is_speaking: bool = False
    user_is_speaking: bool = False
    silence_start: float = 0.0
    silence_timeout_ms: int = 3000
    interruption_count: int = 0
    last_activity_at: float = field(default_factory=time.time)


class TurnManager:
    """Manages conversational turn-taking with duplex support."""

    def __init__(self, silence_timeout_ms: int = 3000):
        self._states: Dict[str, ConversationState] = {}
        self._silence_timeout_ms = silence_timeout_ms
        self._signal_handlers: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()

    def init_session(self, session_uid: str) -> ConversationState:
        state = ConversationState(
            session_uid=session_uid,
            silence_timeout_ms=self._silence_timeout_ms,
        )
        self._states[session_uid] = state
        return state

    def get_state(self, session_uid: str) -> Optional[ConversationState]:
        return self._states.get(session_uid)

    async def user_started_speaking(self, session_uid: str):
        """Handle user speech onset."""
        state = self._states.get(session_uid)
        if not state:
            return

        async with self._lock:
            state.user_is_speaking = True
            state.last_activity_at = time.time()

            # If AI is speaking, this is a barge-in
            if state.ai_is_speaking:
                state.interruption_count += 1
                await self._emit_signal(session_uid, ConversationSignal.BARGE_IN, {
                    "interruption_count": state.interruption_count,
                })

            turn = ConversationTurn(
                turn_id=str(uuid.uuid4()),
                role=TurnRole.USER,
                sequence=state.turn_sequence,
            )
            state.turns.append(turn)
            state.turn_sequence += 1
            state.current_speaker = TurnRole.USER

        await self._emit_signal(session_uid, ConversationSignal.SPEECH_START, {})

    async def user_stopped_speaking(self, session_uid: str, transcript: str = "", duration_ms: float = 0):
        """Handle user speech offset."""
        state = self._states.get(session_uid)
        if not state:
            return

        async with self._lock:
            state.user_is_speaking = False
            state.silence_start = time.time()

            if state.turns:
                current_turn = state.turns[-1]
                current_turn.end_time = time.time()
                current_turn.transcript = transcript
                current_turn.is_partial = False

        await self._emit_signal(session_uid, ConversationSignal.SPEECH_END, {
            "transcript": transcript,
            "duration_ms": duration_ms,
        })

    async def ai_started_speaking(self, session_uid: str):
        state = self._states.get(session_uid)
        if not state:
            return

        async with self._lock:
            state.ai_is_speaking = True
            state.last_activity_at = time.time()

            turn = ConversationTurn(
                turn_id=str(uuid.uuid4()),
                role=TurnRole.AI,
                sequence=state.turn_sequence,
            )
            state.turns.append(turn)
            state.turn_sequence += 1
            state.current_speaker = TurnRole.AI

        await self._emit_signal(session_uid, ConversationSignal.AI_START_SPEAKING, {})

    async def ai_stopped_speaking(self, session_uid: str, transcript: str = ""):
        state = self._states.get(session_uid)
        if not state:
            return

        async with self._lock:
            state.ai_is_speaking = False
            state.silence_start = time.time()

            if state.turns:
                current_turn = state.turns[-1]
                current_turn.end_time = time.time()
                current_turn.transcript = transcript

        await self._emit_signal(session_uid, ConversationSignal.AI_STOP_SPEAKING, {})

    async def check_silence(self, session_uid: str) -> bool:
        """Check if silence timeout has elapsed — trigger timeout signal."""
        state = self._states.get(session_uid)
        if not state:
            return False

        if state.silence_start > 0:
            elapsed = (time.time() - state.silence_start) * 1000
            if elapsed > state.silence_timeout_ms and not state.user_is_speaking:
                await self._emit_signal(session_uid, ConversationSignal.SILENCE_TIMEOUT, {
                    "elapsed_ms": elapsed,
                })
                return True
        return False

    def on_signal(self, signal: ConversationSignal, handler: Callable):
        signal_key = signal.value
        if signal_key not in self._signal_handlers:
            self._signal_handlers[signal_key] = []
        self._signal_handlers[signal_key].append(handler)

    async def _emit_signal(self, session_uid: str, signal: ConversationSignal, data: Dict[str, Any]):
        handlers = self._signal_handlers.get(signal.value, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(session_uid, data)
                else:
                    handler(session_uid, data)
            except Exception as exc:
                logger.error(f"Signal handler error ({signal.value}): {exc}")

    def get_transcript_context(self, session_uid: str, max_turns: int = 10) -> str:
        """Build conversational context from recent turns."""
        state = self._states.get(session_uid)
        if not state:
            return ""

        recent = state.turns[-max_turns:]
        lines = []
        for turn in recent:
            prefix = "Interviewer" if turn.role == TurnRole.AI else "Candidate"
            if turn.transcript:
                lines.append(f"{prefix}: {turn.transcript}")
        return "\n".join(lines)

    async def reset(self, session_uid: str):
        self._states.pop(session_uid, None)


class InterruptionEngine:
    """Handles barge-in detection and mid-speech cancellation."""

    def __init__(self):
        self._active_interrupts: Dict[str, bool] = {}

    async def handle_interruption(self, session_uid: str, turn_mgr: TurnManager):
        """Process a barge-in: stop TTS, transition AI state, and prepare for user input."""
        state = turn_mgr.get_state(session_uid)
        if not state:
            return

        self._active_interrupts[session_uid] = True

        # Stop TTS immediately
        try:
            from src.services.realtime_tts import get_tts_engine
            await get_tts_engine().stop_stream(session_uid)
        except Exception:
            pass

        # Update turn state
        await turn_mgr.ai_stopped_speaking(session_uid)

        logger.info(f"Interruption processed for {session_uid} (count={state.interruption_count})")
        self._active_interrupts[session_uid] = False

    def is_interrupted(self, session_uid: str) -> bool:
        return self._active_interrupts.get(session_uid, False)


class RealtimeMemory:
    """In-memory transcript cache with partial/final tracking."""

    def __init__(self, max_entries: int = 500):
        self._sessions: Dict[str, List[Dict[str, Any]]] = {}
        self._partials: Dict[str, str] = {}
        self._max_entries = max_entries

    def add_partial(self, session_uid: str, transcript: str):
        self._partials[session_uid] = transcript

    def finalize_transcript(self, session_uid: str, transcript: str):
        self._partials.pop(session_uid, None)
        if session_uid not in self._sessions:
            self._sessions[session_uid] = []
        self._sessions[session_uid].append({
            "text": transcript,
            "timestamp": time.time(),
        })
        if len(self._sessions[session_uid]) > self._max_entries:
            self._sessions[session_uid] = self._sessions[session_uid][-self._max_entries:]

    def get_recent(self, session_uid: str, n: int = 10) -> List[Dict[str, Any]]:
        entries = self._sessions.get(session_uid, [])
        return entries[-n:]

    def get_full_transcript(self, session_uid: str) -> str:
        entries = self._sessions.get(session_uid, [])
        return " ".join(e["text"] for e in entries)

    def clear(self, session_uid: str):
        self._sessions.pop(session_uid, None)
        self._partials.pop(session_uid, None)


# ── Singletons ───────────────────────────────────────────────────────

_turn_mgr: Optional[TurnManager] = None
_interruption: Optional[InterruptionEngine] = None
_memory: Optional[RealtimeMemory] = None


def get_turn_manager() -> TurnManager:
    global _turn_mgr
    if _turn_mgr is None:
        _turn_mgr = TurnManager()
    return _turn_mgr


def get_interruption_engine() -> InterruptionEngine:
    global _interruption
    if _interruption is None:
        _interruption = InterruptionEngine()
    return _interruption


def get_realtime_memory() -> RealtimeMemory:
    global _memory
    if _memory is None:
        _memory = RealtimeMemory()
    return _memory
