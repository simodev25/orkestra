"""Session Agent — LLM ReActAgent for interactive test lab sessions.

The SessionAgent translates natural language user requests into test
executions using 3 internal tool functions from session_mcp:

  list_agents()              — discover available agents
  get_agent_info(agent_id)  — inspect an agent's capabilities
  create_scenario_and_run() — create + execute a test scenario

Usage:
    agent = SessionAgent()
    response, run_result = await agent.run(
        "Test summary_agent on a cyber-risk COMEX case",
        session_context={"last_run_id": "trun_xxx", "last_verdict": "pass"},
    )
    # response:    plain-text reply to show the user
    # run_result:  {"run_id", "scenario_id", "verdict", "score"} or None
"""

from __future__ import annotations

import functools
import json
import logging

from app.services.test_lab.execution_engine import (
    _make_formatter,
    _make_model,
)
from app.services.test_lab.session_mcp import (
    create_scenario_and_run,
    get_agent_info,
    list_agents,
)

logger = logging.getLogger("orkestra.test_lab.session_agent")

_SYSTEM_PROMPT = """\
You are the Orkestra Interactive Test Lab assistant. You help users test AI agents \
through natural language.

## Your workflow
1. If the user mentions an agent by name or id, call get_agent_info() to verify it \
   exists and understand its capabilities.
2. If you don't know which agent to use, call list_agents() first.
3. ONLY IF the agent is suitable for the user's request: translate the intent into \
   a clear objective and input_prompt, then call create_scenario_and_run() ONCE.
4. Report results concisely: verdict, score/100, run_id, and what to do next.

## CRITICAL rules
- **Call create_scenario_and_run() at most ONCE per user request.**
- **Do NOT call create_scenario_and_run() if get_agent_info() shows the agent \
  cannot handle the user's request.** Explain the mismatch instead and stop.
- Never invent run_ids, scenario_ids, verdicts, or scores. Only report what the \
  tools return.
- If get_agent_info returns an error, tell the user and suggest alternatives from \
  the available_agents list.
- For follow-up requests (stricter, edge case, policy, rerun), adapt the \
  input_prompt accordingly before calling create_scenario_and_run().
- Keep responses short. Bullet points preferred over prose.
"""


def _build_enriched_prompt(user_message: str, session_context: dict | None) -> str:
    """Prepend relevant session context so the LLM has situational awareness."""
    if not session_context:
        return user_message

    ctx_lines: list[str] = []

    if session_context.get("target_agent_id"):
        ctx_lines.append(f"Current agent: {session_context['target_agent_id']}")
    if session_context.get("last_run_id"):
        ctx_lines.append(f"Last run: {session_context['last_run_id']}")
    if session_context.get("last_verdict"):
        ctx_lines.append(
            f"Last verdict: {session_context['last_verdict']} "
            f"(score: {session_context.get('last_score', '?')}/100)"
        )
    if session_context.get("last_objective"):
        ctx_lines.append(f"Last objective: {session_context['last_objective']}")

    if not ctx_lines:
        return user_message

    header = "## Session context\n" + "\n".join(ctx_lines) + "\n\n## User request\n"
    return header + user_message


def _make_tool_wrappers():
    """Build ToolResponse-returning wrappers for the 3 session MCP tools.

    AgentScope requires tool functions to return ToolResponse objects.
    functools.wraps preserves __doc__ and __wrapped__ so AgentScope can build
    the correct JSON schema from the original function signatures.

    Returns:
        (wrapped_list_agents, wrapped_get_agent_info,
         wrapped_create_scenario_and_run, capture)
        where capture is a 1-element list; capture[0] is set to the
        create_scenario_and_run result dict if a test was executed.
    """
    from agentscope.message import TextBlock
    from agentscope.tool import ToolResponse

    capture: list[dict | None] = [None]

    @functools.wraps(list_agents)
    def wrapped_list_agents() -> ToolResponse:
        return ToolResponse(content=[TextBlock(type="text", text=list_agents())])

    @functools.wraps(get_agent_info)
    def wrapped_get_agent_info(agent_id: str) -> ToolResponse:
        return ToolResponse(
            content=[TextBlock(type="text", text=get_agent_info(agent_id))]
        )

    @functools.wraps(create_scenario_and_run)
    def wrapped_create_scenario_and_run(
        agent_id: str,
        objective: str,
        input_prompt: str,
        assertions: list | None = None,
        timeout_seconds: int = 60,
        max_iterations: int = 8,
        tags: list | None = None,
    ) -> ToolResponse:
        result_str = create_scenario_and_run(
            agent_id=agent_id,
            objective=objective,
            input_prompt=input_prompt,
            assertions=assertions,
            timeout_seconds=timeout_seconds,
            max_iterations=max_iterations,
            tags=tags,
        )
        try:
            parsed = json.loads(result_str)
            if "run_id" in parsed:
                capture[0] = parsed
        except Exception:
            pass
        return ToolResponse(content=[TextBlock(type="text", text=result_str)])

    return (
        wrapped_list_agents,
        wrapped_get_agent_info,
        wrapped_create_scenario_and_run,
        capture,
    )


class SessionAgent:
    """Async wrapper around a ReActAgent for interactive test sessions.

    A new ReActAgent is created per ``run()`` call so there is no
    cross-turn state pollution in the LLM's memory. Session state is managed
    externally (in TestSessionState) and passed in via ``session_context``.
    """

    async def run(
        self,
        user_message: str,
        session_context: dict | None = None,
    ) -> tuple[str, dict | None]:
        """Run the SessionAgent for a single user turn.

        Args:
            user_message:    Raw message from the user.
            session_context: Optional dict with keys: target_agent_id,
                             last_run_id, last_verdict, last_score,
                             last_objective.  Used to enrich the prompt.

        Returns:
            (response_text, run_result) where run_result is
            {"run_id", "scenario_id", "verdict", "score"} if a test was
            executed, else None.
        """
        try:
            from agentscope.agent import ReActAgent
            from agentscope.memory import InMemoryMemory
            from agentscope.message import Msg
            from agentscope.tool import Toolkit

            (
                wrapped_list_agents,
                wrapped_get_agent_info,
                wrapped_create_scenario_and_run,
                capture,
            ) = _make_tool_wrappers()

            toolkit = Toolkit()
            toolkit.register_tool_function(wrapped_list_agents)
            toolkit.register_tool_function(wrapped_get_agent_info)
            toolkit.register_tool_function(wrapped_create_scenario_and_run)

            agent = ReActAgent(
                name="session_agent",
                sys_prompt=_SYSTEM_PROMPT,
                model=_make_model(),
                formatter=_make_formatter(),
                toolkit=toolkit,
                memory=InMemoryMemory(),
                max_iters=4,
            )

            enriched = _build_enriched_prompt(user_message, session_context)
            response_msg = await agent(Msg("user", enriched, "user"))

            response_text = (
                response_msg.get_text_content()
                if hasattr(response_msg, "get_text_content")
                else str(response_msg)
            )

            return response_text, capture[0]

        except Exception as exc:
            logger.exception("SessionAgent.run failed")
            return f"Test session error: {exc}", None
