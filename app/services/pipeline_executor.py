"""Pipeline Executor — dynamic tool builder for orchestration family agents.

When an orchestrator (family_id="orchestration") is invoked, this module:
1. Loads each pipeline agent from the registry
2. Pre-creates each as an AgentScope ReActAgent
3. Builds one sync tool per pipeline agent (wraps async via _run_async)
4. Each tool automatically passes accumulated context from previous agents

Pattern mirrors the test lab orchestrator_agent.py subagent pattern.
"""

from __future__ import annotations

import contextvars
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("orkestra.pipeline_executor")

# ── Context variable — threads run_id into pipeline tools (test-lab only) ─────
_run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "pipeline_run_id", default=None
)


def set_pipeline_run_id(run_id: str) -> None:
    """Register the current test-lab run_id so pipeline tools can emit events."""
    _run_id_var.set(run_id)


@dataclass
class PipelineContext:
    """Mutable state shared across pipeline tool calls (closure-captured)."""
    accumulated: str = ""                   # running context string from all previous outputs
    results: dict[str, str] = field(default_factory=dict)  # agent_id -> last output
    agents: list = field(default_factory=list)  # pre-created pipeline agents
    ordered_agent_ids: list[str] = field(default_factory=list)  # expected execution order
    next_stage_index: int = 0  # pointer in ordered_agent_ids
    stage_attempts: dict[str, int] = field(default_factory=dict)  # agent_id -> attempt count


@dataclass
class StageExecutionResult:
    """Result for one pipeline stage execution."""

    stage: str
    status: str
    output: str | None = None
    error: str | None = None
    duration_ms: int = 0
    started_at: str | None = None
    completed_at: str | None = None


def _run_async(coro):
    """Run an async coroutine from a sync tool callback."""
    import asyncio
    import concurrent.futures

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return asyncio.run(coro)

    if loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            try:
                return pool.submit(asyncio.run, coro).result(timeout=90)
            except concurrent.futures.TimeoutError as exc:
                raise RuntimeError("Agent step timed out after 90s") from exc

    return loop.run_until_complete(coro)


async def build_pipeline_tools(
    db: AsyncSession,
    pipeline_agent_ids: list[str],
    test_run_id: str | None = None,
) -> tuple[list, PipelineContext]:
    """Pre-create all pipeline agents and return (tools, ctx).

    Each tool is a named sync callable that:
    - Calls the corresponding pipeline agent with task + accumulated context
    - Updates PipelineContext with the agent's output
    - Returns the output string to the orchestrator LLM
    """
    from app.services import agent_registry_service
    from app.services.agent_factory import create_agentscope_agent, get_tools_for_agent

    ctx = PipelineContext()
    entries: list[dict] = []

    for agent_id in pipeline_agent_ids:
        try:
            agent_def = await agent_registry_service.get_agent(db, agent_id)
            if agent_def is None:
                logger.warning("Pipeline agent '%s' not found in registry — skipping", agent_id)
                continue

            local_tools = get_tools_for_agent(agent_def)
            # Keep stage agents bounded to avoid runaway tool loops that can
            # stall the whole pipeline behind the orchestrator timeout window.
            react_agent = await create_agentscope_agent(
                agent_def, db, tools_to_register=local_tools, max_iters=1
            )
            if react_agent is None:
                logger.warning("Could not create AgentScope agent for '%s' — skipping", agent_id)
                continue

            entries.append({
                "id":      agent_id,
                "name":    agent_def.name,
                "purpose": agent_def.purpose or "",
                "desc":    (agent_def.description or "")[:300],
                "agent":   react_agent,
            })
            ctx.agents.append(react_agent)
            logger.info("Pipeline agent pre-created: %s (%s)", agent_id, agent_def.name)

        except Exception as exc:
            logger.warning("Failed to pre-create pipeline agent '%s': %s", agent_id, exc)

    # Keep deterministic order of actually-created stages.
    ctx.ordered_agent_ids = [entry["id"] for entry in entries]

    # Use explicitly-passed run_id (most reliable) or fall back to ContextVar
    run_id = test_run_id or _run_id_var.get()

    # Build one sync tool per pre-created agent
    tools: list = []
    for entry in entries:
        tool = _make_tool(entry, ctx, run_id=run_id)
        tools.append(tool)

    return tools, ctx


