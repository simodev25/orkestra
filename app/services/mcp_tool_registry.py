"""MCP tool registry — local Python tools removed, all tools come from remote MCP servers."""


def get_local_tools() -> dict:
    """No local tools — all MCP tools are resolved from remote servers."""
    return {}


def get_tools_for_mcp(mcp_id: str) -> list | None:
    """Returns None — local tool registry is empty."""
    return None


def get_mcp_id_for_tool(tool_func) -> str | None:
    """Returns None — no local tools registered."""
    return None
