"""Tests for MCP compatibility patches (structuredContent + ExceptionGroup)."""

import pytest


def test_structured_content_list_normalised():
    """structuredContent list should be wrapped in {"items": [...]}."""
    from app.services.mcp_compat import apply_mcp_patches
    apply_mcp_patches()

    from mcp.types import CallToolResult
    r = CallToolResult.model_validate({
        "content": [{"type": "text", "text": "ok"}],
        "structuredContent": [{"ID": "1"}, {"ID": "2"}],
    })
    assert r.structuredContent == {"items": [{"ID": "1"}, {"ID": "2"}]}


def test_structured_content_dict_unchanged():
    """structuredContent dict should pass through unchanged."""
    from app.services.mcp_compat import apply_mcp_patches
    apply_mcp_patches()

    from mcp.types import CallToolResult
    r = CallToolResult.model_validate({
        "content": [{"type": "text", "text": "ok"}],
        "structuredContent": {"data": "value"},
    })
    assert r.structuredContent == {"data": "value"}


def test_structured_content_none():
    """Missing structuredContent should remain None."""
    from app.services.mcp_compat import apply_mcp_patches
    apply_mcp_patches()

    from mcp.types import CallToolResult
    r = CallToolResult.model_validate({
        "content": [{"type": "text", "text": "ok"}],
    })
    assert r.structuredContent is None


def test_unwrap_exception_group():
    """_unwrap_exception_group should extract inner exception messages."""
    from app.services.mcp_compat import _unwrap_exception_group

    inner = ValueError("actual error message")
    eg = ExceptionGroup("unhandled errors in a TaskGroup", [inner])
    result = _unwrap_exception_group(eg)
    assert "actual error message" in result
    assert "ValueError" in result


def test_mcp_tool_function_patched():
    """MCPToolFunction should have the ExceptionGroup patch marker."""
    from app.services.mcp_compat import apply_mcp_patches
    apply_mcp_patches()

    from agentscope.mcp._mcp_function import MCPToolFunction
    assert getattr(MCPToolFunction, "_orkestra_eg_patched", False) is True


def test_patches_idempotent():
    """Calling apply_mcp_patches() multiple times should be safe."""
    from app.services.mcp_compat import apply_mcp_patches
    apply_mcp_patches()
    apply_mcp_patches()  # Should not raise or double-patch