def _make_tool(entry: dict, ctx: PipelineContext, run_id: str | None = None):
    """Factory to avoid late-binding closure issues."""
    from agentscope.message import Msg
    from agentscope.agent._react_agent import ToolResponse
    from agentscope.message._message_block import TextBlock

    agent_id   = entry["id"]
    agent_name = entry["name"]
    purpose    = entry["purpose"]
    react_agent = entry["agent"]

    # Build a valid Python identifier for the tool name
    safe_id = agent_id.replace("-", "_").replace(".", "_")

    def _tool(task: str = "") -> ToolResponse:
        """Executes this pipeline agent with the given task and accumulated context."""
        from app.services.test_lab.execution_engine import emit_event as _emit

        # run_id is captured at tool-creation time (correct async context)
        safe_tool_name = f"run_{safe_id}"
        phase_key = f"pipeline_{safe_id}"

        # Enforce deterministic stage ordering for sequential pipelines.
        expected_next = None
        if ctx.ordered_agent_ids and 0 <= ctx.next_stage_index < len(ctx.ordered_agent_ids):
            expected_next = ctx.ordered_agent_ids[ctx.next_stage_index]

        if expected_next and agent_id != expected_next:
            expected_safe = expected_next.replace("-", "_").replace(".", "_")
            msg = (
                f"[PIPELINE_ORDER_ERROR] Out-of-order tool call. "
                f"Next required stage is run_{expected_safe}."
            )
            logger.info(
                "Pipeline stage order violation: got=%s expected=%s",
                safe_tool_name,
                f"run_{expected_safe}",
            )
            return ToolResponse(content=[TextBlock(type="text", text=msg)])

        if ctx.ordered_agent_ids and ctx.next_stage_index >= len(ctx.ordered_agent_ids):
            msg = "[PIPELINE_ALREADY_COMPLETED] All configured pipeline stages have already run."
            return ToolResponse(content=[TextBlock(type="text", text=msg)])

        # Prepend accumulated context so the agent knows what happened before
        if ctx.accumulated:
            full_input = (
                f"{task}\n\n"
                f"--- Accumulated context from previous pipeline stages ---\n"
                f"{ctx.accumulated}\n"
                f"--- End of context ---"
            )
        else:
            full_input = task

        # Notify the graph: orchestrator called this pipeline tool
        if run_id:
            try:
                _emit(
                    run_id, "pipeline_tool_call", "orchestrator",
                    f"→ {safe_tool_name}",
                    details={"tool_name": safe_tool_name, "agent_id": agent_id, "agent_name": agent_name},
                )
                _emit(run_id, "phase_started", phase_key, f"{agent_name} started")
            except Exception as exc:
                logger.warning("Failed to emit pipeline_tool_call for %s: %s", agent_id, exc)

        msg = Msg("user", full_input, "user")
        t0 = time.time()

        try:
            response = _run_async(react_agent(msg))
            output = (
                response.get_text_content()
                if hasattr(response, "get_text_content")
                else str(response)
            )
            # Fallback: extract JSON from thinking blocks when text content is empty.
            # Some models (e.g. gpt-oss:20b) put their final answer inside thinking blocks
            # rather than text blocks.  _openai_formatter strips thinking blocks before
            # get_text_content() is called, so we check raw content here.
            if not output and hasattr(response, "content") and isinstance(response.content, list):
                import re as _re
                for block in response.content:
                    if block.get("type") == "thinking":
                        thinking_text = block.get("thinking", "")
                        # Look for a JSON object in the thinking block
                        m = _re.search(r"\{[\s\S]*\}", thinking_text)
                        if m:
                            output = m.group(0).strip()
                            logger.info(
                                "Pipeline agent '%s': extracted JSON from thinking block (%d chars)",
                                agent_id, len(output),
                            )
                            break
            output = (output or f"[{agent_name}] completed with no text output").strip()
        except Exception as exc:
            logger.warning("Pipeline agent '%s' raised during execution: %s", agent_id, exc)
            output = f"[ERROR] {agent_name} failed: {exc}"

        elapsed_ms = int((time.time() - t0) * 1000)

        # Propagate output into shared context
        ctx.results[agent_id] = output
        ctx.accumulated += f"\n\n### {agent_name} ({agent_id}):\n{output}"
        is_error = output.startswith("[ERROR]")
        if expected_next == agent_id:
            attempts = ctx.stage_attempts.get(agent_id, 0) + 1
            ctx.stage_attempts[agent_id] = attempts
            # Advance on success OR after 2 failed attempts (prevent infinite retry loop)
            if not is_error or attempts >= 2:
                ctx.next_stage_index += 1

        # Notify the graph: pipeline agent completed with its output
        if run_id:
            try:
                success = not output.startswith("[ERROR]")
                _emit(
                    run_id, "pipeline_agent_output", phase_key,
                    f"← {agent_name}",
                    details={
                        "agent_id": agent_id,
                        "tool_name": safe_tool_name,
                        "output": output[:3000],
                        "success": success,
                    },
                    duration_ms=elapsed_ms,
                )
                _emit(
                    run_id, "phase_completed", phase_key,
                    f"{agent_name} {'completed' if success else 'failed'} ({elapsed_ms}ms)",
                )
            except Exception:
                pass

        logger.info("Pipeline agent '%s' completed (%d chars)", agent_id, len(output))
        return ToolResponse(content=[TextBlock(type="text", text=output)])

    # Set the function name and docstring so AgentScope exposes the right tool
    _tool.__name__ = f"run_{safe_id}"
    _tool.__doc__ = (
        f"Execute pipeline agent '{agent_name}' (id: {agent_id}). "
        f"Purpose: {purpose[:200]}. "
        "Automatically receives accumulated context from all previously executed agents. "
        "Pass the relevant task description as the 'task' argument."
    )

    return _tool


