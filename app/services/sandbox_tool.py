"""Sandboxed Python code execution for Orkestra agents.

Provides a wrapped version of execute_python_code that runs inside an
isolated Docker container via agentscope-runtime BaseSandbox.

Falls back to the bare agentscope execute_python_code if:
  - agentscope-runtime is not installed
  - ORKESTRA_SANDBOX_URL is not set and Docker socket is unavailable

Usage in agent_factory.py:
    from app.services.sandbox_tool import get_code_execution_tool
    tool_fn = get_code_execution_tool()
    if tool_fn:
        toolkit.register_tool_function(tool_fn)
"""

import logging
import os

logger = logging.getLogger(__name__)

_SANDBOX_IMAGE = os.environ.get("ORKESTRA_SANDBOX_IMAGE", "python:3.12-slim")
_SANDBOX_URL = os.environ.get("ORKESTRA_SANDBOX_URL", "")  # remote sandbox service URL


def _try_build_sandboxed() -> object | None:
    """Attempt to build a sandboxed execute_python_code using agentscope-runtime.

    Returns a callable tool function on success, None if BaseSandbox is
    unavailable or cannot connect.
    """
    try:
        from agentscope_runtime import BaseSandbox  # type: ignore[import]
    except ImportError:
        logger.debug("agentscope-runtime not installed — BaseSandbox unavailable")
        return None

    try:
        sandbox_kwargs: dict = {"image": _SANDBOX_IMAGE}
        if _SANDBOX_URL:
            sandbox_kwargs["url"] = _SANDBOX_URL
            logger.info(f"Connecting to remote sandbox at {_SANDBOX_URL}")
        else:
            # Local Docker socket — check it is accessible
            import socket as _socket
            sock_path = "/var/run/docker.sock"
            if not os.path.exists(sock_path):
                logger.warning(
                    "Docker socket not found at /var/run/docker.sock. "
                    "Mount it in the API container or set ORKESTRA_SANDBOX_URL."
                )
                return None

        sandbox = BaseSandbox(**sandbox_kwargs)

        # Build a thin wrapper with the same signature as execute_python_code
        def execute_python_code_sandboxed(code: str, timeout: int = 30) -> str:
            """Execute Python code inside an isolated Docker sandbox.

            Args:
                code: Python source code to execute.
                timeout: Maximum execution time in seconds (default 30).

            Returns:
                Standard output produced by the code, or an error message.
            """
            try:
                result = sandbox.run(code=code, timeout=timeout)
                return result.stdout or result.output or "(no output)"
            except Exception as exc:
                return f"Sandbox execution error: {exc}"

        # Make the function introspectable so AgentScope can build its schema
        execute_python_code_sandboxed.__name__ = "execute_python_code"
        execute_python_code_sandboxed.__qualname__ = "execute_python_code"

        logger.info("BaseSandbox initialised — using sandboxed execute_python_code")
        return execute_python_code_sandboxed

    except Exception as exc:
        logger.warning(f"Failed to initialise BaseSandbox: {exc}")
        return None


def get_code_execution_tool() -> object | None:
    """Return the best available execute_python_code tool.

    Priority:
    1. BaseSandbox (agentscope-runtime) if available and Docker accessible
    2. Bare agentscope execute_python_code as fallback
    3. None if agentscope is not installed
    """
    sandboxed = _try_build_sandboxed()
    if sandboxed is not None:
        return sandboxed

    # Fallback: bare subprocess via agentscope
    try:
        from agentscope.tool import execute_python_code  # type: ignore[import]
        logger.info(
            "BaseSandbox unavailable — using bare execute_python_code "
            "(no container isolation)"
        )
        return execute_python_code
    except ImportError:
        logger.warning("agentscope not available — code execution tool unavailable")
        return None
