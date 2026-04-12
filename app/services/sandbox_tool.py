"""Sandboxed tool functions for Orkestra agents.

Maps agentscope built-in tool names to sandboxed equivalents using the
appropriate agentscope-runtime sandbox image:

  Tool                      Sandbox image
  ─────────────────────     ─────────────────────────────
  execute_python_code       BaseSandbox  (runtime-sandbox-base)
  execute_shell_command     BaseSandbox  (runtime-sandbox-base)
  view_text_file            FilesystemSandbox (runtime-sandbox-filesystem)
  write_text_file           FilesystemSandbox
  insert_text_file          FilesystemSandbox
  dashscope_*/openai_*      BaseSandbox  (API calls — no special isolation needed)

Falls back to the bare agentscope function when:
  - agentscope-runtime is not installed
  - Docker socket is not accessible
  - Sandbox probe fails (e.g. Docker Desktop / macOS DinD limitation)

Usage:
    from app.services.sandbox_tool import get_sandboxed_tool, get_code_execution_tool
"""

import logging
import os

logger = logging.getLogger(__name__)

# ── Sandbox availability cache ───────────────────────────────────────────────

_base_sandbox_ok: bool | None = None       # None = not yet tested
_filesystem_sandbox_ok: bool | None = None


def _docker_socket_accessible() -> bool:
    return os.path.exists("/var/run/docker.sock")


def _probe_base_sandbox() -> bool:
    """Return True if BaseSandbox can actually create and run a container."""
    global _base_sandbox_ok
    if _base_sandbox_ok is not None:
        return _base_sandbox_ok
    try:
        from agentscope_runtime.sandbox import BaseSandbox
        with BaseSandbox() as sb:
            result = sb.run_ipython_cell("print(1)")
            output = result.get("output", "") if isinstance(result, dict) else str(result)
            _base_sandbox_ok = "1" in output
    except Exception as exc:
        logger.warning(f"BaseSandbox probe failed: {exc}")
        _base_sandbox_ok = False
    return _base_sandbox_ok


def _probe_filesystem_sandbox() -> bool:
    """Return True if FilesystemSandbox can actually create and run a container."""
    global _filesystem_sandbox_ok
    if _filesystem_sandbox_ok is not None:
        return _filesystem_sandbox_ok
    try:
        from agentscope_runtime.sandbox.box.filesystem import FilesystemSandbox
        with FilesystemSandbox() as sb:
            result = sb.run_shell_command("echo ok")
            output = result.get("output", "") if isinstance(result, dict) else str(result)
            _filesystem_sandbox_ok = "ok" in output
    except Exception as exc:
        logger.warning(f"FilesystemSandbox probe failed: {exc}")
        _filesystem_sandbox_ok = False
    return _filesystem_sandbox_ok


# ── Sandboxed wrappers ───────────────────────────────────────────────────────

def _make_base_sandboxed(fn_name: str, bare_fn):
    """Wrap an agentscope tool so it runs inside a BaseSandbox container."""
    from agentscope_runtime.sandbox import BaseSandbox

    if fn_name == "execute_python_code":
        def execute_python_code(code: str, timeout: int = 30) -> str:
            """Execute Python code inside an isolated Docker sandbox (BaseSandbox)."""
            try:
                with BaseSandbox() as sb:
                    result = sb.run_ipython_cell(code)
                    if isinstance(result, dict):
                        output = result.get("output") or result.get("stdout") or ""
                        error  = result.get("error")  or result.get("stderr")  or ""
                        return (f"{output}\n[stderr]: {error}".strip()) if error else (output or "(no output)")
                    return str(result)
            except Exception as exc:
                return f"Sandbox execution error: {exc}"
        return execute_python_code

    elif fn_name == "execute_shell_command":
        def execute_shell_command(command: str, timeout: int = 30) -> str:
            """Execute a shell command inside an isolated Docker sandbox (BaseSandbox)."""
            try:
                with BaseSandbox() as sb:
                    result = sb.run_shell_command(command)
                    if isinstance(result, dict):
                        output = result.get("output") or result.get("stdout") or ""
                        error  = result.get("error")  or result.get("stderr")  or ""
                        return (f"{output}\n[stderr]: {error}".strip()) if error else (output or "(no output)")
                    return str(result)
            except Exception as exc:
                return f"Sandbox execution error: {exc}"
        return execute_shell_command

    else:
        # dashscope_* / openai_* — these are API calls; run via ipython cell in BaseSandbox
        import inspect
        src_params = ", ".join(
            p for p in inspect.signature(bare_fn).parameters if p != "self"
        )

        def _sandboxed(*args, **kwargs):
            """Run this tool inside a BaseSandbox container."""
            try:
                with BaseSandbox() as sb:
                    code = _build_tool_call_code(fn_name, args, kwargs)
                    result = sb.run_ipython_cell(code)
                    if isinstance(result, dict):
                        return result.get("output") or result.get("stdout") or str(result)
                    return str(result)
            except Exception as exc:
                return f"Sandbox execution error: {exc}"

        _sandboxed.__name__ = fn_name
        _sandboxed.__qualname__ = fn_name
        _sandboxed.__doc__ = getattr(bare_fn, "__doc__", "")
        return _sandboxed


