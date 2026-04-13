"""Test Lab Execution Engine.

Single source of truth for test execution logic.
Extracted from orchestrator.py for clean separation of concerns.

Architecture:
  execute_test_run(run_id, scenario_id)   ← called by Celery / batch
  execute_test_from_request(request)      ← called by interactive sessions

  Both run the same 5-phase deterministic pipeline:
    Phase 1: Preparation  (SubAgent generates test plan)
    Phase 2: Runtime      (real target agent via target_agent_runner)
    Phase 3: Assertions   (deterministic via assertion_engine)
    Phase 4: Diagnostics  (deterministic via diagnostic_engine)
    Phase 5: Verdict      (deterministic scoring + SubAgent summary)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import redis

from app.core.config import get_settings
from app.models.base import new_id

logger = logging.getLogger("orkestra.test_lab.execution_engine")


# ── Async runner (shared by orchestrator_agent.py and session_mcp.py) ────────


def _run_async(coro):
    """Run an async coroutine from a synchronous context.

    Handles the case where an event loop is already running (e.g. inside
    Uvicorn/FastAPI) by dispatching to a ThreadPoolExecutor.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)

# ── Phase constants ───────────────────────────────────────────────────────────

PHASES = ["preparation", "runtime", "assertions", "diagnostics", "verdict"]

# ── Shared sync engine singleton ──────────────────────────────────────────────

_sync_engine = None


def _get_sync_engine():
    """Return (or lazily create) the shared synchronous SQLAlchemy engine."""
    global _sync_engine
    if _sync_engine is None:
        from sqlalchemy import create_engine

        settings = get_settings()
        sync_url = getattr(settings, "DATABASE_URL_SYNC", None)
        if not sync_url:
            sync_url = (
                settings.DATABASE_URL
                .replace("+asyncpg", "")
                .replace("asyncpg", "psycopg2")
            )
        _sync_engine = create_engine(sync_url, pool_size=5, max_overflow=3)
    return _sync_engine


# ── Event publishing ──────────────────────────────────────────────────────────


def emit_event(
    run_id: str,
    event_type: str,
    phase: str,
    message: str,
    details: dict | None = None,
    duration_ms: int | None = None,
):
    """Persist an event to ``test_run_events`` and publish to Redis pub/sub.

    Event IDs use the ``tevt_`` prefix to match the model convention.
    """
    from sqlalchemy import text

    settings = get_settings()
    evt_id = new_id("tevt_")

    engine = _get_sync_engine()
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO test_run_events "
                "(id, run_id, event_type, phase, message, details, timestamp, duration_ms, created_at, updated_at) "
                "VALUES (:id, :rid, :et, :ph, :msg, :det, NOW(), :dur, NOW(), NOW())"
            ),
            {
                "id": evt_id,
                "rid": run_id,
                "et": event_type,
                "ph": phase,
                "msg": message,
                "det": json.dumps(details) if details else None,
                "dur": duration_ms,
            },
        )
        conn.commit()

    # Publish to Redis for SSE streaming (best-effort)
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.publish(
            f"test_lab:run:{run_id}",
            json.dumps(
                {
                    "id": evt_id,
                    "event_type": event_type,
                    "phase": phase,
                    "message": message,
                    "details": details,
                    "duration_ms": duration_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                default=str,
            ),
        )
        r.close()
    except Exception:
        pass


# ── Colonnes autorisées pour update_run ──────────────────────────────────

_ALLOWED_UPDATE_FIELDS = frozenset({
    "status",
    "final_output",
    "score",
    "verdict",
    "summary",
    "error_message",
    "assertion_results",
    "diagnostic_results",
    "iteration_count",
    "duration_ms",
    "started_at",
    "ended_at",
})


def update_run(run_id: str, **fields):
    """Update a ``test_runs`` row via raw SQL.

    Only columns in ``_ALLOWED_UPDATE_FIELDS`` are accepted to prevent
    SQL injection via crafted column names.
    """
    from sqlalchemy import text

    unknown = set(fields.keys()) - _ALLOWED_UPDATE_FIELDS
    if unknown:
        raise ValueError(f"update_run: disallowed fields {unknown!r}")
    if not fields:
        return

    sets = ", ".join(f"{k} = :{k}" for k in fields)
    engine = _get_sync_engine()
    with engine.connect() as conn:
        conn.execute(
            text(f"UPDATE test_runs SET {sets}, updated_at = NOW() WHERE id = :id"),
            {"id": run_id, **fields},
        )
        conn.commit()


# ── Config loader ─────────────────────────────────────────────────────────────


def _get_config_sync() -> dict:
    """Load test lab config from ``test_lab_config`` table using the shared engine."""
    from sqlalchemy import text

    config: dict = {
        "orchestrator": {"provider": "ollama", "host": "", "api_key": "", "model": "gpt-oss:20b-cloud", "thinking": False},
        "workers": {
            "preparation": {
                "prompt": "You are a test preparation worker. Produce a structured TEST PLAN.",
                "model": None,
            },
            "assertion": {"prompt": "Analyze assertion results briefly.", "model": None},
            "diagnostic": {
                "prompt": "Analyze diagnostic findings and recommend fixes.",
                "model": None,
            },
            "verdict": {"prompt": "Produce a concise final test summary.", "model": None},
        },
    }
    try:
        engine = _get_sync_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT key, value FROM test_lab_config"))
            for row in result.fetchall():
                if row[0] in config and isinstance(config[row[0]], dict):
                    config[row[0]] = {**config[row[0]], **row[1]}
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Failed to load test_lab_config from DB, using defaults: %s",
            e,
            exc_info=False,
        )
    return config


