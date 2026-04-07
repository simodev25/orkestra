"""Celery tasks for Agentic Test Lab.

Each test phase runs as a Celery task. The orchestrator dispatches
them sequentially and publishes agent messages to Redis for SSE streaming.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import redis

from app.celery_app import celery
from app.core.config import get_settings

logger = logging.getLogger("orkestra.tasks.test_lab")


def _get_redis():
    settings = get_settings()
    return redis.Redis.from_url(settings.REDIS_URL)


def _publish_event(run_id: str, event: dict):
    """Publish event to Redis pub/sub for SSE streaming."""
    r = _get_redis()
    event["run_id"] = run_id
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    r.publish(f"test_lab:run:{run_id}", json.dumps(event, default=str))
    r.close()


def _persist_event(run_id: str, event_type: str, phase: str, message: str, details: dict | None = None, duration_ms: int | None = None):
    """Persist event to DB via sync connection + publish to Redis."""
    from sqlalchemy import create_engine, text
    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("asyncpg", "psycopg2").replace("+asyncpg", "")
    engine = create_engine(sync_url)
    evt_id = f"evt_{datetime.now(timezone.utc).strftime('%H%M%S%f')}"
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO test_run_events (id, run_id, event_type, phase, message, details, timestamp, duration_ms, created_at, updated_at) "
            "VALUES (:id, :run_id, :etype, :phase, :msg, :details, NOW(), :dur, NOW(), NOW())"
        ), {
            "id": evt_id, "run_id": run_id, "etype": event_type, "phase": phase,
            "msg": message, "details": json.dumps(details) if details else None, "dur": duration_ms,
        })
        conn.commit()
    engine.dispose()

    # Also publish to Redis for real-time SSE
    _publish_event(run_id, {
        "id": evt_id, "event_type": event_type, "phase": phase,
        "message": message, "details": details, "duration_ms": duration_ms,
    })


def _update_run(run_id: str, **fields):
    """Update run record via sync connection."""
    from sqlalchemy import create_engine, text
    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("asyncpg", "psycopg2").replace("+asyncpg", "")
    engine = create_engine(sync_url)
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    with engine.connect() as conn:
        conn.execute(text(f"UPDATE test_runs SET {sets}, updated_at = NOW() WHERE id = :id"), {"id": run_id, **fields})
        conn.commit()
    engine.dispose()


def _run_async(coro):
    """Run an async coroutine in a new event loop (for Celery sync workers)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Main orchestrator task ────────────────────────────────────────────


@celery.task(bind=True, name="test_lab.run_test")
def run_test_task(self, run_id: str, scenario_id: str):
    """Execute a full agentic test run as a Celery task.

    Uses stream_printing_messages for real-time agent output capture.
    """
    _persist_event(run_id, "run_created", "orchestrator", "Test run created")
    _update_run(run_id, status="running")
    _persist_event(run_id, "orchestrator_started", "orchestrator", "Celery worker started")

    try:
        _run_async(_execute_test(run_id, scenario_id))
    except Exception as e:
        logger.error(f"Test run {run_id} failed: {e}")
        _persist_event(run_id, "run_failed", "orchestrator", f"Error: {e}")
        _update_run(run_id, status="failed", error_message=str(e)[:1000], ended_at=datetime.now(timezone.utc).isoformat())