def _build_tool_call_code(fn_name: str, args: tuple, kwargs: dict) -> str:
    """Build Python source code that calls agentscope.tool.<fn_name> with the given args."""
    import json
    parts = [f"from agentscope.tool import {fn_name}", ""]
    call_args = []
    for a in args:
        call_args.append(json.dumps(a))
    for k, v in kwargs.items():
        call_args.append(f"{k}={json.dumps(v)}")
    parts.append(f"result = {fn_name}({', '.join(call_args)})")
    parts.append("print(result)")
    return "\n".join(parts)


def _make_filesystem_sandboxed(fn_name: str, bare_fn):
    """Wrap a filesystem tool so it runs inside a FilesystemSandbox container."""
    from agentscope_runtime.sandbox.box.filesystem import FilesystemSandbox

    METHOD_MAP = {
        "view_text_file":   "read_file",
        "write_text_file":  "write_file",
        "insert_text_file": "edit_file",
    }

    sandbox_method = METHOD_MAP.get(fn_name)
    if sandbox_method is None:
        return bare_fn  # unknown — use bare

    if fn_name == "view_text_file":
        def view_text_file(file_path: str) -> str:
            """Read a text file inside an isolated FilesystemSandbox container."""
            try:
                with FilesystemSandbox() as sb:
                    result = sb.read_file(file_path)
                    if isinstance(result, dict):
                        return result.get("content") or result.get("output") or str(result)
                    return str(result)
            except Exception as exc:
                return f"Sandbox execution error: {exc}"
        return view_text_file

    elif fn_name == "write_text_file":
        def write_text_file(file_path: str, content: str) -> str:
            """Write content to a text file inside an isolated FilesystemSandbox container."""
            try:
                with FilesystemSandbox() as sb:
                    result = sb.write_file(file_path, content)
                    if isinstance(result, dict):
                        return result.get("output") or "Written successfully"
                    return str(result)
            except Exception as exc:
                return f"Sandbox execution error: {exc}"
        return write_text_file

    elif fn_name == "insert_text_file":
        def insert_text_file(file_path: str, content: str, insert_line: int = 0) -> str:
            """Insert text into a file inside an isolated FilesystemSandbox container."""
            try:
                with FilesystemSandbox() as sb:
                    result = sb.edit_file(file_path, content)
                    if isinstance(result, dict):
                        return result.get("output") or "Inserted successfully"
                    return str(result)
            except Exception as exc:
                return f"Sandbox execution error: {exc}"
        return insert_text_file

    return bare_fn


# ── Public API ───────────────────────────────────────────────────────────────

# Tools that need BaseSandbox (code/shell execution + API calls)
_BASE_SANDBOX_TOOLS = {
    "execute_python_code",
    "execute_shell_command",
    "dashscope_text_to_image",
    "dashscope_text_to_audio",
    "dashscope_image_to_text",
    "openai_text_to_image",
    "openai_text_to_audio",
    "openai_edit_image",
    "openai_create_image_variation",
    "openai_image_to_text",
    "openai_audio_to_text",
}

# Tools that need FilesystemSandbox
_FILESYSTEM_SANDBOX_TOOLS = {
    "view_text_file",
    "write_text_file",
    "insert_text_file",
}


def get_sandboxed_tool(tool_name: str):
    """Return the best available version of a built-in tool.

    Priority:
      1. Sandboxed version (appropriate sandbox image) if Docker socket + probe pass
      2. Bare agentscope function as fallback
      3. None if agentscope is not installed
    """
    try:
        import agentscope.tool as _as_tools
        bare_fn = getattr(_as_tools, tool_name, None)
    except ImportError:
        logger.warning("agentscope not available")
        return None

    if bare_fn is None:
        logger.warning(f"Built-in tool '{tool_name}' not found in agentscope.tool")
        return None

    if not _docker_socket_accessible():
        logger.info(f"Docker socket absent — using bare {tool_name}")
        return bare_fn

    if tool_name in _BASE_SANDBOX_TOOLS:
        try:
            from agentscope_runtime.sandbox import BaseSandbox  # noqa: F401
        except ImportError:
            logger.debug("agentscope-runtime BaseSandbox unavailable")
            return bare_fn

        if _probe_base_sandbox():
            logger.info(f"Using sandboxed {tool_name} (BaseSandbox)")
            return _make_base_sandboxed(tool_name, bare_fn)
        else:
            logger.warning(
                f"BaseSandbox probe failed — using bare {tool_name} (no container isolation)"
            )
            return bare_fn

    elif tool_name in _FILESYSTEM_SANDBOX_TOOLS:
        try:
            from agentscope_runtime.sandbox.box.filesystem import FilesystemSandbox  # noqa: F401
        except ImportError:
            logger.debug("agentscope-runtime FilesystemSandbox unavailable")
            return bare_fn

        if _probe_filesystem_sandbox():
            logger.info(f"Using sandboxed {tool_name} (FilesystemSandbox)")
            return _make_filesystem_sandboxed(tool_name, bare_fn)
        else:
            logger.warning(
                f"FilesystemSandbox probe failed — using bare {tool_name} (no container isolation)"
            )
            return bare_fn

    # Unknown tool — return bare
    return bare_fn


def get_code_execution_tool():
    """Convenience wrapper: return sandboxed (or bare) execute_python_code.

    Kept for backwards compatibility with agent_factory.py.
    """
    return get_sandboxed_tool("execute_python_code")
