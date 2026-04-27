"""Target agent runner — wraps real AgentScope ReActAgent execution into a clean interface."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class TargetAgentResult:
    status: str  # "completed", "failed", "timeout"
    final_output: str
    duration_ms: int
    iteration_count: int
    message_history: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    error: str | None = None
    # Runtime introspection (populated after agent creation)
    connected_mcps: list[dict] = field(default_factory=list)  # [{id, url, tools: [name,...]}]
    discovered_tools: list[str] = field(default_factory=list)  # flat list of all tool names registered


def _build_execution_events(message_history: list[dict]) -> list[dict]:
    """Convert agent message history into structured test events.

    - Messages with role "tool"      -> event_type "tool_call_completed"
    - Messages with role "assistant" -> event_type "iteration"
    """
    events = []
    for i, msg in enumerate(message_history):
        role = msg.get("role", "unknown")
        if role == "tool":
            events.append(
                {
                    "event_type": "tool_call_completed",
                    "phase": "runtime",
                    "index": i,
                    "name": msg.get("name", "unknown"),
                    "content": msg.get("content", ""),
                }
            )
        elif role == "assistant":
            events.append(
                {
                    "event_type": "iteration",
                    "phase": "runtime",
                    "index": i,
                    "content": msg.get("content", ""),
                }
            )
    return events


async def run_target_agent(
    db: AsyncSession,
    agent_id: str,
    agent_version: str | None,
    input_prompt: str,
    allowed_tools: list[str] | None = None,
    timeout_seconds: int = 120,
    max_iterations: int = 5,
    run_id: str | None = None,
) -> TargetAgentResult:
    """Execute a real AgentScope ReActAgent and return structured results.

    Steps:
    1. Load agent definition from registry.
    2. Resolve local tools for the agent.
    3. Create the AgentScope ReActAgent.
    4. Run the agent with a timeout.
    5. Extract message history from agent memory.
    6. Return a TargetAgentResult.
    """
    from app.services import agent_registry_service
    from app.services.agent_factory import create_agentscope_agent, get_tools_for_agent
    from agentscope.message import Msg

    # ── 1. Load agent definition ──────────────────────────────────────────
    try:
        agent_def = await agent_registry_service.get_agent(db, agent_id)
    except Exception as exc:
        logger.warning(f"Failed to load agent definition '{agent_id}': {exc}")
        return TargetAgentResult(
            status="failed",
            final_output="",
            duration_ms=0,
            iteration_count=0,
            error=f"Could not load agent definition: {exc}",
        )

    if agent_def is None:
        return TargetAgentResult(
            status="failed",
            final_output="",
            duration_ms=0,
            iteration_count=0,
            error=f"Agent '{agent_id}' not found",
        )

    # ── 2. Resolve tools ──────────────────────────────────────────────────
    try:
        tools = get_tools_for_agent(agent_def)
    except Exception as exc:
        logger.warning(f"Failed to resolve tools for agent '{agent_id}': {exc}")
        tools = []

    # ── 3. Create the AgentScope agent ────────────────────────────────────
    # Use the test lab config model as fallback so the target agent runs on the
    # same model as the orchestrator (gpt-oss:20b-cloud by default), not the
    # platform default (mistral).
    try:
        from app.services.test_lab.execution_engine import _make_model, _make_formatter
        tl_model = _make_model()
        tl_formatter = _make_formatter()
    except Exception as exc:
        logger.warning(f"Could not load test lab model config: {exc}")
        tl_model = None
        tl_formatter = None

    try:
        react_agent = await create_agentscope_agent(
            agent_def,
            db=db,
            tools_to_register=tools,
            max_iters=max_iterations,
            fallback_model=tl_model,
            fallback_formatter=tl_formatter,
            test_run_id=run_id,
        )
    except Exception as exc:
        from app.services.agent_factory import _format_mcp_exception
        readable_err = _format_mcp_exception(exc)
        logger.warning(f"Agent creation raised an exception for '{agent_id}': {readable_err}")
        return TargetAgentResult(
            status="failed",
            final_output="",
            duration_ms=0,
            iteration_count=0,
            error=f"Agent creation failed: {readable_err}",
        )

    if react_agent is None:
        return TargetAgentResult(
            status="failed",
            final_output="",
            duration_ms=0,
            iteration_count=0,
            error="Agent creation failed (LLM or AgentScope unavailable)",
        )

    # ── 3b. Introspect the freshly created agent for trace metadata ──────
    connected_mcps: list[dict] = list(getattr(react_agent, "_connected_mcps", []) or [])
    discovered_tools: list[str] = []
    try:
        toolkit = getattr(react_agent, "toolkit", None)
        if toolkit is not None:
            # AgentScope Toolkit exposes its tools via get_json_schemas() which returns list of schemas
            try:
                schemas = toolkit.get_json_schemas()
                for sch in schemas or []:
                    fn = (sch or {}).get("function") if isinstance(sch, dict) else None
                    if isinstance(fn, dict) and fn.get("name"):
                        discovered_tools.append(fn["name"])
            except Exception:
                pass
            # Fallback: walk the private _tools dict if available
            if not discovered_tools:
                tools_dict = getattr(toolkit, "_tools", None) or getattr(toolkit, "tools", None)
                if isinstance(tools_dict, dict):
                    discovered_tools.extend(list(tools_dict.keys()))
    except Exception as exc:
        logger.debug(f"Could not introspect toolkit for agent '{agent_id}': {exc}")

    # ── 4. Run the agent with timeout ─────────────────────────────────────
    user_msg = Msg("user", input_prompt, "user")
    t0 = time.time()
    effective_timeout_seconds = max(timeout_seconds, 120)

    try:
        try:
            await asyncio.wait_for(
                react_agent(user_msg),
                timeout=effective_timeout_seconds,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - t0) * 1000)
            logger.warning(f"Agent '{agent_id}' timed out after {effective_timeout_seconds}s")
            return TargetAgentResult(
                status="timeout",
                final_output="",
                duration_ms=duration_ms,
                iteration_count=0,
                error=f"Timed out after {effective_timeout_seconds}s",
                connected_mcps=connected_mcps,
                discovered_tools=discovered_tools,
            )
        except Exception as exc:
            duration_ms = int((time.time() - t0) * 1000)
            # Unwrap ExceptionGroup / TaskGroup to surface the real sub-exception
            from app.services.agent_factory import _format_mcp_exception
            readable_err = _format_mcp_exception(exc)
            logger.warning(f"Agent '{agent_id}' raised an error during execution: {readable_err}")
            # Try to salvage partial memory so assertions have something to evaluate
            partial_output = ""
            partial_history: list[dict] = []
            try:
                msgs = await react_agent.memory.get_memory()
                for m in msgs:
                    role = getattr(m, "role", "")
                    name = getattr(m, "name", "")
                    text = m.get_text_content() if hasattr(m, "get_text_content") else ""
                    partial_history.append({"role": role, "name": name, "content": (text or "")[:5000]})
                for m in reversed(msgs):
                    if getattr(m, "role", "") == "assistant":
                        t = m.get_text_content() if hasattr(m, "get_text_content") else ""
                        if t and t.strip():
                            partial_output = t[:10000]
                            break
            except Exception:
                pass
            return TargetAgentResult(
                status="failed",
                final_output=partial_output,
                duration_ms=duration_ms,
                iteration_count=len(partial_history),
                message_history=partial_history,
                error=f"Execution error: {readable_err}",
                connected_mcps=connected_mcps,
                discovered_tools=discovered_tools,
            )
    finally:
        # Explicitly close MCP/httpx async clients while loop is alive.
        from app.services.agent_factory import close_agentscope_agent_resources
        await close_agentscope_agent_resources(react_agent)

    duration_ms = int((time.time() - t0) * 1000)

    # ── 5. Extract message history from agent memory ──────────────────────
    message_history: list[dict] = []
    tool_calls: list[dict] = []
    final_output = ""

    def _bget(block, key, default=""):
        if isinstance(block, dict):
            return block.get(key, default)
        return getattr(block, key, default)

    def _extract_tool_output(output_field) -> str:
        """Extract readable text from a tool_result output field."""
        if isinstance(output_field, list):
            parts = [item.get("text", str(item)) if isinstance(item, dict) else str(item) for item in output_field]
            return "\n".join(parts)
        return str(output_field)

    # FIFO queue: tool_use blocks waiting to be paired with their tool_result
    _pending_tcs: list[dict] = []

    try:
        msgs = await react_agent.memory.get_memory()
        for m in msgs:
            role = getattr(m, "role", "")
            name = getattr(m, "name", "")
            text = m.get_text_content() if hasattr(m, "get_text_content") else ""
            content_blocks = getattr(m, "content", None)
            _result_assigned = False

            if isinstance(content_blocks, list):
                for block in content_blocks:
                    bt = _bget(block, "type", "")
                    if bt == "tool_use":
                        tc = {
                            "tool_name": _bget(block, "name", "unknown"),
                            "tool_input": str(_bget(block, "raw_input", "") or _bget(block, "input", ""))[:500],
                            "tool_output": "",
                        }
                        tool_calls.append(tc)
                        _pending_tcs.append(tc)
                    elif bt == "tool_result":
                        out = _extract_tool_output(_bget(block, "output", []))
                        if _pending_tcs:
                            _pending_tcs.pop(0)["tool_output"] = out[:800]
                        _result_assigned = True
                if not text:
                    parts = [str(_bget(b, "text", b))[:500] for b in content_blocks]
                    text = "\n".join(parts)
            elif isinstance(content_blocks, dict):
                if content_blocks.get("type") == "tool_result":
                    out = _extract_tool_output(content_blocks.get("output", []))
                    if _pending_tcs:
                        _pending_tcs.pop(0)["tool_output"] = out[:800]
                    _result_assigned = True
                elif not text:
                    text = str(content_blocks)
            elif isinstance(content_blocks, str) and not text:
                text = content_blocks

            # Fallback for system messages: try ast.literal_eval on text string repr
            if not _result_assigned and role == "system" and _pending_tcs:
                import ast as _ast
                raw = (text or "").strip()
                if not raw and isinstance(content_blocks, str):
                    raw = content_blocks.strip()
                if raw.startswith("{"):
                    try:
                        parsed = _ast.literal_eval(raw)
                        if isinstance(parsed, dict) and parsed.get("type") == "tool_result":
                            out = _extract_tool_output(parsed.get("output", []))
                            _pending_tcs.pop(0)["tool_output"] = out[:800]
                            _result_assigned = True
                    except Exception:
                        pass
                if not _result_assigned and raw:
                    # Last resort: use raw system message text as output
                    _pending_tcs.pop(0)["tool_output"] = raw[:800]

            message_history.append({"role": role, "name": name, "content": text[:5000]})

        # Find the last assistant message with REAL text content (skip tool_use-only messages)
        if msgs:
            for m in reversed(msgs):
                role = getattr(m, "role", "")
                if role != "assistant":
                    continue
                text = ""
                if hasattr(m, "get_text_content"):
                    text = m.get_text_content() or ""
                if not text:
                    # Extract text blocks directly
                    blocks = getattr(m, "content", None)
                    if isinstance(blocks, list):
                        text_parts = []
                        for b in blocks:
                            bt = _bget(b, "type", "")
                            if bt == "text":
                                text_parts.append(str(_bget(b, "text", "")))
                            elif bt == "thinking":
                                # Include thinking as last resort
                                text_parts.append(str(_bget(b, "thinking", "")))
                        text = "\n".join(p for p in text_parts if p).strip()
                    elif isinstance(blocks, str):
                        text = blocks

                if text and text.strip():
                    final_output = text[:10000]
                    break

            # Fallback: if no assistant text found, use the last message of any role
            if not final_output and msgs:
                last = msgs[-1]
                final_output = (
                    (last.get_text_content() if hasattr(last, "get_text_content") else "")
                    or str(getattr(last, "content", ""))
                )[:5000]
    except Exception as exc:
        logger.warning(f"Failed to extract memory for agent '{agent_id}': {exc}")

    # ── 6. Return result ──────────────────────────────────────────────────
    return TargetAgentResult(
        status="completed",
        final_output=final_output,
        duration_ms=duration_ms,
        iteration_count=len(message_history),
        message_history=message_history,
        tool_calls=tool_calls,
        connected_mcps=connected_mcps,
        discovered_tools=discovered_tools,
    )
