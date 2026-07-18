"""Phase 5 — MCP Tool Execution Layer Package.

Lazy exports for MCP router, governance, and observability.
"""


def __getattr__(name: str):
    if name == "mcp_router":
        from src.services.mcp.mcp_router import get_mcp_router
        return get_mcp_router()
    if name == "mcp_governance":
        from src.services.mcp.mcp_governance import get_mcp_governance
        return get_mcp_governance()
    if name == "mcp_observability":
        from src.services.mcp.mcp_observability import get_mcp_observability
        return get_mcp_observability()
    if name == "twilio_mcp_service":
        from src.services.mcp.twilio_mcp_service import get_twilio_mcp_service
        return get_twilio_mcp_service()
    if name == "elevenlabs_mcp_service":
        from src.services.mcp.elevenlabs_mcp_service import get_elevenlabs_mcp_service
        return get_elevenlabs_mcp_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
