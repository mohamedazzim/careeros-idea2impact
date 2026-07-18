import pytest
import pytest_asyncio
import os
from src.services.mcp_client import run_elevenlabs_mcp, run_twilio_mcp, execute_mcp_opportunity_workflow, mcp_pool

pytestmark = pytest.mark.skip(reason="MCP tests require running subprocess servers")

@pytest_asyncio.fixture(autouse=True)
async def cleanup_mcp_pool():
    yield
    await mcp_pool.close_all()

@pytest.mark.asyncio
async def test_elevenlabs_mcp():
    os.environ["MOCK_MCP"] = "false"
    result = await run_elevenlabs_mcp(
        candidate_name="Alice Candidate",
        job_title="Backend Dev",
        company="TechCorp",
        match_score=95,
        urgency="Critical"
    )
    assert result["status"] in ("mock", "success")

@pytest.mark.asyncio
async def test_twilio_mcp():
    os.environ["MOCK_MCP"] = "false"
    result = await run_twilio_mcp(
        phone_number="+15555555555",
        audio_message="Playing generated asset: elevenlabs_audio.mp3"
    )
    assert result["status"] in ("mock", "queued")

@pytest.mark.asyncio
async def test_execute_workflow():
    os.environ["MOCK_MCP"] = "false"
    result = await execute_mcp_opportunity_workflow(
        candidate_name="Bob Tester",
        job_title="QA",
        company="Quality Inc",
        match_score=88,
        urgency="High",
        phone_number="+15550000000"
    )
    assert "elevenlabs_mcp_result" in result
    assert "twilio_mcp_result" in result

