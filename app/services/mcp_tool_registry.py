"""Single source of truth for MCP tool resolution."""
import logging

logger = logging.getLogger(__name__)

_LOCAL_TOOLS: dict | None = None


def get_local_tools() -> dict:
    """Return mapping of MCP ID -> list of tool functions."""
    global _LOCAL_TOOLS
    if _LOCAL_TOOLS is not None:
        return _LOCAL_TOOLS

    _LOCAL_TOOLS = {}

    try:
        from app.mcp_servers.document_parser import parse_document, classify_document
        _LOCAL_TOOLS["document_parser"] = [parse_document, classify_document]
    except ImportError:
        logger.warning("document_parser tools not available")

    try:
        from app.mcp_servers.consistency_checker import check_consistency, validate_fields
        _LOCAL_TOOLS["consistency_checker"] = [check_consistency, validate_fields]
    except ImportError:
        logger.warning("consistency_checker tools not available")

    try:
        from app.mcp_servers.search_engine import search_knowledge
        _LOCAL_TOOLS["search_engine"] = [search_knowledge]
    except ImportError:
        logger.warning("search_engine tools not available")

    try:
        from app.mcp_servers.weather import get_weather
        _LOCAL_TOOLS["weather"] = [get_weather]
    except ImportError:
        logger.warning("weather tools not available")

    return _LOCAL_TOOLS


def get_tools_for_mcp(mcp_id: str) -> list | None:
    """Get tool functions for a given MCP ID, or None if not found locally."""
    return get_local_tools().get(mcp_id)


def get_mcp_id_for_tool(tool_func) -> str | None:
    """Return the MCP ID that owns *tool_func*, or None if not found in the local registry."""
    for mcp_id, tools in get_local_tools().items():
        if tool_func in tools:
            return mcp_id
    return None
