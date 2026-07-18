"""STT transcript engine tests — providers, orchestrator, partial/final."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestSTTOrchestrator:
    @pytest.mark.asyncio
    async def test_stt_orchestrator_singleton(self):
        from src.services.realtime_stt import get_stt_orchestrator
        stt = get_stt_orchestrator()
        assert stt is not None

    @pytest.mark.asyncio
    async def test_stt_orchestrator_send_audio(self):
        from src.services.realtime_stt import get_stt_orchestrator
        stt = get_stt_orchestrator()
        stt._running = True

        # Send audio bytes — should be enqueued
        await stt.send_audio(b"test audio bytes", session_uid="sess-stt-1")
        assert stt._buffer.qsize() >= 1

    @pytest.mark.asyncio
    async def test_stt_result_json(self):
        from src.services.realtime_stt import STTResult
        result = STTResult(
            transcript="hello world",
            is_partial=True,
            confidence=0.92,
            provider="deepgram",
        )
        j = result.to_json()
        assert j["transcript"] == "hello world"
        assert j["is_partial"] is True
        assert j["confidence"] == 0.92

    @pytest.mark.asyncio
    async def test_stt_chunk_json(self):
        from src.services.realtime_stt import STTChunk
        chunk = STTChunk(
            chunk_id="ch-1",
            session_uid="sess-stt-2",
            audio_bytes=b"data",
            sequence=42,
        )
        j = chunk.to_json()
        assert j["chunk_id"] == "ch-1"
        assert j["sequence"] == 42

    @pytest.mark.asyncio
    async def test_stt_provider_enum(self):
        from src.services.realtime_stt import STTProvider
        assert STTProvider.DEEPGRAM.value == "deepgram"
        assert STTProvider.WHISPER.value == "whisper"

    @pytest.mark.asyncio
    async def test_deepgram_provider_no_key(self):
        from src.services.realtime_stt import DeepgramProvider
        provider = DeepgramProvider()
        # Without DEEPGRAM_API_KEY, connect returns False
        connected = await provider.connect()
        assert connected is False

    @pytest.mark.asyncio
    async def test_whisper_provider_connect(self):
        from src.services.realtime_stt import WhisperStreamingProvider
        provider = WhisperStreamingProvider()
        connected = await provider.connect()
        assert connected is True

    @pytest.mark.asyncio
    async def test_on_transcript_callback(self):
        from src.services.realtime_stt import get_stt_orchestrator, STTResult
        stt = get_stt_orchestrator()

        results = []
        stt.on_transcript(lambda r: results.append(r.transcript))

        # Simulate a callback invocation
        stt._callbacks[0](STTResult(transcript="test callback", is_partial=True, confidence=0.88, provider="test"))
        assert "test callback" in results


class TestTurnManager:
    @pytest.mark.asyncio
    async def test_turn_manager_init(self):
        from src.interview_runtime.duplex_engine import get_turn_manager
        tm = get_turn_manager()
        state = tm.init_session("tm-sess-1")
        assert state.session_uid == "tm-sess-1"
        assert state.current_speaker.value == "system"

    @pytest.mark.asyncio
    async def test_turn_manager_user_speaking(self):
        from src.interview_runtime.duplex_engine import get_turn_manager
        tm = get_turn_manager()
        tm.init_session("tm-sess-2")
        await tm.user_started_speaking("tm-sess-2")
        state = tm.get_state("tm-sess-2")
        assert state.user_is_speaking is True

    @pytest.mark.asyncio
    async def test_turn_manager_transcript_context(self):
        from src.interview_runtime.duplex_engine import get_turn_manager
        tm = get_turn_manager()
        tm.init_session("tm-sess-3")
        await tm.ai_started_speaking("tm-sess-3")
        await tm.ai_stopped_speaking("tm-sess-3", "Hello candidate")
        ctx = tm.get_transcript_context("tm-sess-3")
        assert "Hello candidate" in ctx
