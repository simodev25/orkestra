"""Agentic Test Lab Orchestrator.

Single source of truth for test execution.
Uses AgentScope stream_printing_messages for real-time output capture.
Publishes events to Redis pub/sub for SSE streaming.

Architecture:
  Celery Task → orchestrator.run_test()
    → Phase 1: Preparation worker (LLM)
    → Phase 2: Target agent execution (stream_printing_messages)
    → Phase 3: Assertion evaluation (deterministic + LLM analysis)
    → Phase 4: Diagnostic analysis (deterministic + LLM analysis)
    → Phase 5: Verdict (deterministic scoring + LLM summary)
    → Events published to Redis in real-time
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import redis

from app.core.config import get_settings

logger = logging.getLogger("orkestra.test_lab.orchestrator")


# ── Shared sync engine singleton (F17) ────────────────────────────────

_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        from sqlalchemy import create_engine
        settings = get_settings()
        sync_url = getattr(settings, 'DATABASE_URL_SYNC', None)
        if not sync_url:
            sync_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("asyncpg", "psycopg2")
        _sync_engine = create_engine(sync_url, pool_size=5, max_overflow=3)
    return _sync_engine


# ── Event publishing ──────────────────────────────────────────────────


def emit(run_id: str, event_type: str, phase: str, message: str,
         details: dict | None = None, duration_ms: int | None = None):
    """Persist event to DB + publish to Redis pub/sub for SSE."""
    from sqlalchemy import text
    settings = get_settings()
    evt_id = f"evt_{datetime.now(timezone.utc).strftime('%H%M%S%f')}"

    engine = _get_sync_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO test_run_events (id, run_id, event_type, phase, message, details, timestamp, duration_ms, created_at, updated_at) "
            "VALUES (:id, :rid, :et, :ph, :msg, :det, NOW(), :dur, NOW(), NOW())"
        ), {"id": evt_id, "rid": run_id, "et": event_type, "ph": phase,
            "msg": message, "det": json.dumps(details) if details else None, "dur": duration_ms})
        conn.commit()

    # Publish to Redis for SSE
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.publish(f"test_lab:run:{run_id}", json.dumps({
            "id": evt_id, "event_type": event_type, "phase": phase,
            "message": message, "details": details, "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, default=str))
        r.close()
    except Exception:
        pass


def update_run(run_id: str, **fields):
    """Update run record in DB."""
    from sqlalchemy import text
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    engine = _get_sync_engine()
    with engine.connect() as conn:
        conn.execute(text(f"UPDATE test_runs SET {sets}, updated_at = NOW() WHERE id = :id"), {"id": run_id, **fields})
        conn.commit()


# ── LLM model factory ────────────────────────────────────────────────


def _get_config_sync() -> dict:
    """Read test lab config from DB (sync for Celery worker)."""
    from sqlalchemy import create_engine, text
    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("asyncpg", "psycopg2").replace("+asyncpg", "")
    engine = create_engine(sync_url)
    config = {
        "orchestrator": {"provider": "ollama", "model": "gpt-oss:20b-cloud"},
        "workers": {
            "preparation": {"prompt": "You are a test preparation worker. Produce a structured TEST PLAN.", "model": None},
            "assertion": {"prompt": "Analyze assertion results briefly.", "model": None},
            "diagnostic": {"prompt": "Analyze diagnostic findings and recommend fixes.", "model": None},
            "verdict": {"prompt": "Produce a concise final test summary.", "model": None},
        },
    }
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT key, value FROM test_lab_config"))
            for row in result.fetchall():
                if row[0] in config and isinstance(config[row[0]], dict):
                    config[row[0]] = {**config[row[0]], **row[1]}
    except Exception:
        pass
    engine.dispose()
    return config


def make_model(worker_name: str | None = None):
    """Create the LLM for worker agents. Reads model from config."""
    from agentscope.model import OllamaChatModel
    import os
    settings = get_settings()
    config = _get_config_sync()

    # Check worker-specific model override
    model_name = None
    if worker_name and worker_name in config.get("workers", {}):
        model_name = config["workers"][worker_name].get("model")

    # Fall back to orchestrator model
    if not model_name:
        model_name = config.get("orchestrator", {}).get("model", "gpt-oss:20b-cloud")

    # Always use ollama.com cloud API
    host = "https://ollama.com"
    return OllamaChatModel(model_name=model_name, host=host, stream=False)


def _load_skills_text(skill_ids: list[str]) -> str:
    """Load skill content from DB by IDs."""
    from sqlalchemy import create_engine, text
    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("asyncpg", "psycopg2").replace("+asyncpg", "")
    engine = create_engine(sync_url)
    parts = []
    try:
        with engine.connect() as conn:
            for sid in skill_ids:
                r = conn.execute(text("SELECT label, category, description, behavior_templates, output_guidelines FROM skill_definitions WHERE id = :id"), {"id": sid})
                row = r.fetchone()
                if row:
                    lines = [f"### {row[0]} ({row[1]})"]
                    if row[2]:
                        lines.append(row[2])
                    if row[3]:
                        lines.append("Behavior:")
                        for b in row[3]:
                            lines.append(f"- {b}")
                    if row[4]:
                        lines.append("Output guidelines:")
                        for g in row[4]:
                            lines.append(f"- {g}")
                    parts.append("\n".join(lines))
    except Exception:
        pass
    engine.dispose()
    return "\n\n".join(parts)


def make_formatter():
    from agentscope.formatter import OllamaChatFormatter
    return OllamaChatFormatter()


# ── Worker helper ─────────────────────────────────────────────────────


async def run_worker(run_id: str, phase: str, worker_name: str, default_prompt: str, user_prompt: str) -> str:
    """Create a worker ReActAgent, run it, return response."""
    from agentscope.agent import ReActAgent
    from agentscope.tool import Toolkit
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg

    # Read prompt + skills from config
    config = _get_config_sync()
    agent_key = worker_name.replace("_agent", "").replace("_worker", "")
    worker_cfg = config.get("workers", {}).get(agent_key, {})
    sys_prompt = worker_cfg.get("prompt") or default_prompt

    # Inject skills into prompt
    skill_ids = worker_cfg.get("skills") or []
    if skill_ids:
        skills_text = _load_skills_text(skill_ids)
        if skills_text:
            sys_prompt = f"{sys_prompt}\n\n## SKILLS\n\n{skills_text}"

    worker = ReActAgent(
        name=worker_name, sys_prompt=sys_prompt,
        model=make_model(worker_name.replace("_worker", "")),
        formatter=make_formatter(),
        toolkit=Toolkit(), memory=InMemoryMemory(), max_iters=1,
    )

    task_msg = Msg("user", user_prompt, "user")
    response = await worker(task_msg)
    text = response.get_text_content() if hasattr(response, "get_text_content") else str(response)

    emit(run_id, "agent_message", phase, f"{worker_name}: {text[:100]}...",
         details={"agent": worker_name, "content": text[:3000]})

    return text or ""


# ── Main entry point ──────────────────────────────────────────────────


async def run_test(run_id: str, scenario_id: str):
    """Execute a full agentic test run through 5 phases.

    Called by the Celery task. Uses stream_printing_messages for real-time
    output and publishes events to Redis for SSE streaming.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from app.models.test_lab import TestScenario, TestRun, TestRunAssertion, TestRunDiagnostic, TestRunEvent
    from app.services import agent_registry_service

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        scenario = await db.get(TestScenario, scenario_id)
        run = await db.get(TestRun, run_id)
        agent_def = await agent_registry_service.get_agent(db, scenario.agent_id)

        if not scenario or not run or not agent_def:
            raise ValueError("Scenario, run, or agent not found")

        update_run(run_id, status="running")
        emit(run_id, "run_created", "orchestrator", "Test run created")
        emit(run_id, "orchestrator_started", "orchestrator", "Orchestrator started")
        t0 = time.time()

        # ── Phase 1: Preparation ──────────────────────────────
        emit(run_id, "orchestrator_tool_call", "orchestrator", "→ prepare_test_scenario",
             details={"tool_name": "prepare_test_scenario"})
        emit(run_id, "phase_started", "preparation", "Preparation worker started")

        config = json.dumps({
            "name": scenario.name, "agent_id": scenario.agent_id,
            "timeout": scenario.timeout_seconds, "max_iters": scenario.max_iterations,
            "assertions": len(scenario.assertions or []),
            "expected_tools": scenario.expected_tools or [],
        })
        plan = await run_worker(run_id, "preparation", "preparation_agent",
            "You are a test preparation worker. Produce a structured TEST PLAN: Objective, Target agent, Input, Expected behavior, Assertions, Constraints, Risks. Be concise.",
            f"Prepare test plan for:\n{config}\n\nPrompt: {scenario.input_prompt}")

        emit(run_id, "phase_completed", "preparation", "Test plan ready",
             details={"worker_response": plan[:3000]})

        # ── Phase 2: Target agent execution ───────────────────
        emit(run_id, "orchestrator_tool_call", "orchestrator", "→ execute_target_agent",
             details={"tool_name": "execute_target_agent"})
        emit(run_id, "phase_started", "runtime", "Creating target agent")

        runtime_result = await _execute_target_agent(run_id, db, scenario, agent_def)

        duration_ms = int((time.time() - t0) * 1000)
        run.final_output = runtime_result.get("final_output")
        run.duration_ms = duration_ms
        run.execution_metadata = {
            "iteration_count": runtime_result.get("iteration_count", 0),
            "message_history": runtime_result.get("message_history", []),
            "status": runtime_result.get("status"),
        }
        await db.commit()

        emit(run_id, "phase_completed", "runtime", f"Agent completed ({duration_ms}ms)",
             details={"duration_ms": duration_ms, "status": runtime_result["status"]})
        emit(run_id, "orchestrator_tool_call", "orchestrator", "← execute_target_agent completed")

        # ── Phase 3: Assertions ───────────────────────────────
        emit(run_id, "orchestrator_tool_call", "orchestrator", "→ run_assertion_evaluation",
             details={"tool_name": "run_assertion_evaluation"})
        emit(run_id, "assertion_phase_started", "assertions", "Assertion evaluation started")

        from app.services.test_lab.assertion_engine import evaluate_assertions
        result = await db.execute(
            select(TestRunEvent).where(TestRunEvent.run_id == run_id).order_by(TestRunEvent.timestamp))
        all_events = [{"event_type": e.event_type, "details": e.details, "duration_ms": e.duration_ms}
                      for e in result.scalars().all()]

        assertion_results = evaluate_assertions(
            assertion_defs=scenario.assertions or [], events=all_events,
            final_output=run.final_output, duration_ms=duration_ms,
            iteration_count=runtime_result.get("iteration_count", 0),
            final_status=runtime_result.get("status", "unknown"))

        for ar in assertion_results:
            emit(run_id, "assertion_passed" if ar["passed"] else "assertion_failed", "assertions", ar["message"])
            db.add(TestRunAssertion(
                run_id=run_id, assertion_type=ar["assertion_type"], target=ar.get("target"),
                expected=ar.get("expected"), actual=ar.get("actual"), passed=ar["passed"],
                critical=ar.get("critical", False), message=ar["message"], details=ar.get("details")))
        await db.commit()

        passed = sum(1 for a in assertion_results if a["passed"])
        analysis = await run_worker(run_id, "assertions", "assertion_agent",
            "Analyze assertion results briefly.",
            json.dumps({"passed": passed, "total": len(assertion_results),
                        "results": [{"type": a["assertion_type"], "passed": a["passed"], "message": a["message"]} for a in assertion_results]}))

        emit(run_id, "phase_completed", "assertions", f"Assertions: {passed}/{len(assertion_results)} passed",
             details={"worker_response": analysis[:3000], "passed": passed, "total": len(assertion_results)})

        # ── Phase 4: Diagnostics ──────────────────────────────
        emit(run_id, "orchestrator_tool_call", "orchestrator", "→ run_diagnostic_analysis",
             details={"tool_name": "run_diagnostic_analysis"})
        emit(run_id, "diagnostic_phase_started", "diagnostics", "Diagnostic analysis started")

        from app.services.test_lab.diagnostic_engine import generate_diagnostics
        diagnostic_results = generate_diagnostics(
            events=all_events, assertions=assertion_results,
            expected_tools=scenario.expected_tools, duration_ms=duration_ms,
            iteration_count=runtime_result.get("iteration_count", 0),
            max_iterations=scenario.max_iterations, timeout_seconds=scenario.timeout_seconds,
            final_output=run.final_output)

        for dr in diagnostic_results:
            emit(run_id, "diagnostic_generated", "diagnostics", dr["message"],
                 details={"code": dr["code"], "severity": dr["severity"]})
            db.add(TestRunDiagnostic(
                run_id=run_id, code=dr["code"], severity=dr["severity"], message=dr["message"],
                probable_causes=dr.get("probable_causes"), recommendation=dr.get("recommendation"),
                evidence=dr.get("evidence")))
        await db.commit()

        diag_analysis = await run_worker(run_id, "diagnostics", "diagnostic_agent",
            "Analyze diagnostic findings and recommend fixes.",
            json.dumps([{"code": d["code"], "severity": d["severity"], "message": d["message"]} for d in diagnostic_results]))

        emit(run_id, "phase_completed", "diagnostics", f"Diagnostics: {len(diagnostic_results)} findings",
             details={"worker_response": diag_analysis[:3000], "count": len(diagnostic_results)})

        # ── Phase 5: Verdict ──────────────────────────────────
        emit(run_id, "orchestrator_tool_call", "orchestrator", "→ compute_final_verdict",
             details={"tool_name": "compute_final_verdict"})
        emit(run_id, "report_phase_started", "report", "Computing verdict")

        from app.services.test_lab.scoring import compute_score_and_verdict
        score, verdict = compute_score_and_verdict(assertion_results, diagnostic_results)

        summary = await run_worker(run_id, "report", "verdict_agent",
            "Produce a concise final test summary.",
            json.dumps({"score": score, "verdict": verdict,
                        "assertions_passed": passed, "assertions_total": len(assertion_results),
                        "diagnostics": len(diagnostic_results)}))

        emit(run_id, "phase_completed", "report", f"Score: {score}/100 — Verdict: {verdict}",
             details={"worker_response": summary[:3000], "score": score, "verdict": verdict})

        update_run(run_id, score=score, verdict=verdict, status="completed",
                   summary=f"Score: {score}/100 — Verdict: {verdict} — {summary[:200]}",
                   ended_at=datetime.now(timezone.utc).isoformat())

        emit(run_id, "run_completed", "orchestrator", f"Run completed: {verdict} ({score}/100)")

    await engine.dispose()