# ── LLM model factory ─────────────────────────────────────────────────────────


def _make_model(worker_name: str | None = None):
    """Create the appropriate chat model for subagents, reading config from DB."""
    config = _get_config_sync()
    orch = config.get("orchestrator", {})

    model_name = None
    worker_cfg: dict = {}
    if worker_name and worker_name in config.get("workers", {}):
        worker_cfg = config["workers"][worker_name] or {}
        model_name = worker_cfg.get("model")
    if not model_name:
        model_name = orch.get("model", "mistral")

    provider = orch.get("provider", "ollama")
    api_key = orch.get("api_key", "") or ""
    settings = get_settings()

    # thinking: worker-level overrides orchestrator-level; None = model default (not passed)
    thinking: bool | None = None
    if "thinking" in worker_cfg and worker_cfg["thinking"] is not None:
        thinking = bool(worker_cfg["thinking"])
    elif "thinking" in orch and orch["thinking"] is not None:
        thinking = bool(orch["thinking"])

    if provider == "openai":
        from agentscope.model import OpenAIChatModel
        base_url = orch.get("host", "") or getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")
        key = api_key or getattr(settings, "OPENAI_API_KEY", "")
        return OpenAIChatModel(model_name=model_name, api_key=key, base_url=base_url)
    else:
        from agentscope.model import OllamaChatModel
        host = orch.get("host", "") or getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
        kwargs: dict = {"model_name": model_name, "host": host, "stream": False}
        if api_key:
            kwargs["api_key"] = api_key
        if thinking is not None:
            kwargs["enable_thinking"] = thinking
        return OllamaChatModel(**kwargs)


def _make_formatter():
    config = _get_config_sync()
    provider = config.get("orchestrator", {}).get("provider", "ollama")
    if provider == "openai":
        from agentscope.formatter import OpenAIChatFormatter
        return OpenAIChatFormatter()
    from agentscope.formatter import OllamaChatFormatter
    return OllamaChatFormatter()


def _load_skills_text(skill_ids: list[str]) -> str:
    """Load skill content from DB by IDs using the shared engine."""
    from sqlalchemy import text

    parts: list[str] = []
    try:
        engine = _get_sync_engine()
        with engine.connect() as conn:
            for sid in skill_ids:
                r = conn.execute(
                    text(
                        "SELECT label, category, description, behavior_templates, output_guidelines "
                        "FROM skill_definitions WHERE id = :id"
                    ),
                    {"id": sid},
                )
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
    return "\n\n".join(parts)


# ── SubAgent helper (renamed from run_worker) ─────────────────────────────────


