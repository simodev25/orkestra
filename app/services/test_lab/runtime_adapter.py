# app/services/test_lab/runtime_adapter.py
"""Runtime adapter — wraps AgentScope ReActAgent execution and captures events via hooks."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("orkestra.test_lab.runtime")


class RuntimeEventCollector:
    """Collects and persists events during agent execution via AgentScope hooks."""

    def __init__(self, run_id: str, db=None):
        self.run_id = run_id
        self.db = db
        self.events: list[dict] = []
        self.iteration_count = 0
        self._iter_start: float | None = None
        self._llm_start: float | None = None
        self._tool_start: float | None = None

    def _emit(self, event_type: str, phase: str = "runtime", message: str = "", details: dict | None = None, duration_ms: int | None = None):
        evt = {
            "run_id": self.run_id,
            "event_type": event_type,
            "phase": phase,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
        }
        self.events.append(evt)

        # Persist to DB immediately for SSE streaming (separate sync connection)
        if self.db:
            try:
                from app.core.config import get_settings
                from sqlalchemy import create_engine, text
                import json as _json
                settings = get_settings()
                sync_url = settings.DATABASE_URL.replace("asyncpg", "psycopg2").replace("+asyncpg", "")
                engine = create_engine(sync_url)
                with engine.connect() as conn:
                    conn.execute(text(
                        "INSERT INTO test_run_events (id, run_id, event_type, phase, message, details, timestamp, duration_ms, created_at, updated_at) "
                        "VALUES (:id, :run_id, :etype, :phase, :msg, :details, NOW(), :dur, NOW(), NOW())"
                    ), {
                        "id": f"evt_{datetime.now(timezone.utc).strftime('%H%M%S%f')[:12]}",
                        "run_id": self.run_id, "etype": event_type, "phase": phase,
                        "msg": message, "details": _json.dumps(details) if details else None, "dur": duration_ms,
                    })
                    conn.commit()
                engine.dispose()
            except Exception:
                pass

    # ── AgentScope hooks ───────────────────────────────────

    async def on_pre_reasoning(self, agent, *args, **kwargs):
        self.iteration_count += 1
        self._iter_start = time.time()
        self._llm_start = time.time()
        self._emit("agent_iteration_started", message=f"Iteration {self.iteration_count}")
        self._emit("llm_request_started", message=f"LLM inference iteration {self.iteration_count}")

    async def on_post_reasoning(self, agent, *args, **kwargs):
        llm_ms = int((time.time() - self._llm_start) * 1000) if self._llm_start else 0

        # Get last message from agent memory (the LLM response)
        llm_text = ""
        tool_calls = []

        try:
            msgs = await agent.memory.get_memory()
            if msgs:
                last_msg = msgs[-1]
                content = getattr(last_msg, "content", None)

                def bget(block, key, default=""):
                    if isinstance(block, dict):
                        return block.get(key, default)
                    return getattr(block, key, default)

                if isinstance(content, list):
                    for block in content:
                        btype = bget(block, "type", "")
                        if btype in ("thinking", "text"):
                            llm_text += str(bget(block, "text", ""))[:1000] + "\n"
                        elif btype == "tool_use":
                            name = bget(block, "name", "unknown")
                            self._last_tool_name = name
                            raw_input = bget(block, "raw_input", "") or str(bget(block, "input", ""))
                            tool_calls.append({
                                "tool_name": name,
                                "tool_input": str(raw_input)[:500],
                            })
                elif isinstance(content, str):
                    llm_text = content[:2000]

                if not llm_text:
                    llm_text = (last_msg.get_text_content() or "") if hasattr(last_msg, "get_text_content") else ""
        except Exception as e:
            logger.warning(f"Failed to extract from memory: {e}")

        self._emit("llm_request_completed", message=f"LLM responded", duration_ms=llm_ms, details={
            "llm_output": llm_text.strip()[:2000] if llm_text.strip() else None,
            "tool_calls_planned": tool_calls if tool_calls else None,
        })

        for tc in tool_calls:
            self._emit("tool_call_started", message=f"Calling MCP tool: {tc['tool_name']}", details=tc)

    async def on_pre_acting(self, agent, *args, **kwargs):
        self._tool_start = time.time()

    async def on_post_acting(self, agent, *args, **kwargs):
        tool_ms = int((time.time() - self._tool_start) * 1000) if self._tool_start else 0
        iter_ms = int((time.time() - self._iter_start) * 1000) if self._iter_start else 0

        def bget(block, key, default=""):
            if isinstance(block, dict):
                return block.get(key, default)
            return getattr(block, key, default)

        tool_name = getattr(self, "_last_tool_name", "unknown")
        tool_output_preview = ""

        # Get last message from memory (the tool result)
        try:
            msgs = await agent.memory.get_memory()
            if msgs:
                last_msg = msgs[-1]
                content = getattr(last_msg, "content", None)
                if isinstance(content, list):
                    for block in content:
                        btype = bget(block, "type", "")
                        if btype == "tool_result":
                            tool_name = bget(block, "name", tool_name)
                            output = bget(block, "output", "")
                            if isinstance(output, list):
                                parts = [str(bget(b, "text", str(b)))[:800] for b in output]
                                tool_output_preview = "\n".join(parts)[:3000]
                            elif isinstance(output, str):
                                tool_output_preview = output[:3000]
                            else:
                                tool_output_preview = str(output)[:3000]
                elif isinstance(content, str):
                    tool_output_preview = content[:3000]
        except Exception as e:
            logger.warning(f"Failed to extract tool result from memory: {e}")

        self._emit("tool_call_completed", message=f"MCP tool '{tool_name}' returned", duration_ms=tool_ms, details={
            "tool_name": tool_name,
            "output_preview": tool_output_preview,
        })
        self._emit("agent_iteration_completed", message=f"Iteration {self.iteration_count} done", duration_ms=iter_ms)


async def execute_with_event_capture(
    db,
    agent_def,
    input_prompt: str,
    max_iterations: int,
    timeout_seconds: int,
    run_id: str,
) -> dict[str, Any]:
    """Execute a real agent with event capture via hooks.

    Returns dict with: status, final_output, duration_ms, events, iteration_count, message_history
    """
    from app.services.agent_factory import create_agentscope_agent, get_tools_for_agent
    from agentscope.message import Msg

    collector = RuntimeEventCollector(run_id, db=db)

    # Create agent
    collector._emit("phase_started", phase="runtime", message="Creating ReActAgent")
    tools = get_tools_for_agent(agent_def)

    try:
        react_agent = await create_agentscope_agent(
            agent_def, db=db, tools_to_register=tools, max_iters=max_iterations,
        )
    except Exception as e:
        collector._emit("phase_failed", phase="runtime", message=f"Agent creation failed: {e}")
        return {
            "status": "failed",
            "final_output": None,
            "duration_ms": 0,
            "events": collector.events,
            "iteration_count": 0,
            "message_history": [],
            "error": str(e),
        }

    if react_agent is None:
        collector._emit("phase_failed", phase="runtime", message="Agent creation returned None")
        return {
            "status": "failed",
            "final_output": None,
            "duration_ms": 0,
            "events": collector.events,
            "iteration_count": 0,
            "message_history": [],
            "error": "Could not create ReActAgent",
        }

    # Register hooks for event capture
    react_agent.register_instance_hook("pre_reasoning", "test_lab_pre_reasoning", collector.on_pre_reasoning)
    react_agent.register_instance_hook("post_reasoning", "test_lab_post_reasoning", collector.on_post_reasoning)
    react_agent.register_instance_hook("pre_acting", "test_lab_pre_acting", collector.on_pre_acting)
    react_agent.register_instance_hook("post_acting", "test_lab_post_acting", collector.on_post_acting)

    # Log MCP connections
    connected_mcps = getattr(react_agent, "_connected_mcps", [])
    for mcp in connected_mcps:
        collector._emit("mcp_session_connected", message=f"Connected to {mcp.get('url', '')}", details=mcp)

    collector._emit("run_started", phase="runtime", message="Agent execution started")

    # Execute with timeout
    import asyncio
    t0 = time.time()
    try:
        task_msg = Msg("user", input_prompt, "user")
        response = await asyncio.wait_for(
            react_agent(task_msg),
            timeout=timeout_seconds,
        )
        duration_ms = int((time.time() - t0) * 1000)

        # Extract final output
        if hasattr(response, "get_text_content"):
            final_output = response.get_text_content() or ""
        elif hasattr(response, "content"):
            final_output = str(response.content)
        else:
            final_output = str(response)

        # Capture message history
        message_history = []
        try:
            msgs = await react_agent.memory.get_memory()
            for msg in msgs:
                entry = {"role": getattr(msg, "role", "unknown"), "name": getattr(msg, "name", "")}
                text = ""
                if hasattr(msg, "get_text_content"):
                    text = msg.get_text_content() or ""
                if not text and hasattr(msg, "content"):
                    raw = msg.content
                    if isinstance(raw, list):
                        parts = []
                        for block in raw:
                            if hasattr(block, "text"):
                                parts.append(block.text[:2000])
                            elif hasattr(block, "type"):
                                parts.append(f"[{block.type}]")
                            else:
                                parts.append(str(block)[:500])
                        text = "\n".join(parts)
                    elif isinstance(raw, str):
                        text = raw[:5000]
                    else:
                        text = str(raw)[:5000]
                entry["content"] = text
                message_history.append(entry)
        except Exception:
            pass

        collector._emit("phase_completed", phase="runtime", message="Agent execution completed", duration_ms=duration_ms)

        return {
            "status": "completed",
            "final_output": final_output,
            "duration_ms": duration_ms,
            "events": collector.events,
            "iteration_count": collector.iteration_count,
            "message_history": message_history,
            "error": None,
        }

    except asyncio.TimeoutError:
        duration_ms = int((time.time() - t0) * 1000)
        collector._emit("run_timeout", phase="runtime", message=f"Execution timed out after {timeout_seconds}s", duration_ms=duration_ms)
        return {
            "status": "timed_out",
            "final_output": None,
            "duration_ms": duration_ms,
            "events": collector.events,
            "iteration_count": collector.iteration_count,
            "message_history": [],
            "error": f"Timeout after {timeout_seconds}s",
        }

    except Exception as e:
        duration_ms = int((time.time() - t0) * 1000)
        collector._emit("run_failed", phase="runtime", message=f"Execution failed: {e}", duration_ms=duration_ms)
        return {
            "status": "failed",
            "final_output": None,
            "duration_ms": duration_ms,
            "events": collector.events,
            "iteration_count": collector.iteration_count,
            "message_history": [],
            "error": str(e),
        }
