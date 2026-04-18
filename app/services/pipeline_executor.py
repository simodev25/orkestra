"""Pipeline Executor — dynamic tool builder for orchestration family agents.

When an orchestrator (family_id="orchestration") is invoked, this module:
1. Loads each pipeline agent from the registry
2. Pre-creates each as an AgentScope ReActAgent
3. Builds one sync tool per pipeline agent (wraps async via _run_async)
4. Each tool automatically passes accumulated context from previous agents

Pattern mirrors the test lab orchestrator_agent.py subagent pattern.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("orkestra.pipeline_executor")


@dataclass
class PipelineContext:
    """Mutable state shared across pipeline tool calls (closure-captured)."""
    accumulated: str = ""                   # running context string from all previous outputs
    results: dict[str, str] = field(default_factory=dict)  # agent_id -> last output


def _run_async(coro):
    """Run an async coroutine from a sync tool callback."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def build_pipeline_tools(
    db: AsyncSession,
    pipeline_agent_ids: list[str],
) -> tuple[list, PipelineContext]:
    """Pre-create all pipeline agents and return (tools, ctx).

    Each tool is a named sync callable that:
    - Calls the corresponding pipeline agent with task + accumulated context
    - Updates PipelineContext with the agent's output
    - Returns the output string to the orchestrator LLM
    """
    from app.services import agent_registry_service
    from app.services.agent_factory import create_agentscope_agent, get_tools_for_agent
    from agentscope.message import Msg

    ctx = PipelineContext()
    entries: list[dict] = []

    for agent_id in pipeline_agent_ids:
        try:
            agent_def = await agent_registry_service.get_agent(db, agent_id)
            if agent_def is None:
                logger.warning("Pipeline agent '%s' not found in registry — skipping", agent_id)
                continue

            local_tools = get_tools_for_agent(agent_def)
            react_agent = await create_agentscope_agent(
                agent_def, db, tools_to_register=local_tools
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
            logger.info("Pipeline agent pre-created: %s (%s)", agent_id, agent_def.name)

        except Exception as exc:
            logger.warning("Failed to pre-create pipeline agent '%s': %s", agent_id, exc)

    # Build one sync tool per pre-created agent
    tools: list = []
    for entry in entries:
        tool = _make_tool(entry, ctx)
        tools.append(tool)

    return tools, ctx


def _make_tool(entry: dict, ctx: PipelineContext):
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

        msg = Msg("user", full_input, "user")

        try:
            response = _run_async(react_agent(msg))
            output = (
                response.get_text_content()
                if hasattr(response, "get_text_content")
                else str(response)
            )
            output = (output or f"[{agent_name}] completed with no text output").strip()
        except Exception as exc:
            logger.warning("Pipeline agent '%s' raised during execution: %s", agent_id, exc)
            output = f"[ERROR] {agent_name} failed: {exc}"

        # Propagate output into shared context
        ctx.results[agent_id] = output
        ctx.accumulated += f"\n\n### {agent_name} ({agent_id}):\n{output}"

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