async def build_pipeline_prompt_section(
    db: AsyncSession,
    pipeline_agent_ids: list[str],
) -> str:
    """Build a prompt section describing the pipeline agents and their tools.

    Injected into the orchestrator's system prompt by prompt_builder.py.
    """
    from app.services import agent_registry_service

    lines = [
        "You orchestrate the following pipeline agents in order.",
        "Call each agent's tool in sequence, passing the task and relevant context.",
        "Each tool automatically receives the accumulated output of previous agents.",
        "",
        "PIPELINE AGENTS (in execution order):",
    ]

    for i, agent_id in enumerate(pipeline_agent_ids, 1):
        try:
            agent_def = await agent_registry_service.get_agent(db, agent_id)
            if agent_def is None:
                lines.append(f"{i}. [NOT FOUND] {agent_id}")
                continue
            safe_id = agent_id.replace("-", "_").replace(".", "_")
            lines.append(
                f"{i}. Tool: run_{safe_id}\n"
                f"   Name: {agent_def.name}\n"
                f"   Purpose: {agent_def.purpose or 'N/A'}\n"
                f"   Description: {(agent_def.description or '')[:200]}"
            )
        except Exception as exc:
            logger.warning("Could not load pipeline agent '%s' for prompt: %s", agent_id, exc)
            lines.append(f"{i}. [ERROR] {agent_id}: {exc}")

    lines += [
        "",
        "EXECUTION RULES:",
        "- Call agents strictly in the order listed above.",
        "- Pass the user task to the first agent.",
        "- For subsequent agents, the accumulated context is injected automatically.",
        "- After all agents have run, synthesize their outputs into a final coherent response.",
        "- Do NOT skip any agent in the pipeline.",
    ]

    return "\n".join(lines)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sanitize_stage_error(exc: Exception) -> str:
    """Return a safe client-facing error string."""

    raw = str(exc) or exc.__class__.__name__
    lowered = raw.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return "stage timeout"
    if any(token in lowered for token in ("api key", "authorization", "forbidden", "permission")):
        return "stage failed due to upstream authorization"
    return "stage execution failed"


def _extract_final_output_from_memory(msgs: list) -> str:
    """Extract the last meaningful assistant text from AgentScope memory."""

    def _bget(block, key, default=""):
        if isinstance(block, dict):
            return block.get(key, default)
        return getattr(block, key, default)

    for m in reversed(msgs):
        if getattr(m, "role", "") != "assistant":
            continue
        text = ""
        if hasattr(m, "get_text_content"):
            text = m.get_text_content() or ""
        if not text:
            blocks = getattr(m, "content", None)
            if isinstance(blocks, list):
                text_parts: list[str] = []
                for b in blocks:
                    bt = _bget(b, "type", "")
                    if bt == "text":
                        text_parts.append(str(_bget(b, "text", "")))
                    elif bt == "thinking":
                        text_parts.append(str(_bget(b, "thinking", "")))
                text = "\n".join(p for p in text_parts if p).strip()
            elif isinstance(blocks, str):
                text = blocks
        if text and text.strip():
            return text[:10000]

    if msgs:
        last = msgs[-1]
        return (
            (last.get_text_content() if hasattr(last, "get_text_content") else "")
            or str(getattr(last, "content", ""))
        )[:5000]
    return ""