async def run_subagent(
    run_id: str,
    phase: str,
    worker_name: str,
    default_prompt: str,
    user_prompt: str,
) -> str:
    """Create a ReActAgent subagent, run it once, and return the text response.

    Used in the Preparation and Verdict phases for LLM-assisted tasks.
    NOT used for deterministic scoring.
    """
    from agentscope.agent import ReActAgent
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg
    from agentscope.tool import Toolkit

    config = _get_config_sync()
    agent_key = worker_name.replace("_agent", "").replace("_worker", "")
    worker_cfg = config.get("workers", {}).get(agent_key, {})
    sys_prompt = worker_cfg.get("prompt") or default_prompt

    # Inject skills into the system prompt
    skill_ids = worker_cfg.get("skills") or []
    if skill_ids:
        skills_text = _load_skills_text(skill_ids)
        if skills_text:
            sys_prompt = f"{sys_prompt}\n\n## SKILLS\n\n{skills_text}"

    worker = ReActAgent(
        name=worker_name,
        sys_prompt=sys_prompt,
        model=_make_model(agent_key),
        formatter=_make_formatter(),
        toolkit=Toolkit(),
        memory=InMemoryMemory(),
        max_iters=1,
    )

    task_msg = Msg("user", user_prompt, "user")
    try:
        async with asyncio.timeout(45):  # 45s max per LLM call
            response = await worker(task_msg)
    except TimeoutError:
        logger.warning(
            "LLM timeout in run_subagent: phase=%s worker=%s run_id=%s",
            phase, worker_name, run_id,
        )
        emit_event(
            run_id,
            "subagent_timeout",
            phase,
            f"[{worker_name}] LLM did not respond within 45s",
            details={"worker": worker_name, "timeout_s": 45},
        )
        return f"[TIMEOUT] {worker_name} did not respond in 45s"

    text = (
        response.get_text_content()
        if hasattr(response, "get_text_content")
        else str(response)
    )

    emit_event(
        run_id,
        "agent_message",
        phase,
        f"{worker_name}: {text[:100]}...",
        details={"agent": worker_name, "content": text[:3000]},
    )

    return text or ""


# ── Main pipeline ─────────────────────────────────────────────────────────────


