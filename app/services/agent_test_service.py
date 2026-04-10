"""Agent Test Lab service — executes isolated behavioral tests via AgentScope ReActAgent."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import AgentDefinition
from app.services.llm_output_validator import validate_forbidden_effects, validate_output_structure
from app.core.tracing import setup_tracing as _setup_tracing, flush_traces as _flush_traces
from app.core.config import get_settings as _get_settings

logger = logging.getLogger("orkestra.agent_test")


def _ensure_tracing():
    """Lazy-init tracing on first test run (delegates to core module)."""
    _setup_tracing(endpoint=_get_settings().OTEL_ENDPOINT)


def _truncate(s: str, max_len: int = 32000) -> str:
    """Truncate a string to fit in OTLP span attributes."""
    return s[:max_len] if len(s) > max_len else s


async def execute_test_run(
    db: AsyncSession,
    agent: AgentDefinition,
    task: str,
    structured_input: dict | None = None,
    evidence: str | None = None,
    context_variables: dict | None = None,
) -> dict[str, Any]:
    """Run an isolated behavioral test with full OTLP tracing of each step."""

    provider = agent.llm_provider or "ollama"
    model = agent.llm_model or "mistral"

    # Build user message
    user_parts = [task]
    if structured_input:
        user_parts.append(f"\n\nStructured input:\n```json\n{json.dumps(structured_input, indent=2)}\n```")
    if evidence:
        user_parts.append(f"\n\nEvidence / reference documents:\n{evidence}")
    user_message = "\n".join(user_parts)

    _ensure_tracing()

    from opentelemetry import trace as otel_trace
    tracer = otel_trace.get_tracer("orkestra.test_lab")

    t0 = time.time()
    message_history = []
    react_agent = None

    with tracer.start_as_current_span(
        "agent_test_run",
        attributes={
            "orkestra.agent_id": agent.id,
            "orkestra.agent_name": agent.name,
            "orkestra.agent_version": agent.version,
            "orkestra.family_id": agent.family_id or "",
            "orkestra.criticality": agent.criticality or "",
            "gen_ai.system": provider,
            "gen_ai.request.model": model,
            "gen_ai.operation.name": "chat",
        },
    ) as root_span:

        # ── Step 1: Build system prompt ─────────────────────────
        with tracer.start_as_current_span("build_system_prompt") as prompt_span:
            from app.services.prompt_builder import build_agent_prompt
            system_prompt = await build_agent_prompt(db, agent, runtime_context=context_variables)
            prompt_span.set_attribute("gen_ai.prompt.system", _truncate(system_prompt))
            prompt_span.set_attribute("gen_ai.prompt.system_length", len(system_prompt))

        # ── Step 2: Resolve tools / MCP ─────────────────────────
        with tracer.start_as_current_span("resolve_tools") as tools_span:
            from app.services.agent_factory import get_tools_for_agent, resolve_mcp_servers
            tools = get_tools_for_agent(agent)
            allowed_mcps = agent.allowed_mcps or []
            forbidden_effects = agent.forbidden_effects or []
            mcp_servers = await resolve_mcp_servers(db, agent)
            tools_span.set_attribute("orkestra.allowed_mcps", json.dumps(allowed_mcps))
            tools_span.set_attribute("orkestra.forbidden_effects", json.dumps(forbidden_effects))
            tools_span.set_attribute("orkestra.local_tools_count", len(tools))
            tools_span.set_attribute("orkestra.mcp_servers", json.dumps([s.get("url", "") for s in mcp_servers if s.get("url")]))

        # ── Step 3: Create ReActAgent with MCP ─────────────────
        with tracer.start_as_current_span("create_react_agent") as agent_span:
            from app.services.agent_factory import create_agentscope_agent
            # Use max_iters=3 to allow tool calls (ReAct loop: think → act → observe)
            react_agent = await create_agentscope_agent(
                agent, db=db, tools_to_register=tools, max_iters=3,
            )
            if react_agent is None:
                error_msg = (
                    f"Could not create ReActAgent for {agent.id} "
                    f"(provider={provider}, model={model})"
                )
                agent_span.set_attribute("orkestra.error", error_msg)
                root_span.set_attribute("orkestra.verdict", "error")
                _flush_traces()
                return {
                    "status": "error",
                    "error": error_msg,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "raw_output": "",
                    "provider": provider,
                    "model": model,
                    "token_usage": None,
                }
            agent_span.set_attribute("orkestra.agent_class", type(react_agent).__name__)
            connected_mcps = getattr(react_agent, "_connected_mcps", [])
            if connected_mcps:
                agent_span.set_attribute("orkestra.connected_mcps", json.dumps(connected_mcps))

        # ── Step 4: LLM call (invoke agent) ─────────────────────
        with tracer.start_as_current_span(
            "llm_call",
            attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.system": provider,
                "gen_ai.request.model": model,
                "gen_ai.prompt.user": _truncate(user_message),
                "gen_ai.prompt.user_length": len(user_message),
            },
        ) as llm_span:
            try:
                from agentscope.message import Msg
                task_msg = Msg("user", user_message, "user")
                llm_t0 = time.time()
                response = await react_agent(task_msg)
                llm_latency = int((time.time() - llm_t0) * 1000)

                # Extract text
                if hasattr(response, "get_text_content"):
                    content = response.get_text_content() or ""
                elif hasattr(response, "content"):
                    content = str(response.content)
                else:
                    content = str(response)

                llm_span.set_attribute("gen_ai.response", _truncate(content))
                llm_span.set_attribute("gen_ai.response_length", len(content))
                llm_span.set_attribute("gen_ai.latency_ms", llm_latency)

                # Capture full message history (think → tool_call → tool_result → answer)
                try:
                    memory = react_agent.memory
                    if memory:
                        msgs = await memory.get_memory()
                        for msg in msgs:
                            entry = {"role": getattr(msg, "role", "unknown"), "name": getattr(msg, "name", "")}
                            # Get text content first, fallback to raw content
                            text = ""
                            if hasattr(msg, "get_text_content"):
                                text = msg.get_text_content() or ""
                            if not text and hasattr(msg, "content"):
                                raw = msg.content
                                if isinstance(raw, list):
                                    # Tool results are lists of blocks
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
                except Exception as e:
                    logger.warning(f"Failed to capture message history: {e}")

            except Exception as e:
                logger.error(f"AgentScope execution failed for {agent.id}: {e}")
                llm_span.set_attribute("orkestra.error", str(e))
                root_span.set_attribute("orkestra.verdict", "error")
                _flush_traces()
                return {
                    "status": "error",
                    "error": str(e),
                    "latency_ms": int((time.time() - t0) * 1000),
                    "raw_output": "",
                    "user_prompt": user_message,
                    "provider": provider,
                    "model": model,
                    "token_usage": None,
                }

        # ── Step 5: Post-LLM output validation (F13) ────────────
        result: dict[str, Any] = {
            "status": "completed",
            "raw_output": content,
            "user_prompt": user_message,
            "latency_ms": 0,  # updated below
            "provider": provider,
            "model": model,
            "token_usage": None,
            "connected_mcps": getattr(react_agent, "_connected_mcps", []) if react_agent else [],
            "message_history": message_history,
        }

        forbidden = agent.forbidden_effects or []
        if forbidden:
            fx_check = validate_forbidden_effects(content, forbidden)
            if not fx_check.valid:
                result["forbidden_effect_violations"] = fx_check.violations

        struct_check = validate_output_structure(content)
        if not struct_check.valid:
            result["structure_violations"] = struct_check.violations

        # ── Finalize root span ──────────────────────────────────
        latency_ms = int((time.time() - t0) * 1000)
        result["latency_ms"] = latency_ms
        root_span.set_attribute("orkestra.verdict", "pass")
        root_span.set_attribute("orkestra.latency_ms", latency_ms)
        root_span.set_attribute("orkestra.output_length", len(content))

    _flush_traces()

    return result