async def _execute_stage_agent(
    db: AsyncSession,
    stage: str,
    stage_agent_id: str,
    input_prompt: str,
    max_iterations: int,
) -> str:
    """Execute one stage with a dedicated AgentScope instance.

    Important: each call creates and destroys a brand-new agent instance to
    satisfy AgentScope non-thread-safe constraints under concurrent runs.
    """

    from agentscope.message import Msg

    from app.services import agent_registry_service
    from app.services.agent_factory import (
        close_agentscope_agent_resources,
        create_agentscope_agent,
        get_tools_for_agent,
    )

    agent_def = await agent_registry_service.get_agent(db, stage_agent_id)
    if agent_def is None:
        raise ValueError(f"stage agent not found: {stage_agent_id}")

    tools = get_tools_for_agent(agent_def)
    agent = await create_agentscope_agent(
        agent_def,
        db=db,
        tools_to_register=tools,
        max_iters=max_iterations,
    )
    if agent is None:
        raise RuntimeError(f"could not create stage agent: {stage_agent_id}")

    try:
        await agent(Msg("user", input_prompt, "user"))
        msgs = await agent.memory.get_memory()
        return _extract_final_output_from_memory(msgs)
    finally:
        await close_agentscope_agent_resources(agent)


async def _run_stage_with_timeout(
    db: AsyncSession,
    stage: str,
    stage_agent_id: str,
    input_prompt: str,
    stage_timeout_seconds: int,
    max_iterations: int,
    stage_runner=None,
) -> StageExecutionResult:
    """Run one stage with timeout isolation and sanitized error capture."""

    started_at = _utc_now_iso()
    t0 = time.time()
    try:
        if stage_runner is None:
            coro = _execute_stage_agent(
                db=db,
                stage=stage,
                stage_agent_id=stage_agent_id,
                input_prompt=input_prompt,
                max_iterations=max_iterations,
            )
        else:
            coro = stage_runner(stage, stage_agent_id, input_prompt)

        output = await asyncio.wait_for(coro, timeout=stage_timeout_seconds)
        elapsed = int((time.time() - t0) * 1000)
        return StageExecutionResult(
            stage=stage,
            status="completed",
            output=(output or "").strip(),
            duration_ms=elapsed,
            started_at=started_at,
            completed_at=_utc_now_iso(),
        )
    except asyncio.TimeoutError:
        elapsed = int((time.time() - t0) * 1000)
        return StageExecutionResult(
            stage=stage,
            status="failed",
            error="stage timeout",
            duration_ms=elapsed,
            started_at=started_at,
            completed_at=_utc_now_iso(),
        )
    except Exception as exc:
        elapsed = int((time.time() - t0) * 1000)
        logger.warning("Pipeline stage '%s' failed: %s", stage, exc)
        return StageExecutionResult(
            stage=stage,
            status="failed",
            error=_sanitize_stage_error(exc),
            duration_ms=elapsed,
            started_at=started_at,
            completed_at=_utc_now_iso(),
        )


def resolve_stage_agents(pipeline_agent_ids: list[str]) -> dict[str, str]:
    """Resolve canonical pipeline stages from configured pipeline agent IDs."""

    stage_map: dict[str, str] = {}
    lowered = {aid.lower(): aid for aid in pipeline_agent_ids}

    for stage in ("discover", "mobility", "weather", "budget_fit"):
        if stage in lowered:
            stage_map[stage] = lowered[stage]
            continue
        for aid in pipeline_agent_ids:
            if stage in aid.lower():
                stage_map[stage] = aid
                break

    # Positional fallback for known 4-stage pipelines.
    if len(stage_map) < 4 and len(pipeline_agent_ids) >= 4:
        defaults = {
            "discover": pipeline_agent_ids[0],
            "mobility": pipeline_agent_ids[1],
            "weather": pipeline_agent_ids[2],
            "budget_fit": pipeline_agent_ids[3],
        }
        for key, value in defaults.items():
            stage_map.setdefault(key, value)

    return stage_map