async def _execute_test(run_id: str, scenario_id: str):
    """Async orchestration logic using stream_printing_messages."""
    import time
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import get_settings
    from app.models.test_lab import TestScenario, TestRun
    from app.services import agent_registry_service

    engine = create_async_engine(get_settings().DATABASE_URL)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        scenario = await db.get(TestScenario, scenario_id)
        run = await db.get(TestRun, run_id)
        agent_def = await agent_registry_service.get_agent(db, scenario.agent_id)

        if not scenario or not run or not agent_def:
            raise ValueError("Scenario, run, or agent not found")

        t0 = time.time()

        # ── Phase 1: Preparation ──────────────────────────────
        _persist_event(run_id, "orchestrator_tool_call", "orchestrator", "Master calls → prepare_test_scenario",
                       details={"tool_name": "prepare_test_scenario"})
        plan = await _phase_preparation(run_id, db, scenario, agent_def)

        # ── Phase 2: Runtime execution ────────────────────────
        _persist_event(run_id, "orchestrator_tool_call", "orchestrator", "Master calls → execute_target_agent",
                       details={"tool_name": "execute_target_agent"})
        runtime_result = await _phase_runtime(run_id, db, scenario, agent_def)

        duration_ms = int((time.time() - t0) * 1000)

        # Update run with runtime results
        run.final_output = runtime_result.get("final_output")
        run.duration_ms = duration_ms
        run.execution_metadata = {
            "iteration_count": runtime_result.get("iteration_count", 0),
            "message_history": runtime_result.get("message_history", []),
            "runtime_status": runtime_result.get("status"),
        }
        await db.commit()

        # ── Phase 3: Assertions ───────────────────────────────
        _persist_event(run_id, "orchestrator_tool_call", "orchestrator", "Master calls → run_assertion_evaluation",
                       details={"tool_name": "run_assertion_evaluation"})
        assertion_results = await _phase_assertions(run_id, db, scenario, run, runtime_result)

        # ── Phase 4: Diagnostics ──────────────────────────────
        _persist_event(run_id, "orchestrator_tool_call", "orchestrator", "Master calls → run_diagnostic_analysis",
                       details={"tool_name": "run_diagnostic_analysis"})
        diagnostic_results = await _phase_diagnostics(run_id, db, scenario, run, runtime_result, assertion_results)

        # ── Phase 5: Verdict ──────────────────────────────────
        _persist_event(run_id, "orchestrator_tool_call", "orchestrator", "Master calls → compute_final_verdict",
                       details={"tool_name": "compute_final_verdict"})
        await _phase_verdict(run_id, db, run, assertion_results, diagnostic_results)

    await engine.dispose()


# ── Phase implementations ─────────────────────────────────────────────


async def _phase_preparation(run_id, db, scenario, agent_def):
    """Phase 1: Create preparation worker and capture its output via stream_printing_messages."""
    from agentscope.agent import ReActAgent
    from agentscope.tool import Toolkit
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg
    from agentscope.pipeline import stream_printing_messages
    import json

    _persist_event(run_id, "phase_started", "preparation", "Preparation worker started")

    config = {
        "scenario_id": scenario.id, "name": scenario.name, "agent_id": scenario.agent_id,
        "timeout_seconds": scenario.timeout_seconds, "max_iterations": scenario.max_iterations,
        "assertion_count": len(scenario.assertions or []),
        "expected_tools": scenario.expected_tools or [],
        "input_prompt": scenario.input_prompt[:300],
    }

    from app.services.test_lab.orchestrator import _make_model, _make_formatter
    worker = ReActAgent(
        name="preparation_worker",
        sys_prompt="You are a test preparation worker. Analyze the scenario and produce a structured TEST PLAN with: Objective, Target agent, Input, Expected behavior, Assertions, Constraints, Risk factors. Be concise.",
        model=_make_model(), formatter=_make_formatter(),
        toolkit=Toolkit(), memory=InMemoryMemory(), max_iters=1,
    )
    worker.set_console_output_enabled(False)

    task_msg = Msg("user", f"Prepare test plan for:\n{json.dumps(config, indent=2)}\n\nFull prompt: {scenario.input_prompt}", "user")

    # Use stream_printing_messages for real-time output
    async for msg, is_last in stream_printing_messages(agents=[worker], coroutine_task=worker(task_msg)):
        text = msg.get_text_content() if hasattr(msg, "get_text_content") else str(msg)
        if text:
            _persist_event(run_id, "agent_message", "preparation", f"preparation_worker: {text[:100]}...",
                           details={"agent": "preparation_worker", "content": text[:3000]})

    # Get final response from memory
    msgs = await worker.memory.get_memory()
    final_text = ""
    if msgs:
        last = msgs[-1]
        final_text = last.get_text_content() if hasattr(last, "get_text_content") else str(last)

    _persist_event(run_id, "phase_completed", "preparation", "Test plan ready",
                   details={"worker_response": final_text[:3000], **config})
    return final_text


