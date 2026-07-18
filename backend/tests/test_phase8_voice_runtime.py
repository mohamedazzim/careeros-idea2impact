"""Phase 8 Tests — True Realtime Voice + WebRTC Infrastructure.

Tests for Deepgram streaming STT, ElevenLabs streaming TTS,
duplex conversation engine, turn manager, interruption engine,
distributed session registry, and transcript aggregator.
"""

import pytest
import asyncio
import time

from src.services.stt import (
    DeepgramStreamingProvider, TranscriptAggregator,
)
from src.services.tts import ElevenLabsStreamingProvider
from src.services.realtime_stt import STTChunk, STTResult
from src.services.realtime_tts import TTSChunk, AudioBufferManager, TTSVoice
from src.interview_runtime.duplex_engine import (
    TurnManager, InterruptionEngine, RealtimeMemory,
    ConversationTurn, ConversationState, TurnRole, ConversationSignal,
    get_turn_manager, get_interruption_engine, get_realtime_memory,
)
from src.runtime.distributed import (
    DistributedSessionRegistry,
    RedisPubSubRouter,
    DistributedPresence,
    get_session_registry, get_pubsub_router, get_presence,
)


class TestTranscriptAggregator:
    @pytest.fixture
    def agg(self):
        return TranscriptAggregator()

    def test_add_partial(self, agg):
        result = agg.add_partial("I think the answer is...")
        assert result

    def test_add_final(self, agg):
        agg.add_partial("partial")
        result = agg.add_final("This is the final answer")
        assert result == "This is the final answer"
        assert agg.get_last_final_sentence() == "This is the final answer"

    def test_get_full_transcript(self, agg):
        agg.add_final("Sentence one.")
        agg.add_final("Sentence two.")
        agg.add_partial("and ongoing...")
        full = agg.get_full_transcript()
        assert "Sentence one" in full
        assert "Sentence two" in full
        assert "and ongoing" in full

    def test_reset(self, agg):
        agg.add_final("Something.")
        agg.reset()
        assert agg.get_full_transcript() == ""


class TestDeepgramStreaming:
    def test_connect(self):
        provider = DeepgramStreamingProvider(api_key=None)
        ok = asyncio.run(provider.connect())
        assert ok  # Falls back to mock when no key

    def test_send_audio_when_not_connected(self):
        provider = DeepgramStreamingProvider()
        chunk = STTChunk(chunk_id="c1", session_uid="s1", audio_bytes=b"test", sequence=1)
        result = asyncio.run(provider.send_audio(chunk))
        assert result is None  # Not connected yet


class TestElevenLabsStreaming:
    def test_connect(self):
        provider = ElevenLabsStreamingProvider(api_key=None)
        ok = asyncio.run(provider.connect())
        assert ok is False  # No API key, no SDK — returns False

    def test_get_voices(self):
        provider = ElevenLabsStreamingProvider()
        voices = asyncio.run(provider.get_voices())
        assert len(voices) >= 3


class TestTurnManager:
    @pytest.fixture
    def tm(self):
        return TurnManager()

    def test_init_session(self, tm):
        state = tm.init_session("s1")
        assert state.session_uid == "s1"
        assert state.current_speaker == TurnRole.SYSTEM
        assert state.ai_is_speaking is False

    @pytest.mark.asyncio
    async def test_user_start_speaking(self, tm):
        tm.init_session("s1")
        await tm.user_started_speaking("s1")
        state = tm.get_state("s1")
        assert state.user_is_speaking
        assert len(state.turns) == 1

    @pytest.mark.asyncio
    async def test_ai_speaking_flow(self, tm):
        tm.init_session("s1")
        await tm.ai_started_speaking("s1")
        assert tm.get_state("s1").ai_is_speaking
        await tm.ai_stopped_speaking("s1")
        assert not tm.get_state("s1").ai_is_speaking

    @pytest.mark.asyncio
    async def test_barge_in(self, tm):
        signals = []
        def handler(sid, data):
            signals.append(("barge_in", data))

        tm.on_signal(ConversationSignal.BARGE_IN, handler)
        tm.init_session("s1")
        await tm.ai_started_speaking("s1")
        await tm.user_started_speaking("s1")
        assert len(signals) == 1

    @pytest.mark.asyncio
    async def test_transcript_context(self, tm):
        tm.init_session("s1")
        await tm.ai_started_speaking("s1")
        await tm.ai_stopped_speaking("s1", "Hello, how are you?")
        await tm.user_started_speaking("s1")
        await tm.user_stopped_speaking("s1", "I am doing well, thank you!")
        ctx = tm.get_transcript_context("s1")
        assert "Hello" in ctx
        assert "thank you" in ctx

    def test_singletons(self):
        assert get_turn_manager() is get_turn_manager()
        assert get_interruption_engine() is get_interruption_engine()
        assert get_realtime_memory() is get_realtime_memory()


class TestInterruptionEngine:
    def test_singleton(self):
        engine = get_interruption_engine()
        assert engine is not None

    @pytest.mark.asyncio
    async def test_handle_interruption(self):
        engine = get_interruption_engine()
        tm = get_turn_manager()
        tm.init_session("s1")
        await engine.handle_interruption("s1", tm)
        assert not engine.is_interrupted("s1")


class TestRealtimeMemory:
    @pytest.fixture
    def mem(self):
        return RealtimeMemory()

    def test_add_partial_and_finalize(self, mem):
        mem.add_partial("s1", "I think that the")
        mem.finalize_transcript("s1", "I think that the answer is 42")
        recent = mem.get_recent("s1")
        assert len(recent) == 1
        assert "42" in recent[0]["text"]

    def test_get_full_transcript(self, mem):
        mem.finalize_transcript("s1", "Hello")
        mem.finalize_transcript("s1", "World")
        assert mem.get_full_transcript("s1") == "Hello World"

    def test_max_entries(self, mem):
        for i in range(600):
            mem.finalize_transcript("s1", f"entry_{i}")
        assert len(mem.get_recent("s1", 600)) <= 500


class TestDistributedSessionRegistry:
    def test_singleton(self):
        a = get_session_registry()
        b = get_session_registry()
        assert a is b

    def test_pubsub_singleton(self):
        assert get_pubsub_router() is get_pubsub_router()

    def test_presence_singleton(self):
        assert get_presence() is get_presence()


class TestAudioBufferManager:
    def test_create_buffer(self):
        mgr = AudioBufferManager()
        queue = mgr.create_buffer("s1")
        assert queue is not None

    @pytest.mark.asyncio
    async def test_interrupt_clears(self):
        mgr = AudioBufferManager()
        chunk = TTSChunk(chunk_id="c1", audio_data=b"audio", text="hi", sequence=0)
        await mgr.enqueue("s1", chunk)
        await mgr.interrupt("s1")
        result = await mgr.dequeue("s1")
        assert result is None

    def test_tts_chunk_dataclass(self):
        chunk = TTSChunk(chunk_id="c1", audio_data=b"test", text="hello", sequence=1, is_final=True)
        assert chunk.text == "hello"
        assert chunk.is_final


class TestTurnRoles:
    def test_roles(self):
        assert TurnRole.AI.value == "ai"
        assert TurnRole.USER.value == "user"
        assert TurnRole.SYSTEM.value == "system"


class TestConversationSignals:
    def test_signals(self):
        assert ConversationSignal.SPEECH_START.value == "speech_start"
        assert ConversationSignal.BARGE_IN.value == "barge_in"
        assert ConversationSignal.SPEECH_END.value == "speech_end"
