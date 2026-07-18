"""Phase 16 — MCP Validation API.

End-to-end trace endpoint for MCP workflow validation.
Twilio + ElevenLabs integration proof.

Phase 17.7 — Hardened: Uses get_current_user, no hardcoded demo_user.
"""

import time
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List

from src.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["mcp"])


class MCPStep(BaseModel):
    step: str
    provider: str
    status: str
    latency_ms: float = 0


class MCPTraceResponse(BaseModel):
    workflow: str
    steps: List[MCPStep]
    total_latency_ms: float
    status: str


@router.post("/test", response_model=MCPTraceResponse)
async def test_mcp_workflow(user: dict = Depends(get_current_user)):
    """Execute full MCP workflow trace: ElevenLabs voice → Twilio call."""
    t0 = time.time()
    steps: List[MCPStep] = []
    user_id = user["sub"]

    # Step 1: Voice script generation
    t1 = time.time()
    voice_result = {"status": "generated", "script": "Candidate match: 94% for Lead AI role at Netflix. Message: Great match detected."}
    try:
        from src.agents.elevenlabs_voice_synthesis_agent import get_elevenlabs_voice_synthesis_agent
        agent = get_elevenlabs_voice_synthesis_agent()
        result = await agent.synthesize(
            user_id=user_id,
            candidate_name="Candidate",
            job_title="Lead Deep Learning Infrastructure Architect",
            company="Netflix",
            match_score=94,
            urgency="high",
            notification_message="High-match opportunity at Netflix. 94% fit.",
        )
        voice_result = {
            "status": "synthesized",
            "voice_script": result.voice_script,
            "audio_status": result.audio_result.get("status", "unknown") if result.audio_result else "no_audio",
        }
    except Exception as e:
        voice_result = {"status": "error", "error": str(e)}

    steps.append(MCPStep(
        step="voice_synthesis",
        provider="elevenlabs",
        status="completed" if "error" not in str(voice_result).lower() else "failed",
        latency_ms=round((time.time() - t1) * 1000, 1),
    ))

    # Step 2: MCP Router dispatch
    t2 = time.time()
    dispatch_result = {"status": "routed"}
    try:
        from src.services.mcp.mcp_router import get_mcp_router
        router = get_mcp_router()
        result = await router.dispatch(
            tool_name="synthesize_speech",
            arguments={
                "candidate_name": "Demo Candidate",
                "job_title": "Lead Deep Learning Infrastructure Architect",
                "company": "Netflix",
                "match_score": 94,
                "urgency": "high",
            },
            session_uid="mcp_test_demo",
        )
        dispatch_result = result
    except Exception as e:
        dispatch_result = {"status": "error", "error": str(e)}

    steps.append(MCPStep(
        step="mcp_router_dispatch",
        provider="mcp_router",
        status="completed" if dispatch_result.get("status") != "error" else "failed",
        latency_ms=round((time.time() - t2) * 1000, 1),
    ))

    # Step 3: Twilio connectivity check
    t3 = time.time()
    twilio_result = {"status": "checked"}
    try:
        from src.services.mcp.twilio_mcp_service import get_twilio_mcp_service
        svc = get_twilio_mcp_service()
        twilio_result = await svc.check_health()
    except Exception as e:
        twilio_result = {"status": "unavailable", "error": str(e)}

    twilio_status = twilio_result.get("status", "unknown")
    steps.append(MCPStep(
        step="twilio_connectivity",
        provider="twilio",
        status="completed" if twilio_status == "ready" else ("blocked" if twilio_status == "blocked_by_credentials" else "unavailable"),
        latency_ms=round((time.time() - t3) * 1000, 1),
    ))

    total_ms = round((time.time() - t0) * 1000, 1)
    all_ok = all(s.status in ("completed", "available") for s in steps)

    return MCPTraceResponse(
        workflow="opportunity→voice→twilio",
        steps=steps,
        total_latency_ms=total_ms,
        status="completed" if all_ok else ("blocked" if twilio_status == "blocked_by_credentials" else "partial"),
    )
