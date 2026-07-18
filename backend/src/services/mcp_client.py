import sys
import os
import json
import logging
import asyncio
from typing import Dict, Any

from src.observability.tracing import trace_async

logger = logging.getLogger(__name__)

try:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
    MCP_CLIENT_AVAILABLE = True
except Exception as exc:  # pragma: no cover - runtime dependency guard
    ClientSession = None  # type: ignore[assignment]
    stdio_client = None  # type: ignore[assignment]
    StdioServerParameters = None  # type: ignore[assignment]
    MCP_CLIENT_AVAILABLE = False
    MCP_CLIENT_IMPORT_ERROR = exc

class MCPConnectionPool:
    def __init__(self):
        self._pools = {}
        self._locks = {}

    async def get_connection(self, server_name: str, server_path: str):
        if not MCP_CLIENT_AVAILABLE:
            raise RuntimeError(f"mcp_dependency_missing:{MCP_CLIENT_IMPORT_ERROR}")

        if server_name not in self._locks:
            self._locks[server_name] = asyncio.Lock()
            
        async with self._locks[server_name]:
            if server_name not in self._pools:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUNBUFFERED"] = "1"
                
                server_params = StdioServerParameters(
                    command=sys.executable,
                    args=[server_path],
                    env=env
                )
                
                # Context managers manually entered to keep connection alive
                client_ctx = stdio_client(server_params)
                read_stream, write_stream = await client_ctx.__aenter__()
                
                session_ctx = ClientSession(read_stream, write_stream)
                session = await session_ctx.__aenter__()
                
                await asyncio.wait_for(session.initialize(), timeout=15.0)
                
                self._pools[server_name] = {
                    "client_ctx": client_ctx,
                    "session_ctx": session_ctx,
                    "session": session
                }
                
            return self._pools[server_name]["session"]

    async def close_all(self):
        for name, pool in self._pools.items():
            try:
                await pool["session_ctx"].__aexit__(None, None, None)
                await pool["client_ctx"].__aexit__(None, None, None)
            except BaseException as e:
                logger.warning(f"Error closing MCP pool for {name}: {e}")
        self._pools.clear()

mcp_pool = MCPConnectionPool()

@trace_async("run_elevenlabs_mcp")
async def run_elevenlabs_mcp(
    candidate_name: str,
    job_title: str,
    company: str,
    match_score: int,
    urgency: str,
    message: str = "",
    language: str = "english",
    retries: int = 3,
) -> Dict[str, Any]:
    """
    Connects to the ElevenLabs MCP server via stdio using a connection pool, avoiding subprocess spawn deadlocks.
    """
    server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mcp_servers', 'elevenlabs_server.py'))
    
    last_error = None
    for attempt in range(retries):
        try:
            session = await mcp_pool.get_connection("elevenlabs", server_path)
            
            result = await asyncio.wait_for(
                session.call_tool(
                    "generate_audio",
                    arguments={
                    "candidate_name": candidate_name,
                    "job_title": job_title,
                    "company": company,
                    "match_score": match_score,
                    "urgency": urgency,
                    "message": message,
                    "language": language,
                }
            ),
            timeout=15.0
        )
            
            content = result.content[0].text
            return json.loads(content)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout on ElevenLabs MCP attempt {attempt+1}/{retries}")
            last_error = "TimeoutError"
            await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Error on ElevenLabs MCP attempt {attempt+1}/{retries}: {str(e)}")
            last_error = str(e)
            # On generic error, force reset connection
            if "elevenlabs" in mcp_pool._pools:
                del mcp_pool._pools["elevenlabs"]
            await asyncio.sleep(1)
            
    raise RuntimeError(f"ElevenLabs MCP completely failed after {retries} retries. Last error: {last_error}")

async def _run_twilio_tool(tool_name: str, arguments: Dict[str, Any], retries: int = 3) -> Dict[str, Any]:
    """
    Connects to the Twilio MCP server via connection pool for graceful handling and performance.
    """
    server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mcp_servers', 'twilio_server.py'))
    
    last_error = None
    for attempt in range(retries):
        try:
            session = await mcp_pool.get_connection("twilio", server_path)
            
            result = await asyncio.wait_for(
                session.call_tool(
                    tool_name,
                    arguments=arguments,
                ),
                timeout=15.0
            )
            
            content = result.content[0].text
            return json.loads(content)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout on Twilio MCP attempt {attempt+1}/{retries}")
            last_error = "TimeoutError"
            await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Error on Twilio MCP attempt {attempt+1}/{retries}: {str(e)}")
            last_error = str(e)
            if "twilio" in mcp_pool._pools:
                del mcp_pool._pools["twilio"]
            await asyncio.sleep(1)
            
    raise RuntimeError(f"Twilio MCP completely failed after {retries} retries. Last error: {last_error}")


@trace_async("run_twilio_mcp")
async def run_twilio_mcp(phone_number: str, audio_message: str, retries: int = 3) -> Dict[str, Any]:
    return await _run_twilio_tool(
        "make_call",
        {
            "phone_number": phone_number,
            "audio_message": audio_message,
        },
        retries=retries,
    )


@trace_async("run_twilio_sms_mcp")
async def run_twilio_sms_mcp(phone_number: str, message: str, retries: int = 3) -> Dict[str, Any]:
    return await _run_twilio_tool(
        "send_sms",
        {
            "phone_number": phone_number,
            "message": message,
        },
        retries=retries,
    )

from langsmith import traceable

@trace_async("execute_mcp_opportunity_workflow")
@traceable(name="execute_mcp_opportunity_workflow")
async def execute_mcp_opportunity_workflow(
    candidate_name: str, 
    job_title: str, 
    company: str, 
    match_score: int, 
    urgency: str,
    phone_number: str,
    message: str = "",
    language: str = "english",
) -> Dict[str, Any]:
    """
    Executes the MCP pipeline for Opportunity Alert routing mapping 
    ElevenLabs Audio Generation into Twilio Call Injection securely via Tool selections.
    """
    elevenlabs_result = await run_elevenlabs_mcp(
        candidate_name=candidate_name,
        job_title=job_title,
        company=company,
        match_score=match_score,
        urgency=urgency,
        message=message,
        language=language,
    )
    
    audio_asset_ref = elevenlabs_result.get("audio_asset_reference", "default.mp3")
    
    twilio_result = await run_twilio_mcp(
        phone_number=phone_number,
        audio_message=f"Playing generated asset: {audio_asset_ref}"
    )
    
    return {
        "elevenlabs_mcp_result": elevenlabs_result,
        "twilio_mcp_result": twilio_result
    }