async def _phase_runtime(run_id, db, scenario, agent_def):
    """Phase 2: Execute target agent with stream_printing_messages for live output."""
    import time
    from agentscope.message import Msg
    from agentscope.pipeline import stream_printing_messages
    from app.services.agent_factory import create_agentscope_agent, get_tools_for_agent

    _persist_event(run_id, "handoff_started", "orchestrator", "Dispatching to target agent")
    _persist_event(run_id, "phase_started", "runtime", "Creating target agent")

    tools = get_tools_for_agent(agent_def)
    react_agent = await create_agentscope_agent(
        agent_def, db=db, tools_to_register=tools, max_iters=scenario.max_iterations,
    )

    if react_agent is None:
        _persist_event(run_id, "phase_failed", "runtime", "Agent creation failed")
        return {"status": "failed", "final_output": None, "duration_ms": 0, "iteration_count": 0, "message_history": []}

    # Log MCP connections
    connected_mcps = getattr(react_agent, "_connected_mcps", [])
    for mcp in connected_mcps:
        _persist_event(run_id, "mcp_session_connected", "runtime", f"Connected to {mcp.get('url', '')}",
                       details={"tools": mcp.get("tools", []), "url": mcp.get("url", "")})

    _persist_event(run_id, "run_started", "runtime", "Target agent execution started")

    react_agent.set_console_output_enabled(False)
    task_msg = Msg("user", scenario.input_prompt, "user")
    t0 = time.time()

    # Stream agent messages in real-time
    msg_count = 0
    try:
        async for msg, is_last in stream_printing_messages(
            agents=[react_agent],
            coroutine_task=asyncio.wait_for(react_agent(task_msg), timeout=scenario.timeout_seconds),
        ):
            msg_count += 1
            text = msg.get_text_content() if hasattr(msg, "get_text_content") else ""
            name = getattr(msg, "name", "agent")
            role = getattr(msg, "role", "unknown")

            # Detect content type from blocks
            content_blocks = getattr(msg, "content", None)
            event_type = "agent_message"
            details = {"agent": name, "role": role}

            if isinstance(content_blocks, list):
                for block in content_blocks:
                    btype = block.get("type", "") if isinstance(block, dict) else getattr(block, "type", "")
                    if btype == "tool_use":
                        tool_name = block.get("name", "") if isinstance(block, dict) else getattr(block, "name", "")
                        tool_input = block.get("raw_input", block.get("input", "")) if isinstance(block, dict) else getattr(block, "raw_input", getattr(block, "input", ""))
                        event_type = "tool_call_started"
                        details["tool_name"] = tool_name
                        details["tool_input"] = str(tool_input)[:500]
                    elif btype == "tool_result":
                        tool_name = block.get("name", "") if isinstance(block, dict) else getattr(block, "name", "")
                        output = block.get("output", "") if isinstance(block, dict) else getattr(block, "output", "")
                        if isinstance(output, list):
                            parts = []
                            for b in output:
                                t = b.get("text", str(b)) if isinstance(b, dict) else getattr(b, "text", str(b))
                                parts.append(str(t)[:800])
                            output_text = "\n".join(parts)[:3000]
                        else:
                            output_text = str(output)[:3000]
                        event_type = "tool_call_completed"
                        details["tool_name"] = tool_name
                        details["output_preview"] = output_text
                    elif btype == "thinking":
                        details["thinking"] = (block.get("text", "") if isinstance(block, dict) else getattr(block, "text", ""))[:1000]
                    elif btype == "text":
                        details["content"] = (block.get("text", "") if isinstance(block, dict) else getattr(block, "text", ""))[:2000]

            if text and not details.get("content"):
                details["content"] = text[:2000]

            _persist_event(run_id, event_type, "runtime", f"{name}: {(text or '')[:100]}", details=details)

    except asyncio.TimeoutError:
        duration_ms = int((time.time() - t0) * 1000)
        _persist_event(run_id, "run_timeout", "runtime", f"Timed out after {scenario.timeout_seconds}s")
        return {"status": "timed_out", "final_output": None, "duration_ms": duration_ms, "iteration_count": msg_count, "message_history": []}

    duration_ms = int((time.time() - t0) * 1000)

    # Get final output and message history from memory
    final_output = ""
    message_history = []
    try:
        msgs = await react_agent.memory.get_memory()
        for m in msgs:
            entry = {"role": getattr(m, "role", "unknown"), "name": getattr(m, "name", "")}
            text = m.get_text_content() if hasattr(m, "get_text_content") else ""
            if not text and hasattr(m, "content"):
                raw = m.content
                if isinstance(raw, list):
                    parts = []
                    for block in raw:
                        if isinstance(block, dict):
                            parts.append(block.get("text", str(block))[:500])
                        else:
                            parts.append(getattr(block, "text", str(block))[:500])
                    text = "\n".join(parts)
                elif isinstance(raw, str):
                    text = raw
            entry["content"] = text[:5000]
            message_history.append(entry)
        if msgs:
            last = msgs[-1]
            final_output = last.get_text_content() if hasattr(last, "get_text_content") else str(last.content)[:5000]
    except Exception:
        pass

    _persist_event(run_id, "phase_completed", "runtime", f"Target agent completed ({duration_ms}ms, {msg_count} messages)",
                   details={"duration_ms": duration_ms, "message_count": msg_count})
    _persist_event(run_id, "handoff_completed", "orchestrator", "Target agent execution completed")

    return {
        "status": "completed", "final_output": final_output, "duration_ms": duration_ms,
        "iteration_count": msg_count, "message_history": message_history,
    }


