"""Agent Test Run Service — orchestrates test execution, persistence, and debug output."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_test_run import AgentTestRun
from app.models.family import AgentSkill
from app.models.registry import AgentDefinition
from app.models.skill import SkillDefinition
from app.services import agent_registry_service
from app.services.agent_factory import get_tools_for_agent
from app.services.agent_test_service import execute_test_run
from app.services.prompt_builder import build_agent_prompt

logger = logging.getLogger("orkestra.agent_test_run")


async def run_test(
    db: AsyncSession,
    agent: AgentDefinition,
    task: str,
    structured_input: Optional[dict] = None,
    evidence: Optional[str] = None,
    context_variables: Optional[dict] = None,
    behavioral_checks: Optional[list] = None,
) -> dict:
    """Execute a behavioral test run against an agent's LLM and persist the result.

    Returns a dict suitable for serialising directly as an HTTP response.
    """
    agent_id = agent.id

    result = await execute_test_run(
        db,
        agent,
        task=task,
        structured_input=structured_input,
        evidence=evidence,
        context_variables=context_variables,
    )

    is_error = result.get("status") == "error"
    verdict = "error" if is_error else "pass"

    # Record Prometheus metrics
    from app.api.routes.metrics import AGENT_TEST_LATENCY, AGENT_TEST_RUNS, AGENT_TEST_TOKENS

    AGENT_TEST_RUNS.labels(agent_id=agent_id, verdict=verdict).inc()
    AGENT_TEST_LATENCY.labels(agent_id=agent_id).observe(result.get("latency_ms", 0))
    token_usage = result.get("token_usage")
    if token_usage:
        AGENT_TEST_TOKENS.labels(agent_id=agent_id, type="input").inc(token_usage.get("input", 0))
        AGENT_TEST_TOKENS.labels(agent_id=agent_id, type="output").inc(token_usage.get("output", 0))

    # Build system prompt
    try:
        system_prompt = await build_agent_prompt(db, agent, runtime_context=context_variables)
    except Exception:
        system_prompt = ""

    tools = get_tools_for_agent(agent)

    # Resolve skills from DB
    skill_result = await db.execute(
        select(SkillDefinition)
        .join(AgentSkill, AgentSkill.skill_id == SkillDefinition.id)
        .where(AgentSkill.agent_id == agent_id)
    )
    skills_resolved = [
        {"skill_id": s.id, "label": s.label, "category": s.category, "description": s.description}
        for s in skill_result.scalars().all()
    ]

    # Resolve MCP details from catalog
    mcp_details = []
    try:
        catalog_mcps = await agent_registry_service.available_mcp_summaries(db)
        mcp_map = {m["id"]: m for m in catalog_mcps}
    except Exception:
        mcp_map = {}
    for mcp_id in agent.allowed_mcps or []:
        cat = mcp_map.get(mcp_id)
        if cat:
            mcp_details.append(
                {
                    "id": mcp_id,
                    "name": cat.get("name", mcp_id),
                    "purpose": cat.get("purpose", ""),
                    "effect_type": cat.get("effect_type", ""),
                    "criticality": cat.get("criticality", ""),
                    "orkestra_state": cat.get("orkestra_state", "unknown"),
                }
            )
        else:
            mcp_details.append({"id": mcp_id, "name": mcp_id, "orkestra_state": "not_found"})

    trace_meta = {
        "system_prompt": system_prompt,
        "agent_name": agent.name,
        "family_id": agent.family_id,
        "purpose": agent.purpose,
        "allowed_mcps": agent.allowed_mcps or [],
        "mcp_details": mcp_details,
        "forbidden_effects": agent.forbidden_effects or [],
        "tools": [f.__name__ for f in tools],
        "skills": skills_resolved,
        "limitations": agent.limitations or [],
        "criticality": agent.criticality,
        "llm_provider": agent.llm_provider,
        "llm_model": agent.llm_model,
        "prompt_ref": agent.prompt_ref,
    }

    # Persist the run in DB
    run = AgentTestRun(
        agent_id=agent_id,
        agent_version=agent.version,
        status=result.get("status", "error"),
        verdict="error" if is_error else "pending",
        latency_ms=result.get("latency_ms", 0),
        provider=result.get("provider"),
        model=result.get("model"),
        raw_output=result.get("raw_output", ""),
        task=task,
        token_usage=result.get("token_usage"),
        behavioral_checks=behavioral_checks,
        error_message=result.get("error") if is_error else None,
        trace_data=trace_meta,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Save debug JSON file
    debug_dir = Path(os.environ.get("ORKESTRA_DEBUG_STRATEGY_DIR", "/app/storage/debug-strategy"))
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = (
        run.created_at.strftime("%Y%m%d_%H%M%S")
        if run.created_at
        else datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
    debug_filename = f"{agent_id}_test_{verdict}_v{agent.version}_{ts}.json"
    debug_payload = {
        "schema_version": 1,
        "type": "agent_test_run",
        "run_id": run.id,
        "generated_at": run.created_at.isoformat() if run.created_at else None,
        "status": run.status,
        "verdict": verdict,
        "elapsed_ms": result.get("latency_ms", 0),
        "agent": {
            "id": agent_id,
            "name": agent.name,
            "version": agent.version,
            "family_id": agent.family_id,
            "purpose": agent.purpose,
            "criticality": agent.criticality,
            "cost_profile": agent.cost_profile,
        },
        "llm": {
            "provider": result.get("provider"),
            "model": result.get("model"),
        },
        "prompts": {
            "system_prompt": system_prompt,
            "user_task": task,
            "user_prompt": result.get("user_prompt", ""),
            "structured_input": structured_input,
            "evidence": evidence,
            "context_variables": context_variables,
        },
        "tools": {
            "allowed_mcps": agent.allowed_mcps or [],
            "mcp_details": mcp_details,
            "forbidden_effects": agent.forbidden_effects or [],
            "registered_tools": [f.__name__ for f in tools],
            "connected_mcps": result.get("connected_mcps", []),
        },
        "skills": skills_resolved,
        "limitations": agent.limitations or [],
        "result": {
            "raw_output": result.get("raw_output", ""),
            "user_prompt": result.get("user_prompt", ""),
            "token_usage": result.get("token_usage"),
            "error": result.get("error"),
        },
        "behavioral_checks": behavioral_checks,
        "message_history": result.get("message_history", []),
    }
    try:
        with open(debug_dir / debug_filename, "w") as f:
            json.dump(debug_payload, f, indent=2, default=str)
    except Exception:
        pass

    return {
        "id": run.id,
        "agent_id": agent_id,
        "agent_version": agent.version,
        "created_at": run.created_at.isoformat(),
        "debug_file": debug_filename,
        **result,
    }


async def list_runs(db: AsyncSession, agent_id: str, limit: int = 50) -> list[dict]:
    """Return persisted test runs for an agent, most recent first."""
    result = await db.execute(
        select(AgentTestRun)
        .where(AgentTestRun.agent_id == agent_id)
        .order_by(AgentTestRun.created_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    return [
        {
            "id": r.id,
            "agent_id": r.agent_id,
            "agent_version": r.agent_version,
            "status": r.status,
            "verdict": r.verdict,
            "latency_ms": r.latency_ms,
            "provider": r.provider,
            "model": r.model,
            "raw_output": r.raw_output,
            "task": r.task,
            "token_usage": r.token_usage,
            "behavioral_checks": r.behavioral_checks,
            "error_message": r.error_message,
            "metadata": r.trace_data,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]
