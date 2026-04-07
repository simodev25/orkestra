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


# ── Event publishing ──────────────────────────────────────────────────


def emit(run_id: str, event_type: str, phase: str, message: str,
         details: dict | None = None, duration_ms: int | None = None):
    """Persist event to DB + publish to Redis pub/sub for SSE."""
    from sqlalchemy import create_engine, text
    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("asyncpg", "psycopg2").replace("+asyncpg", "")
    evt_id = f"evt_{datetime.now(timezone.utc).strftime('%H%M%S%f')}"

    engine = create_engine(sync_url)
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO test_run_events (id, run_id, event_type, phase, message, details, timestamp, duration_ms, created_at, updated_at) "
            "VALUES (:id, :rid, :et, :ph, :msg, :det, NOW(), :dur, NOW(), NOW())"
        ), {"id": evt_id, "rid": run_id, "et": event_type, "ph": phase,
            "msg": message, "det": json.dumps(details) if details else None, "dur": duration_ms})
        conn.commit()
    engine.dispose()

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
    from sqlalchemy import create_engine, text
    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("asyncpg", "psycopg2").replace("+asyncpg", "")
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    engine = create_engine(sync_url)
    with engine.connect() as conn:
        conn.execute(text(f"UPDATE test_runs SET {sets}, updated_at = NOW() WHERE id = :id"), {"id": run_id, **fields})
        conn.commit()
    engine.dispose()


# ── LLM model factory ────────────────────────────────────────────────


def make_model():
    """Create the LLM for worker agents (gpt-oss:20b-cloud via Ollama)."""
    from agentscope.model import OllamaChatModel
    settings = get_settings()
    host = settings.OLLAMA_HOST
    # Docker: replace localhost with host.docker.internal
    import os
    if os.path.exists("/.dockerenv") or os.environ.get("ORKESTRA_DATABASE_URL", "").startswith("postgresql"):
        host = host.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
    return OllamaChatModel(model_name="gpt-oss:20b-cloud", host=host, stream=False)


def make_formatter():
    from agentscope.formatter import OllamaChatFormatter
    return OllamaChatFormatter()


# ── Worker helper ─────────────────────────────────────────────────────


async def run_worker(run_id: str, phase: str, worker_name: str, sys_prompt: str, user_prompt: str) -> str:
    """Create a worker ReActAgent, run it, capture output via stream_printing_messages."""
    from agentscope.agent import ReActAgent
    from agentscope.tool import Toolkit
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg
    from agentscope.pipeline import stream_printing_messages

    worker = ReActAgent(
        name=worker_name, sys_prompt=sys_prompt,
        model=make_model(), formatter=make_formatter(),
        toolkit=Toolkit(), memory=InMemoryMemory(), max_iters=1,
    )
    worker.set_console_output_enabled(False)

    task_msg = Msg("user", user_prompt, "user")

    async for msg, is_last in stream_printing_messages(agents=[worker], coroutine_task=worker(task_msg)):
        text = msg.get_text_content() if hasattr(msg, "get_text_content") else ""
        if text:
            emit(run_id, "agent_message", phase, f"{worker_name}: {text[:100]}...",
                 details={"agent": worker_name, "content": text[:3000]})

    # Get final response
    msgs = await worker.memory.get_memory()
    return msgs[-1].get_text_content() if msgs else ""


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
        plan = await run_worker(run_id, "preparation", "preparation_worker",
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
        analysis = await run_worker(run_id, "assertions", "assertion_worker",
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

        diag_analysis = await run_worker(run_id, "diagnostics", "diagnostic_worker",
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

        summary = await run_worker(run_id, "report", "verdict_worker",
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
    react_agent.set_console_output_enabled(False)
    task_msg = Msg("user", scenario.input_prompt, "user")
    t0 = time.time()
    msg_count = 0

    try:
        async for msg, is_last in stream_printing_messages(
            agents=[react_agent],
            coroutine_task=asyncio.wait_for(react_agent(task_msg), timeout=scenario.timeout_seconds),
        ):
            msg_count += 1
            name = getattr(msg, "name", "agent")
            text = msg.get_text_content() if hasattr(msg, "get_text_content") else ""

            # Detect content type
            event_type = "agent_message"
            details = {"agent": name}
            content_blocks = getattr(msg, "content", None)

            if isinstance(content_blocks, list):
                for block in content_blocks:
                    bt = block.get("type", "") if isinstance(block, dict) else getattr(block, "type", "")
                    if bt == "tool_use":
                        tool_name = block.get("name", "") if isinstance(block, dict) else getattr(block, "name", "")
                        tool_input = block.get("raw_input", block.get("input", "")) if isinstance(block, dict) else getattr(block, "raw_input", getattr(block, "input", ""))
                        event_type = "tool_call_started"
                        details.update({"tool_name": tool_name, "tool_input": str(tool_input)[:500]})
                    elif bt == "tool_result":
                        tool_name = block.get("name", "") if isinstance(block, dict) else getattr(block, "name", "")
                        output = block.get("output", "") if isinstance(block, dict) else getattr(block, "output", "")
                        if isinstance(output, list):
                            output_text = "\n".join(
                                str(b.get("text", b) if isinstance(b, dict) else getattr(b, "text", b))[:800] for b in output)[:3000]
                        else:
                            output_text = str(output)[:3000]
                        event_type = "tool_call_completed"
                        details.update({"tool_name": tool_name, "output_preview": output_text})
                    elif bt == "thinking":
                        t = block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
                        details["thinking"] = t[:1000]
                    elif bt == "text":
                        t = block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
                        details["content"] = t[:2000]

            if text and "content" not in details:
                details["content"] = text[:2000]

            emit(run_id, event_type, "runtime", f"{name}: {(text or '')[:100]}", details=details)

    except asyncio.TimeoutError:
        emit(run_id, "run_timeout", "runtime", f"Timed out after {scenario.timeout_seconds}s")
        return {"status": "timed_out", "final_output": None, "duration_ms": int((time.time() - t0) * 1000),
                "iteration_count": msg_count, "message_history": []}

    duration_ms = int((time.time() - t0) * 1000)

    # Extract final output + history from memory
    final_output = ""
    message_history = []
    try:
        msgs = await react_agent.memory.get_memory()
        for m in msgs:
            text = m.get_text_content() if hasattr(m, "get_text_content") else ""
            if not text and hasattr(m, "content"):
                raw = m.content
                if isinstance(raw, list):
                    parts = []
                    for b in raw:
                        t = b.get("text", str(b)) if isinstance(b, dict) else getattr(b, "text", str(b))
                        parts.append(str(t)[:500])
                    text = "\n".join(parts)
                elif isinstance(raw, str):
                    text = raw
            message_history.append({"role": getattr(m, "role", ""), "name": getattr(m, "name", ""), "content": text[:5000]})
        if msgs:
            last = msgs[-1]
            final_output = last.get_text_content() if hasattr(last, "get_text_content") else str(last.content)[:5000]
    except Exception:
        pass

    return {"status": "completed", "final_output": final_output, "duration_ms": duration_ms,
            "iteration_count": msg_count, "message_history": message_history}