async def execute_pipeline_dag(
    db: AsyncSession,
    pipeline_agent_ids: list[str],
    user_message: str,
    stage_timeout_seconds: int = 90,
    max_iterations: int = 5,
    stage_runner=None,
    on_stage_result=None,
) -> tuple[dict[str, StageExecutionResult], str]:
    """Execute discover -> (mobility || weather) -> budget_fit with isolation.

    Returns tuple: (stage_results, final_result_text)
    """

    stage_agents = resolve_stage_agents(pipeline_agent_ids)
    required = ("discover", "mobility", "weather", "budget_fit")
    missing = [s for s in required if s not in stage_agents]
    if missing:
        raise ValueError(f"pipeline stages missing mappings: {missing}")

    results: dict[str, StageExecutionResult] = {}

    # Stage 1 - discover
    discover_res = await _run_stage_with_timeout(
        db=db,
        stage="discover",
        stage_agent_id=stage_agents["discover"],
        input_prompt=user_message,
        stage_timeout_seconds=stage_timeout_seconds,
        max_iterations=max_iterations,
        stage_runner=stage_runner,
    )
    results["discover"] = discover_res
    if on_stage_result is not None:
        await on_stage_result(discover_res)

    discover_ctx = discover_res.output or ""

    # Stage 2 - parallel mobility + weather
    mobility_prompt = (
        f"{user_message}\n\n--- discover context ---\n{discover_ctx}\n--- end discover context ---"
    )
    weather_prompt = mobility_prompt

    stage2_outputs = await asyncio.gather(
        _run_stage_with_timeout(
            db=db,
            stage="mobility",
            stage_agent_id=stage_agents["mobility"],
            input_prompt=mobility_prompt,
            stage_timeout_seconds=stage_timeout_seconds,
            max_iterations=max_iterations,
            stage_runner=stage_runner,
        ),
        _run_stage_with_timeout(
            db=db,
            stage="weather",
            stage_agent_id=stage_agents["weather"],
            input_prompt=weather_prompt,
            stage_timeout_seconds=stage_timeout_seconds,
            max_iterations=max_iterations,
            stage_runner=stage_runner,
        ),
        return_exceptions=True,
    )

    for idx, stage_name in enumerate(("mobility", "weather")):
        candidate = stage2_outputs[idx]
        if isinstance(candidate, StageExecutionResult):
            results[stage_name] = candidate
            if on_stage_result is not None:
                await on_stage_result(candidate)
            continue
        # Safety fallback even with return_exceptions=True.
        results[stage_name] = StageExecutionResult(
            stage=stage_name,
            status="failed",
            error=_sanitize_stage_error(candidate if isinstance(candidate, Exception) else Exception(str(candidate))),
            started_at=_utc_now_iso(),
            completed_at=_utc_now_iso(),
        )
        if on_stage_result is not None:
            await on_stage_result(results[stage_name])

    # Stage 3 - budget_fit still executes even if one Stage-2 sibling failed.
    mobility_ctx = results["mobility"].output or ""
    weather_ctx = results["weather"].output or ""
    budget_prompt = (
        f"{user_message}\n\n"
        f"--- discover context ---\n{discover_ctx}\n"
        f"--- mobility context ---\n{mobility_ctx}\n"
        f"--- weather context ---\n{weather_ctx}\n"
        f"--- end contexts ---"
    )
    budget_res = await _run_stage_with_timeout(
        db=db,
        stage="budget_fit",
        stage_agent_id=stage_agents["budget_fit"],
        input_prompt=budget_prompt,
        stage_timeout_seconds=stage_timeout_seconds,
        max_iterations=max_iterations,
        stage_runner=stage_runner,
    )
    results["budget_fit"] = budget_res
    if on_stage_result is not None:
        await on_stage_result(budget_res)

    final_result = budget_res.output or ""
    if not final_result:
        final_result = "\n\n".join(
            filter(
                None,
                [
                    discover_ctx,
                    mobility_ctx,
                    weather_ctx,
                ],
            )
        )

    return results, final_result