async def execute_test_run(run_id: str, scenario_id: str):
    """Run the 5-phase deterministic test pipeline.

    This is the primary entry point used by the Celery task (batch mode).
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.test_lab import (
        TestRun,
        TestRunAssertion,
        TestRunDiagnostic,
        TestRunEvent,
        TestScenario,
    )
    from app.services.test_lab.assertion_engine import evaluate_assertions
    from app.services.test_lab.diagnostic_engine import generate_diagnostics
    from app.services.test_lab.scoring import compute_score_and_verdict
    from app.services.test_lab.target_agent_runner import (
        _build_execution_events,
        run_target_agent,
    )

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        scenario = await db.get(TestScenario, scenario_id)
        run = await db.get(TestRun, run_id)

        if not scenario or not run:
            raise ValueError(f"Scenario '{scenario_id}' or run '{run_id}' not found")

        update_run(run_id, status="running")
        emit_event(run_id, "run_created", "orchestrator", "Test run created")
        emit_event(run_id, "orchestrator_started", "orchestrator", "Orchestrator started")
        t0 = time.time()

        # ── Phase 1: Preparation ──────────────────────────────────────────────
        emit_event(
            run_id,
            "orchestrator_tool_call",
            "orchestrator",
            "→ prepare_test_scenario",
            details={"tool_name": "prepare_test_scenario"},
        )
        emit_event(run_id, "phase_started", "preparation", "Preparation subagent started")

        config_summary = json.dumps(
            {
                "name": scenario.name,
                "agent_id": scenario.agent_id,
                "timeout": scenario.timeout_seconds,
                "max_iters": scenario.max_iterations,
                "assertions": len(scenario.assertions or []),
                "expected_tools": scenario.expected_tools or [],
            }
        )
        plan = await run_subagent(
            run_id,
            "preparation",
            "preparation_agent",
            "You are a test preparation worker. Produce a structured TEST PLAN: "
            "Objective, Target agent, Input, Expected behavior, Assertions, Constraints, Risks. Be concise.",
            f"Prepare test plan for:\n{config_summary}\n\nPrompt: {scenario.input_prompt}",
        )
        emit_event(
            run_id,
            "phase_completed",
            "preparation",
            "Test plan ready",
            details={"worker_response": plan[:3000]},
        )

        # ── Phase 2: Runtime ──────────────────────────────────────────────────
        emit_event(
            run_id,
            "orchestrator_tool_call",
            "orchestrator",
            "→ execute_target_agent",
            details={"tool_name": "execute_target_agent"},
        )
        emit_event(run_id, "phase_started", "runtime", "Creating target agent")

        runtime_result = await run_target_agent(
            db=db,
            agent_id=scenario.agent_id,
            agent_version=None,
            input_prompt=scenario.input_prompt,
            allowed_tools=scenario.allowed_tools,
            timeout_seconds=scenario.timeout_seconds,
            max_iterations=scenario.max_iterations,
        )

        duration_ms = int((time.time() - t0) * 1000)
        run.final_output = runtime_result.final_output
        run.duration_ms = duration_ms
        run.execution_metadata = {
            "iteration_count": runtime_result.iteration_count,
            "message_history": runtime_result.message_history,
            "status": runtime_result.status,
        }
        await db.commit()

        # Emit per-message events from the agent's execution
        for evt in _build_execution_events(runtime_result.message_history):
            emit_event(run_id, evt["event_type"], evt["phase"], str(evt.get("content", ""))[:200])

        emit_event(
            run_id,
            "phase_completed",
            "runtime",
            f"Agent completed ({duration_ms}ms)",
            details={"duration_ms": duration_ms, "status": runtime_result.status},
        )
        emit_event(run_id, "orchestrator_tool_call", "orchestrator", "← execute_target_agent completed")

        # ── Phase 3: Assertions ───────────────────────────────────────────────
        emit_event(
            run_id,
            "orchestrator_tool_call",
            "orchestrator",
            "→ run_assertion_evaluation",
            details={"tool_name": "run_assertion_evaluation"},
        )
        emit_event(run_id, "assertion_phase_started", "assertions", "Assertion evaluation started")

        result = await db.execute(
            select(TestRunEvent)
            .where(TestRunEvent.run_id == run_id)
            .order_by(TestRunEvent.timestamp)
        )
        all_events = [
            {
                "event_type": e.event_type,
                "details": e.details,
                "duration_ms": e.duration_ms,
            }
            for e in result.scalars().all()
        ]

        assertion_results = evaluate_assertions(
            assertion_defs=scenario.assertions or [],
            events=all_events,
            final_output=run.final_output,
            duration_ms=duration_ms,
            iteration_count=runtime_result.iteration_count,
            final_status=runtime_result.status,
        )

        for ar in assertion_results:
            emit_event(
                run_id,
                "assertion_passed" if ar["passed"] else "assertion_failed",
                "assertions",
                ar["message"],
            )
            db.add(
                TestRunAssertion(
                    run_id=run_id,
                    assertion_type=ar["assertion_type"],
                    target=ar.get("target"),
                    expected=ar.get("expected"),
                    actual=ar.get("actual"),
                    passed=ar["passed"],
                    critical=ar.get("critical", False),
                    message=ar["message"],
                    details=ar.get("details"),
                )
            )
        await db.commit()

        passed = sum(1 for a in assertion_results if a["passed"])
        analysis = await run_subagent(
            run_id,
            "assertions",
            "assertion_agent",
            "Analyze assertion results briefly.",
            json.dumps(
                {
                    "passed": passed,
                    "total": len(assertion_results),
                    "results": [
                        {
                            "type": a["assertion_type"],
                            "passed": a["passed"],
                            "message": a["message"],
                        }
                        for a in assertion_results
                    ],
                }
            ),
        )
        emit_event(
            run_id,
            "phase_completed",
            "assertions",
            f"Assertions: {passed}/{len(assertion_results)} passed",
            details={
                "worker_response": analysis[:3000],
                "passed": passed,
                "total": len(assertion_results),
            },
        )

        # ── Phase 4: Diagnostics ──────────────────────────────────────────────
        emit_event(
            run_id,
            "orchestrator_tool_call",
            "orchestrator",
            "→ run_diagnostic_analysis",
            details={"tool_name": "run_diagnostic_analysis"},
        )
        emit_event(run_id, "diagnostic_phase_started", "diagnostics", "Diagnostic analysis started")

        diagnostic_results = generate_diagnostics(
            events=all_events,
            assertions=assertion_results,
            expected_tools=scenario.expected_tools,
            duration_ms=duration_ms,
            iteration_count=runtime_result.iteration_count,
            max_iterations=scenario.max_iterations,
            timeout_seconds=scenario.timeout_seconds,
            final_output=run.final_output,
        )

        for dr in diagnostic_results:
            emit_event(
                run_id,
                "diagnostic_generated",
                "diagnostics",
                dr["message"],
                details={"code": dr["code"], "severity": dr["severity"]},
            )
            db.add(
                TestRunDiagnostic(
                    run_id=run_id,
                    code=dr["code"],
                    severity=dr["severity"],
                    message=dr["message"],
                    probable_causes=dr.get("probable_causes"),
                    recommendation=dr.get("recommendation"),
                    evidence=dr.get("evidence"),
                )
            )
        await db.commit()

        diag_analysis = await run_subagent(
            run_id,
            "diagnostics",
            "diagnostic_agent",
            "Analyze diagnostic findings and recommend fixes.",
            json.dumps(
                [
                    {"code": d["code"], "severity": d["severity"], "message": d["message"]}
                    for d in diagnostic_results
                ]
            ),
        )
        emit_event(
            run_id,
            "phase_completed",
            "diagnostics",
            f"Diagnostics: {len(diagnostic_results)} findings",
            details={
                "worker_response": diag_analysis[:3000],
                "count": len(diagnostic_results),
            },
        )

        # ── Phase 5: Verdict ──────────────────────────────────────────────────
        emit_event(
            run_id,
            "orchestrator_tool_call",
            "orchestrator",
            "→ compute_final_verdict",
            details={"tool_name": "compute_final_verdict"},
        )
        emit_event(run_id, "report_phase_started", "verdict", "Computing verdict")

        score, verdict = compute_score_and_verdict(assertion_results, diagnostic_results)

        summary = await run_subagent(
            run_id,
            "verdict",
            "verdict_agent",
            "Produce a concise final test summary.",
            json.dumps(
                {
                    "score": score,
                    "verdict": verdict,
                    "assertions_passed": passed,
                    "assertions_total": len(assertion_results),
                    "diagnostics": len(diagnostic_results),
                }
            ),
        )
        emit_event(
            run_id,
            "phase_completed",
            "verdict",
            f"Score: {score}/100 — Verdict: {verdict}",
            details={"worker_response": summary[:3000], "score": score, "verdict": verdict},
        )

        update_run(
            run_id,
            score=score,
            verdict=verdict,
            status="completed",
            summary=f"Score: {score}/100 — Verdict: {verdict} — {summary[:200]}",
            ended_at=datetime.now(timezone.utc).isoformat(),
        )
        emit_event(
            run_id,
            "run_completed",
            "orchestrator",
            f"Run completed: {verdict} ({score}/100)",
        )

    await engine.dispose()


# ── Interactive entry point ───────────────────────────────────────────────────


async def execute_test_from_request(request: "TestExecutionRequest") -> dict:
    """Create a temporary scenario + run from the request, then run the pipeline.

    Entry point for interactive (non-batch) sessions.

    Returns a dict with ``run_id``, ``scenario_id``, ``verdict``, and ``score``.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    scenario_id = new_id("scn_")
    run_id = new_id("trun_")

    async with Session() as db:
        # Persist a temporary scenario row
        await db.execute(
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
                "name": request.objective[:255],
                "desc": f"Interactive run — {request.objective[:200]}",
                "agent_id": request.agent_id,
                "prompt": request.input_prompt,
                "payload": json.dumps(request.input_payload) if request.input_payload else None,
                "allowed": json.dumps(request.allowed_tools),
                "expected": json.dumps(request.expected_tools),
                "timeout": request.timeout_seconds,
                "max_iters": request.max_iterations,
                "retry": request.retry_count,
                "assertions": json.dumps(request.assertions),
                "tags": json.dumps(request.tags),
            },
        )

        # Persist an initial run row
        await db.execute(
            text(
                "INSERT INTO test_runs "
                "(id, scenario_id, agent_id, agent_version, status, created_at, updated_at) "
                "VALUES (:id, :sid, :agent_id, :version, 'queued', NOW(), NOW())"
            ),
            {
                "id": run_id,
                "sid": scenario_id,
                "agent_id": request.agent_id,
                "version": "interactive",
            },
        )
        await db.commit()

    await engine.dispose()

    # Delegate to the main pipeline
    await execute_test_run(run_id, scenario_id)

    return {"run_id": run_id, "scenario_id": scenario_id}
