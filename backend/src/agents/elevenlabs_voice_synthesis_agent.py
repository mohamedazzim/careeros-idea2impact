"""Phase 5 — ElevenLabs Voice Synthesis Agent.

Generates voice scripts and invokes ElevenLabs MCP for audio synthesis.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.agent_observability import get_agent_observability


@dataclass
class VoiceSynthesisState:
    synthesis_run_id: str
    user_id: str
    voice_script: str = ""
    audio_result: Optional[Dict[str, Any]] = None
    confidence: float = 0.7
    reasoning_chain: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = "active"


class ElevenLabsVoiceSynthesisAgent:
    AGENT_NAME = "elevenlabs_voice_synthesis"

    def __init__(self):
        self.observability = get_agent_observability()

    async def synthesize(
        self,
        user_id: str,
        candidate_name: str = "",
        job_title: str = "",
        company: str = "",
        match_score: int = 0,
        urgency: str = "normal",
        notification_message: str = "",
    ) -> VoiceSynthesisState:
        t0 = time.time()
        state = VoiceSynthesisState(
            synthesis_run_id=str(uuid.uuid4()),
            user_id=user_id,
        )

        try:
            if notification_message:
                state.voice_script = notification_message
            else:
                state.voice_script = self._generate_script(
                    candidate_name, job_title, company, match_score, urgency
                )

            from src.services.mcp.mcp_router import get_mcp_router
            router = get_mcp_router()
            state.audio_result = await router.dispatch(
                tool_name="generate_audio",
                arguments={
                    "candidate_name": candidate_name or user_id,
                    "job_title": job_title,
                    "company": company,
                    "match_score": match_score,
                    "urgency": urgency,
                },
                session_uid=state.synthesis_run_id,
            )

            state.reasoning_chain.append(f"Script: {state.voice_script[:100]}...")
            state.reasoning_chain.append(
                f"Audio: {state.audio_result.get('status', 'unknown')}"
            )
            state.status = "completed"
            self.observability.record_agent_execution(self.AGENT_NAME, "completed")
            self.observability.record_voice_call_latency("elevenlabs", time.time() - t0)
        except Exception as exc:
            state.errors.append(str(exc))
            state.status = "failed"
            self.observability.record_agent_execution(self.AGENT_NAME, "failed")

        self.observability.record_agent_latency(self.AGENT_NAME, time.time() - t0)
        return state

    def _generate_script(
        self, name: str, job_title: str, company: str, match_score: int, urgency: str
    ) -> str:
        parts = ["CareerOS opportunity alert."]
        if name:
            parts.append(f"Candidate: {name}.")
        if job_title:
            parts.append(f"Role: {job_title}.")
        if company:
            parts.append(f"Company: {company}.")
        parts.append(f"Match score: {match_score} percent.")
        parts.append(f"Urgency: {urgency}.")
        parts.append("Please review this opportunity immediately.")
        return " ".join(parts)


# ── Singleton ────────────────────────────────────────────────────────

_agent: Optional[ElevenLabsVoiceSynthesisAgent] = None


def get_elevenlabs_voice_synthesis_agent() -> ElevenLabsVoiceSynthesisAgent:
    global _agent
    if _agent is None:
        _agent = ElevenLabsVoiceSynthesisAgent()
    return _agent


def reset_elevenlabs_voice_synthesis_agent() -> None:
    global _agent
    _agent = None
