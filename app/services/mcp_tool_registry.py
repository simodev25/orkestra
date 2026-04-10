"""Single source of truth for MCP tool resolution."""
import logging
import threading

logger = logging.getLogger(__name__)

_LOCAL_TOOLS: dict | None = None
_LOCAL_TOOLS_LOCK = threading.Lock()


def get_local_tools() -> dict:
    """Return mapping of MCP ID -> list of tool functions (thread-safe, lazy init)."""
    global _LOCAL_TOOLS
    if _LOCAL_TOOLS is not None:
        return _LOCAL_TOOLS

    with _LOCAL_TOOLS_LOCK:
        # Double-checked locking: prevents redundant initialization when multiple
        # threads pass the outer None-check simultaneously. A partial-object race
        # is not possible in CPython (STORE_GLOBAL is atomic under the GIL).
        if _LOCAL_TOOLS is not None:
            return _LOCAL_TOOLS

        tools: dict = {}

        try:
            from app.mcp_servers.document_parser import parse_document, classify_document
            tools["document_parser"] = [parse_document, classify_document]
        except ImportError:
            logger.warning("document_parser tools not available")

        try:
            from app.mcp_servers.consistency_checker import check_consistency, validate_fields
            tools["consistency_checker"] = [check_consistency, validate_fields]
        except ImportError:
            logger.warning("consistency_checker tools not available")

        try:
            from app.mcp_servers.search_engine import search_knowledge
            tools["search_engine"] = [search_knowledge]
        except ImportError:
            logger.warning("search_engine tools not available")

        try:
            from app.mcp_servers.weather import get_weather
            tools["weather"] = [get_weather]
        except ImportError:
            logger.warning("weather tools not available")

        _LOCAL_TOOLS = tools

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
