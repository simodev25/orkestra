"""Session MCP Tools — Internal tool functions for the SessionAgent.

Exposes 3 synchronous tool functions that are registered in a ReActAgent
Toolkit (AgentScope). These tools allow the SessionAgent LLM to:

  1. list_agents()                   — discover available agents
  2. get_agent_info(agent_id)        — inspect agent details
  3. create_scenario_and_run(...)    — create a scenario + run and execute it
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.models.base import new_id
from app.services.test_lab.execution_engine import (
    _get_sync_engine,
    _run_async,
    execute_test_run,
)

logger = logging.getLogger("orkestra.test_lab.session_mcp")


# ── Tool 1: list_agents ───────────────────────────────────────────────────────


def list_agents() -> str:
    """List all active agents available for testing.

    Returns a JSON-formatted string containing id, name, and purpose for each
    agent that is not archived or disabled. Use this tool first to discover
    which agents can be tested before calling get_agent_info or
    create_scenario_and_run.

    Returns:
        A JSON string representing a list of agent summaries, e.g.:
        [{"id": "agent_abc", "name": "MyAgent", "purpose": "...", "status": "active"}, ...]
        On error, returns {"error": "..."}.
    """
    try:
        engine = _get_sync_engine()
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, name, purpose, status "
                    "FROM agent_definitions "
                    "WHERE status NOT IN ('archived', 'disabled') "
                    "ORDER BY name"
                )
            ).fetchall()

        agents = [
            {"id": row[0], "name": row[1], "purpose": row[2], "status": row[3]}
            for row in rows
        ]
        return json.dumps(agents, ensure_ascii=False, indent=2)

    except Exception as exc:
        logger.exception("list_agents failed")
        return json.dumps({"error": str(exc)})


# ── Tool 2: get_agent_info ────────────────────────────────────────────────────


def get_agent_info(agent_id: str) -> str:
    """Get detailed information about a specific agent.

    Loads the full definition of the agent identified by agent_id, including
    its purpose, description, system prompt (truncated), skills (truncated),
    allowed MCPs, forbidden effects, limitations, criticality, and LLM config.

    Use this before create_scenario_and_run to understand the agent's
    capabilities and craft a meaningful input_prompt.

    Args:
        agent_id: The unique identifier of the agent (e.g. "agent_abc123").

    Returns:
        A human-readable structured text with all relevant agent fields.
        If the agent is not found, returns {"error": "...", "available_agents": [...]}.
    """
    try:
        engine = _get_sync_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, name, purpose, description, "
                    "       prompt_content, skills_content, "
                    "       allowed_mcps, forbidden_effects, limitations, "
                    "       criticality, llm_provider, llm_model "
                    "FROM agent_definitions "
                    "WHERE id = :agent_id"
                ),
                {"agent_id": agent_id},
            ).fetchone()

            if row is None:
                available = conn.execute(
                    text(
                        "SELECT id, name FROM agent_definitions "
                        "WHERE status NOT IN ('archived', 'disabled') "
                        "ORDER BY name"
                    )
                ).fetchall()
                return json.dumps(
                    {
                        "error": f"Agent '{agent_id}' not found.",
                        "available_agents": [
                            {"id": r[0], "name": r[1]} for r in available
                        ],
                    }
                )

        (
            _id, name, purpose, description,
            prompt_content, skills_content,
            allowed_mcps, forbidden_effects, limitations,
            criticality, llm_provider, llm_model,
        ) = row

        # Truncate long text fields so the LLM context stays manageable
        prompt_snippet = (prompt_content or "")[:400]
        if prompt_content and len(prompt_content) > 400:
            prompt_snippet += "… [truncated]"

        skills_snippet = (skills_content or "")[:300]
        if skills_content and len(skills_content) > 300:
            skills_snippet += "… [truncated]"

        lines = [
            f"Agent: {name} (id: {_id})",
            f"Purpose: {purpose}",
            f"Description: {description or '(none)'}",
            f"Criticality: {criticality or 'medium'}",
            f"LLM: {llm_provider or 'default'} / {llm_model or 'default'}",
            "",
            f"System prompt (excerpt):\n{prompt_snippet or '(none)'}",
            "",
            f"Skills (excerpt):\n{skills_snippet or '(none)'}",
            "",
            f"Allowed MCPs: {json.dumps(allowed_mcps) if allowed_mcps else '(none)'}",
            f"Forbidden effects: {json.dumps(forbidden_effects) if forbidden_effects else '(none)'}",
            f"Limitations: {json.dumps(limitations) if limitations else '(none)'}",
        ]
        return "\n".join(lines)

    except Exception as exc:
        logger.exception("get_agent_info failed for agent_id=%s", agent_id)
        return json.dumps({"error": str(exc)})


# ── Tool 3: create_scenario_and_run ──────────────────────────────────────────


def create_scenario_and_run(
    agent_id: str,
    objective: str,
    input_prompt: str,
    assertions: list[dict] | None = None,
    timeout_seconds: int = 60,
    max_iterations: int = 8,
    tags: list[str] | None = None,
) -> str:
    """Create a test scenario for an agent and immediately execute it.

    This is the main action tool. It:
      1. Validates that the agent exists and is not archived/disabled.
      2. Inserts a test_scenarios row and a test_runs row in the database.
      3. Runs the full 5-phase test pipeline (preparation → runtime →
         assertions → diagnostics → verdict).
      4. Returns the run results as a JSON string.

    Valid assertion types:
      tool_called, tool_not_called, output_field_exists,
      output_schema_matches, max_duration_ms, max_iterations,
      final_status_is, no_tool_failures, output_contains

    Example assertions:
      [{"type": "tool_called", "tool": "search_web"},
       {"type": "max_duration_ms", "value": 5000}]

    Args:
        agent_id:        ID of the agent to test (must exist and be active).
        objective:       Short description of what this test verifies
                         (used as the scenario name, max 255 chars).
        input_prompt:    The user message / query sent to the agent under test.
        assertions:      Optional list of assertion dicts (see above).
        timeout_seconds: Maximum seconds allowed for the agent to respond
                         (default 60, min 5, max 600).
        max_iterations:  Maximum tool-calling iterations allowed (default 8,
                         min 1, max 50).
        tags:            Optional list of string tags for categorisation.

    Returns:
        JSON string: {"run_id": "...", "scenario_id": "...",
                      "verdict": "...", "score": <int>}
        On error:    {"error": "..."}
    """
    assertions = assertions or []
    tags = tags or []
    timeout_seconds = max(5, min(timeout_seconds, 600))
    max_iterations = max(1, min(max_iterations, 50))

    try:
        engine = _get_sync_engine()

        # ── 1. Validate agent exists — single connection block ────────────────
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, name, status FROM agent_definitions WHERE id = :agent_id"
                ),
                {"agent_id": agent_id},
            ).fetchone()

            if row is None:
                available = conn.execute(
                    text(
                        "SELECT id, name FROM agent_definitions "
                        "WHERE status NOT IN ('archived', 'disabled') "
                        "ORDER BY name"
                    )
                ).fetchall()
                return json.dumps(
                    {
                        "error": f"Agent '{agent_id}' not found.",
                        "available_agents": [
                            {"id": r[0], "name": r[1]} for r in available
                        ],
                    }
                )

        agent_status = row[2]
        if agent_status in ("archived", "disabled"):
            return json.dumps(
                {"error": f"Agent '{agent_id}' is {agent_status} and cannot be tested."}
            )

        # ── 2. Create scenario + run rows — single connection block ───────────
        scenario_id = new_id("scn_")
        run_id = new_id("trun_")

        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO test_scenarios "
                    "(id, name, description, agent_id, input_prompt, input_payload, "
                    " allowed_tools, expected_tools, timeout_seconds, max_iterations, "
                    " retry_count, assertions, tags, enabled, created_at, updated_at) "
                    "VALUES (:id, :name, :desc, :agent_id, :prompt, :payload, "
                    "        :allowed, :expected, :timeout, :max_iters, "
                    "        :retry, :assertions, :tags, TRUE, NOW(), NOW())"
                ),
                {
                    "id": scenario_id,
                    "name": objective[:255],
                    "desc": f"Interactive session run — {objective[:200]}",
                    "agent_id": agent_id,
                    "prompt": input_prompt,
                    "payload": None,
                    "allowed": json.dumps([]),
                    "expected": json.dumps([]),
                    "timeout": timeout_seconds,
                    "max_iters": max_iterations,
                    "retry": 0,
                    "assertions": json.dumps(assertions),
                    "tags": json.dumps(tags),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO test_runs "
                    "(id, scenario_id, agent_id, agent_version, status, created_at, updated_at) "
                    "VALUES (:id, :sid, :agent_id, :version, 'queued', NOW(), NOW())"
                ),
                {
                    "id": run_id,
                    "sid": scenario_id,
                    "agent_id": agent_id,
                    "version": "interactive",
                },
            )
            conn.commit()

        # ── 3. Execute the test pipeline ──────────────────────────────────────
        _run_async(execute_test_run(run_id, scenario_id))

        # ── 4. Read back verdict + score written by the pipeline ──────────────
        with engine.connect() as conn:
            result_row = conn.execute(
                text("SELECT verdict, score FROM test_runs WHERE id = :run_id"),
                {"run_id": run_id},
            ).fetchone()

        verdict = result_row[0] if result_row else "unknown"
        score = result_row[1] if (result_row and result_row[1] is not None) else 0

        return json.dumps(
            {
                "run_id": run_id,
                "scenario_id": scenario_id,
                "verdict": verdict,
                "score": score,
            }
        )

    except Exception as exc:
        logger.exception(
            "create_scenario_and_run failed for agent_id=%s", agent_id
        )
        return json.dumps({"error": str(exc)})
