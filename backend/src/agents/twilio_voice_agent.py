"""Phase 5 — Twilio Voice Agent.

Prepares and executes Twilio voice call through MCP Router.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.agent_observability import get_agent_observability


@dataclass
class TwilioVoiceState:
    call_run_id: str
    user_id: str
    phone_number: str = ""
    call_result: Optional[Dict[str, Any]] = None
    call_sid: Optional[str] = None
    confidence: float = 0.7
    reasoning_chain: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = "active"


class TwilioVoiceAgent:
    AGENT_NAME = "twilio_voice"

    def __init__(self):
        self.observability = get_agent_observability()

    async def execute_call(
        self,
        user_id: str,
        phone_number: str,
        audio_message: str,
        session_uid: str = "",
    ) -> TwilioVoiceState:
        t0 = time.time()
        state = TwilioVoiceState(
            call_run_id=str(uuid.uuid4()),
            user_id=user_id,
            phone_number=phone_number,
        )

        try:
            from src.services.mcp.mcp_router import get_mcp_router
            router = get_mcp_router()
            state.call_result = await router.dispatch(
                tool_name="make_call",
                arguments={
                    "phone_number": phone_number,
                    "audio_message": audio_message,
                },
                session_uid=session_uid or state.call_run_id,
            )

            state.call_sid = state.call_result.get("call_sid")
            call_status = state.call_result.get("status", "unknown")
            state.reasoning_chain.append(
                f"Call: {call_status} (SID: {state.call_sid})"
            )
            state.status = "completed" if call_status not in ("failed", "blocked_by_credentials") else call_status
            self.observability.record_agent_execution(self.AGENT_NAME, state.status)
            self.observability.record_voice_call_latency("twilio", time.time() - t0)
        except Exception as exc:
            state.errors.append(str(exc))
            state.status = "failed"
            self.observability.record_agent_execution(self.AGENT_NAME, "failed")

        self.observability.record_agent_latency(self.AGENT_NAME, time.time() - t0)
        return state


# ── Singleton ────────────────────────────────────────────────────────

_agent: Optional[TwilioVoiceAgent] = None


def get_twilio_voice_agent() -> TwilioVoiceAgent:
    global _agent
    if _agent is None:
        _agent = TwilioVoiceAgent()
    return _agent


def reset_twilio_voice_agent() -> None:
    global _agent
    _agent = None