async def _phase_assertions(run_id, db, scenario, run, runtime_result):
    """Phase 3: Deterministic assertions + worker analysis."""
    from agentscope.agent import ReActAgent
    from agentscope.tool import Toolkit
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg
    from agentscope.pipeline import stream_printing_messages
    from app.services.test_lab.assertion_engine import evaluate_assertions
    from app.models.test_lab import TestRunAssertion, TestRunEvent
    from sqlalchemy import select
    import json

    _persist_event(run_id, "assertion_phase_started", "assertions", "Assertion worker started")

    # Get all events
    result = await db.execute(select(TestRunEvent).where(TestRunEvent.run_id == run_id).order_by(TestRunEvent.timestamp))
    all_events = [{"event_type": e.event_type, "details": e.details, "duration_ms": e.duration_ms} for e in result.scalars().all()]

    assertion_results = evaluate_assertions(
        assertion_defs=scenario.assertions or [], events=all_events,
        final_output=run.final_output, duration_ms=run.duration_ms or 0,
        iteration_count=runtime_result.get("iteration_count", 0),
        final_status=runtime_result.get("status", "unknown"),
    )

    # Persist assertions
    for ar in assertion_results:
        ev_type = "assertion_passed" if ar["passed"] else "assertion_failed"
        _persist_event(run_id, ev_type, "assertions", ar["message"])
        db.add(TestRunAssertion(
            run_id=run_id, assertion_type=ar["assertion_type"], target=ar.get("target"),
            expected=ar.get("expected"), actual=ar.get("actual"), passed=ar["passed"],
            critical=ar.get("critical", False), message=ar["message"], details=ar.get("details"),
        ))
    await db.commit()

    # Worker analysis
    passed = sum(1 for a in assertion_results if a["passed"])
    from app.services.test_lab.orchestrator import _make_model, _make_formatter
    worker = ReActAgent(
        name="assertion_worker",
        sys_prompt="You are an assertion evaluation worker. Analyze the results and provide a brief assessment.",
        model=_make_model(), formatter=_make_formatter(),
        toolkit=Toolkit(), memory=InMemoryMemory(), max_iters=1,
    )
    worker.set_console_output_enabled(False)

    summary = json.dumps({"total": len(assertion_results), "passed": passed, "results": [{"type": a["assertion_type"], "passed": a["passed"], "message": a["message"]} for a in assertion_results]})

    async for msg, is_last in stream_printing_messages(agents=[worker], coroutine_task=worker(Msg("user", f"Analyze:\n{summary}", "user"))):
        text = msg.get_text_content() if hasattr(msg, "get_text_content") else ""
        if text:
            _persist_event(run_id, "agent_message", "assertions", f"assertion_worker: {text[:100]}...",
                           details={"agent": "assertion_worker", "content": text[:3000]})

    msgs = await worker.memory.get_memory()
    analysis = msgs[-1].get_text_content() if msgs else ""

    _persist_event(run_id, "phase_completed", "assertions", f"Assertions: {passed}/{len(assertion_results)} passed",
                   details={"worker_response": analysis[:3000], "passed": passed, "total": len(assertion_results)})

    return assertion_results


