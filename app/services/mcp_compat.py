"""MCP SDK compatibility patches for Orkestra.

Addresses two runtime issues with MCP tool execution:

1. **structuredContent list→dict normalization**: Some MCP servers (e.g. Obot
   Word) return ``structuredContent`` as a JSON array, but the MCP SDK's
   ``CallToolResult`` Pydantic model expects a dict.  We add a
   ``model_validator`` that wraps bare lists in ``{"items": [...]}``.

2. **ExceptionGroup unwrapping in tool calls**: AgentScope's
   ``MCPToolFunction.__call__`` runs inside an asyncio TaskGroup.  When the
   downstream call fails, the exception is wrapped in an ``ExceptionGroup``
   whose ``str()`` is the opaque *"unhandled errors in a TaskGroup"* message.
   We monkey-patch ``MCPToolFunction.__call__`` to catch and unwrap these
   so the agent (and logs) see the real error.

Both patches are idempotent — calling ``apply_mcp_patches()`` multiple times
is safe.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_patches_applied = False


def _unwrap_exception_group(exc: BaseException) -> str:
    """Recursively unwrap BaseExceptionGroup to a readable string."""
    if hasattr(exc, "exceptions"):
        parts = []
        for inner in exc.exceptions:  # type: ignore[attr-defined]
            parts.append(_unwrap_exception_group(inner))
        return f"[{type(exc).__name__}] " + " | ".join(parts)
    return f"{type(exc).__name__}: {exc}"


def apply_mcp_patches() -> None:
    """Apply all MCP compatibility patches.  Idempotent."""
    global _patches_applied
    if _patches_applied:
        return
    _patches_applied = True

    _patch_structured_content()
    _patch_mcp_tool_function_call()
    logger.info("MCP compatibility patches applied")


# ── Patch 1: structuredContent list→dict ──────────────────────────────────────


def _patch_structured_content() -> None:
    """Add a model_validator to CallToolResult that normalises list→dict."""
    try:
        from mcp.types import CallToolResult
    except ImportError:
        return

    # Guard: don't double-patch
    if getattr(CallToolResult, "_orkestra_sc_patched", False):
        return

    original_validate = CallToolResult.model_validate

    @classmethod  # type: ignore[misc]
    def _patched_model_validate(
        cls: type,
        obj: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if isinstance(obj, dict) and "structuredContent" in obj:
            sc = obj["structuredContent"]
            if isinstance(sc, list):
                obj = {**obj, "structuredContent": {"items": sc}}
        return original_validate.__func__(cls, obj, *args, **kwargs)  # type: ignore[attr-defined]

    CallToolResult.model_validate = _patched_model_validate  # type: ignore[assignment]
    CallToolResult._orkestra_sc_patched = True  # type: ignore[attr-defined]
    logger.debug("Patched CallToolResult.model_validate for structuredContent list→dict")


# ── Patch 2: ExceptionGroup unwrapping in MCPToolFunction.__call__ ────────────


def _patch_mcp_tool_function_call() -> None:
    """Monkey-patch MCPToolFunction.__call__ to unwrap ExceptionGroup."""
    try:
        from agentscope.mcp._mcp_function import MCPToolFunction
    except ImportError:
        return

    if getattr(MCPToolFunction, "_orkestra_eg_patched", False):
        return

    _original_call = MCPToolFunction.__call__

    async def _patched_call(self: Any, **kwargs: Any) -> Any:
        try:
            return await _original_call(self, **kwargs)
        except BaseException as exc:
            # If it's an ExceptionGroup, unwrap and re-raise with a clear message
            if hasattr(exc, "exceptions"):
                readable = _unwrap_exception_group(exc)
                raise RuntimeError(
                    f"MCP tool '{self.name}' failed: {readable}"
                ) from exc
            raise

    MCPToolFunction.__call__ = _patched_call  # type: ignore[assignment]
    MCPToolFunction._orkestra_eg_patched = True  # type: ignore[attr-defined]
    logger.debug("Patched MCPToolFunction.__call__ for ExceptionGroup unwrapping")