# ── Target agent execution with stream_printing_messages ──────────────


async def _execute_target_agent(run_id: str, db, scenario, agent_def) -> dict:
    """Execute the real target agent and capture all output via stream_printing_messages."""
    from agentscope.message import Msg
    from agentscope.pipeline import stream_printing_messages
    from app.services.agent_factory import create_agentscope_agent, get_tools_for_agent

    tools = get_tools_for_agent(agent_def)
    react_agent = await create_agentscope_agent(
        agent_def, db=db, tools_to_register=tools, max_iters=scenario.max_iterations)

    if react_agent is None:
        emit(run_id, "phase_failed", "runtime", "Agent creation failed")
        return {"status": "failed", "final_output": None, "duration_ms": 0, "iteration_count": 0, "message_history": []}

    # Log MCP connections
    for mcp in getattr(react_agent, "_connected_mcps", []):
        emit(run_id, "mcp_session_connected", "runtime", f"Connected to {mcp.get('url', '')}",
             details={"tools": mcp.get("tools", []), "url": mcp.get("url", "")})

    emit(run_id, "run_started", "runtime", "Target agent execution started")
    task_msg = Msg("user", scenario.input_prompt, "user")
    t0 = time.time()

    # Execute agent directly (no stream_printing_messages wrapper that breaks ReAct loop)
    try:
        response = await asyncio.wait_for(react_agent(task_msg), timeout=scenario.timeout_seconds)
    except asyncio.TimeoutError:
        emit(run_id, "run_timeout", "runtime", f"Timed out after {scenario.timeout_seconds}s")
        return {"status": "timed_out", "final_output": None, "duration_ms": int((time.time() - t0) * 1000),
                "iteration_count": 0, "message_history": []}

    duration_ms = int((time.time() - t0) * 1000)

    # Extract full conversation from memory and emit detailed events
    final_output = ""
    message_history = []

    def bget(block, key, default=""):
        if isinstance(block, dict):
            return block.get(key, default)
        return getattr(block, key, default)

    try:
        msgs = await react_agent.memory.get_memory()
        for i, m in enumerate(msgs):
            role = getattr(m, "role", "")
            name = getattr(m, "name", "")
            text = m.get_text_content() if hasattr(m, "get_text_content") else ""
            content_blocks = getattr(m, "content", None)

            # Parse each block for detailed events
            if isinstance(content_blocks, list):
                for block in content_blocks:
                    bt = bget(block, "type", "")

                    if bt == "tool_use":
                        tool_name = bget(block, "name", "unknown")
                        tool_input = str(bget(block, "raw_input", "") or bget(block, "input", ""))[:500]
                        emit(run_id, "tool_call_started", "runtime", f"Calling MCP: {tool_name}",
                             details={"tool_name": tool_name, "tool_input": tool_input})

                    elif bt == "tool_result":
                        tool_name = bget(block, "name", "unknown")
                        output = bget(block, "output", "")
                        if isinstance(output, list):
                            output_text = "\n".join(str(bget(b, "text", b))[:800] for b in output)[:3000]
                        else:
                            output_text = str(output)[:3000]
                        emit(run_id, "tool_call_completed", "runtime", f"MCP returned: {tool_name}",
                             details={"tool_name": tool_name, "output_preview": output_text})

                    elif bt == "thinking":
                        thinking_text = str(bget(block, "text", ""))[:1000]
                        if thinking_text:
                            emit(run_id, "agent_message", "runtime", f"{name} (thinking)",
                                 details={"agent": name, "thinking": thinking_text})

                    elif bt == "text":
                        block_text = str(bget(block, "text", ""))[:2000]
                        if block_text and role == "assistant":
                            emit(run_id, "llm_request_completed", "runtime", f"{name}: {block_text[:80]}...",
                                 details={"agent": name, "llm_output": block_text})

                # Build text from blocks for history
                if not text:
                    parts = [str(bget(b, "text", b))[:500] for b in content_blocks]
                    text = "\n".join(parts)

            elif isinstance(content_blocks, str) and not text:
                text = content_blocks

            message_history.append({"role": role, "name": name, "content": text[:5000]})

        if msgs:
            last = msgs[-1]
            final_output = last.get_text_content() if hasattr(last, "get_text_content") else str(last.content)[:5000]
    except Exception:
        pass

    return {"status": "completed", "final_output": final_output, "duration_ms": duration_ms,
            "iteration_count": len(message_history), "message_history": message_history}