async def _phase_diagnostics(run_id, db, scenario, run, runtime_result, assertion_results):
    """Phase 4: Deterministic diagnostics + worker analysis."""
    from agentscope.agent import ReActAgent
    from agentscope.tool import Toolkit
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg
    from agentscope.pipeline import stream_printing_messages
    from app.services.test_lab.diagnostic_engine import generate_diagnostics
    from app.models.test_lab import TestRunDiagnostic, TestRunEvent
    from sqlalchemy import select
    import json

    _persist_event(run_id, "diagnostic_phase_started", "diagnostics", "Diagnostic worker started")

    result = await db.execute(select(TestRunEvent).where(TestRunEvent.run_id == run_id).order_by(TestRunEvent.timestamp))
    all_events = [{"event_type": e.event_type, "details": e.details, "duration_ms": e.duration_ms} for e in result.scalars().all()]

    diagnostic_results = generate_diagnostics(
        events=all_events, assertions=assertion_results, expected_tools=scenario.expected_tools,
        duration_ms=run.duration_ms or 0, iteration_count=runtime_result.get("iteration_count", 0),
        max_iterations=scenario.max_iterations, timeout_seconds=scenario.timeout_seconds,
        final_output=run.final_output,
    )

    for dr in diagnostic_results:
        _persist_event(run_id, "diagnostic_generated", "diagnostics", dr["message"],
                       details={"code": dr["code"], "severity": dr["severity"]})
        db.add(TestRunDiagnostic(
            run_id=run_id, code=dr["code"], severity=dr["severity"], message=dr["message"],
            probable_causes=dr.get("probable_causes"), recommendation=dr.get("recommendation"), evidence=dr.get("evidence"),
        ))
    await db.commit()

    # Worker analysis
    from app.services.test_lab.orchestrator import _make_model, _make_formatter
    worker = ReActAgent(
        name="diagnostic_worker",
        sys_prompt="You are a diagnostic analysis worker. Analyze findings and provide recommendations.",
        model=_make_model(), formatter=_make_formatter(),
        toolkit=Toolkit(), memory=InMemoryMemory(), max_iters=1,
    )
    worker.set_console_output_enabled(False)

    diag_summary = json.dumps([{"code": d["code"], "severity": d["severity"], "message": d["message"]} for d in diagnostic_results])

    async for msg, is_last in stream_printing_messages(agents=[worker], coroutine_task=worker(Msg("user", f"Analyze:\n{diag_summary}", "user"))):
        text = msg.get_text_content() if hasattr(msg, "get_text_content") else ""
        if text:
            _persist_event(run_id, "agent_message", "diagnostics", f"diagnostic_worker: {text[:100]}...",
                           details={"agent": "diagnostic_worker", "content": text[:3000]})

    msgs = await worker.memory.get_memory()
    analysis = msgs[-1].get_text_content() if msgs else ""

    _persist_event(run_id, "phase_completed", "diagnostics", f"Diagnostics: {len(diagnostic_results)} findings",
                   details={"worker_response": analysis[:3000], "findings_count": len(diagnostic_results)})

    return diagnostic_results


async def _phase_verdict(run_id, db, run, assertion_results, diagnostic_results):
    """Phase 5: Score + verdict + worker summary."""
    from agentscope.agent import ReActAgent
    from agentscope.tool import Toolkit
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg
    from agentscope.pipeline import stream_printing_messages
    from app.services.test_lab.scoring import compute_score_and_verdict
    import json

    _persist_event(run_id, "report_phase_started", "report", "Verdict worker started")

    score, verdict = compute_score_and_verdict(assertion_results, diagnostic_results)

    from app.services.test_lab.orchestrator import _make_model, _make_formatter
    worker = ReActAgent(
        name="verdict_worker",
        sys_prompt="You are a verdict worker. Produce a clear, concise final test summary.",
        model=_make_model(), formatter=_make_formatter(),
        toolkit=Toolkit(), memory=InMemoryMemory(), max_iters=1,
    )
    worker.set_console_output_enabled(False)

    verdict_data = json.dumps({"score": score, "verdict": verdict,
        "assertions_passed": sum(1 for a in assertion_results if a["passed"]),
        "assertions_total": len(assertion_results), "diagnostics_count": len(diagnostic_results)})

    async for msg, is_last in stream_printing_messages(agents=[worker], coroutine_task=worker(Msg("user", f"Final summary:\n{verdict_data}", "user"))):
        text = msg.get_text_content() if hasattr(msg, "get_text_content") else ""
        if text:
            _persist_event(run_id, "agent_message", "report", f"verdict_worker: {text[:100]}...",
                           details={"agent": "verdict_worker", "content": text[:3000]})

    msgs = await worker.memory.get_memory()
    summary_text = msgs[-1].get_text_content() if msgs else ""

    _persist_event(run_id, "phase_completed", "report", f"Score: {score}/100 — Verdict: {verdict}",
                   details={"worker_response": summary_text[:3000], "score": score, "verdict": verdict})

    # Update run
    _update_run(run_id, score=score, verdict=verdict, status="completed",
                summary=f"Score: {score}/100 — Verdict: {verdict} — {summary_text[:200]}",
                ended_at=datetime.now(timezone.utc).isoformat())

    _persist_event(run_id, "run_completed", "orchestrator", f"Run completed: {verdict} ({score}/100)")
