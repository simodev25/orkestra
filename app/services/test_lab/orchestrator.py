"""Central test orchestrator — Agent-as-Tool pattern from AgentScope docs.

Each phase is a worker ReActAgent created dynamically by tool functions.
The master orchestrator delegates to these workers via tool calls.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_lab import TestRun, TestRunEvent, TestRunAssertion, TestRunDiagnostic, TestScenario

logger = logging.getLogger("orkestra.test_lab.orchestrator")

# ── Shared state ──────────────────────────────────────────────────────

_db: AsyncSession | None = None
_run: TestRun | None = None
_scenario: TestScenario | None = None
_agent_def: Any = None
_runtime_result: dict | None = None
_assertion_results: list[dict] = []
_diagnostic_results: list[dict] = []


async def _emit(etype: str, phase: str, msg: str, details: dict | None = None, dur: int | None = None):
    if _db and _run:
        _db.add(TestRunEvent(run_id=_run.id, event_type=etype, phase=phase, message=msg, details=details, duration_ms=dur))
        await _db.commit()  # Commit immediately so SSE can see it


def _make_model():
    """Create the LLM model for worker agents."""
    from agentscope.model import OllamaChatModel
    from app.services.agent_factory import _docker_safe_host
    from app.core.config import get_settings
    host = _docker_safe_host(get_settings().OLLAMA_HOST)
    return OllamaChatModel(model_name="gpt-oss:20b-cloud", host=host, stream=False)


def _make_formatter():
    from app.llm.provider import get_formatter
    return get_formatter()


def _tool_response(text: str):
    from agentscope.tool import ToolResponse
    from agentscope.message import TextBlock
    return ToolResponse(content=[TextBlock(type="text", text=text)])


# ── Worker tool functions (Agent-as-Tool pattern) ─────────────────────


async def prepare_test_scenario(scenario_summary: str) -> Any:
    """Create a preparation worker agent to validate the test scenario.

    Args:
        scenario_summary: A description of what scenario to validate.

    Returns:
        ToolResponse with the validation results.
    """
    from agentscope.agent import ReActAgent
    from agentscope.tool import Toolkit
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg

    await _emit("orchestrator_tool_call", "orchestrator", f"Master calls → prepare_test_scenario", details={
        "tool_name": "prepare_test_scenario", "tool_input": scenario_summary[:300],
    })
    await _emit("phase_started", "preparation", "Preparation worker started")

    config = {
        "scenario_id": _scenario.id,
        "name": _scenario.name,
        "agent_id": _scenario.agent_id,
        "timeout_seconds": _scenario.timeout_seconds,
        "max_iterations": _scenario.max_iterations,
        "assertion_count": len(_scenario.assertions or []),
        "expected_tools": _scenario.expected_tools or [],
        "input_prompt_preview": _scenario.input_prompt[:200],
    }

    worker = ReActAgent(
        name="preparation_worker",
        sys_prompt="""You are a test preparation worker. Your job is to analyze the scenario and produce a structured TEST PLAN.

Your test plan must include:
1. **Objective** — what is being tested and why
2. **Target agent** — which agent, what is its purpose
3. **Input** — what prompt/data will be sent
4. **Expected behavior** — what the agent should do (tools to call, output format)
5. **Assertions** — what will be checked automatically
6. **Constraints** — timeout, max iterations, allowed tools
7. **Risk factors** — what could go wrong

Be concise. Use bullet points. This plan will guide the test execution.""",
        model=_make_model(),
        formatter=_make_formatter(),
        toolkit=Toolkit(),
        memory=InMemoryMemory(),
        max_iters=1,
    )

    res = await worker(Msg("user", f"Prepare a test plan for this scenario:\n{json.dumps(config, indent=2)}\n\nFull input prompt: {_scenario.input_prompt}", "user"))
    text = res.get_text_content() if hasattr(res, "get_text_content") else str(res)

    await _emit("phase_completed", "preparation", "Test plan ready", details={
        **config,
        "worker_response": text[:3000],
    })
    return _tool_response(f"Test plan ready.\nConfig: {json.dumps(config)}\nPlan: {text}")


async def execute_target_agent(test_instructions: str) -> Any:
    """Create and execute the real target agent to test its behavior.

    Args:
        test_instructions: Instructions about what to execute and observe.

    Returns:
        ToolResponse with the execution results including events, output, and metrics.
    """
    global _runtime_result

    await _emit("orchestrator_tool_call", "orchestrator", f"Master calls → execute_target_agent", details={
        "tool_name": "execute_target_agent", "tool_input": test_instructions[:300],
    })
    await _emit("handoff_started", "orchestrator", "Dispatching target agent execution")

    from app.services.test_lab.runtime_adapter import execute_with_event_capture

    _runtime_result = await execute_with_event_capture(
        db=_db,
        agent_def=_agent_def,
        input_prompt=_scenario.input_prompt,
        max_iterations=_scenario.max_iterations,
        timeout_seconds=_scenario.timeout_seconds,
        run_id=_run.id,
    )

    # Runtime events already persisted live by RuntimeEventCollector
    await _db.commit()

    _run.final_output = _runtime_result.get("final_output")
    _run.duration_ms = _runtime_result.get("duration_ms", 0)
    _run.execution_metadata = {
        "iteration_count": _runtime_result.get("iteration_count", 0),
        "message_history": _runtime_result.get("message_history", []),
        "runtime_status": _runtime_result.get("status"),
        "error": _runtime_result.get("error"),
    }
    if _runtime_result["status"] in ("failed", "timed_out"):
        _run.status = _runtime_result["status"]
        _run.error_message = _runtime_result.get("error")

    await _emit("handoff_completed", "orchestrator", "Target agent execution completed",
                details={"status": _runtime_result["status"], "duration_ms": _runtime_result.get("duration_ms", 0)})

    summary = json.dumps({
        "status": _runtime_result["status"],
        "duration_ms": _runtime_result.get("duration_ms", 0),
        "iterations": _runtime_result.get("iteration_count", 0),
        "output_preview": (_runtime_result.get("final_output") or "")[:500],
    })
    return _tool_response(f"Target agent execution completed.\n{summary}")


async def run_assertion_evaluation(execution_summary: str) -> Any:
    """Create an assertion worker agent to evaluate test assertions.

    Args:
        execution_summary: Summary of the execution results to evaluate.

    Returns:
        ToolResponse with assertion results.
    """
    global _assertion_results
    from agentscope.agent import ReActAgent
    from agentscope.tool import Toolkit
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg

    await _emit("orchestrator_tool_call", "orchestrator", f"Master calls → run_assertion_evaluation", details={
        "tool_name": "run_assertion_evaluation", "tool_input": execution_summary[:300],
    })
    await _emit("assertion_phase_started", "assertions", "Assertion worker started")

    # Run deterministic assertions
    from app.services.test_lab.assertion_engine import evaluate_assertions as _eval
    from sqlalchemy import select

    result = await _db.execute(
        select(TestRunEvent).where(TestRunEvent.run_id == _run.id).order_by(TestRunEvent.timestamp)
    )
    all_events = [{"event_type": e.event_type, "details": e.details, "duration_ms": e.duration_ms} for e in result.scalars().all()]

    _assertion_results = _eval(
        assertion_defs=_scenario.assertions or [], events=all_events,
        final_output=_run.final_output, duration_ms=_run.duration_ms or 0,
        iteration_count=(_runtime_result or {}).get("iteration_count", 0),
        final_status=(_runtime_result or {}).get("status", "unknown"),
    )

    for ar in _assertion_results:
        await _emit("assertion_passed" if ar["passed"] else "assertion_failed", "assertions", ar["message"])
        _db.add(TestRunAssertion(
            run_id=_run.id, assertion_type=ar["assertion_type"], target=ar.get("target"),
            expected=ar.get("expected"), actual=ar.get("actual"), passed=ar["passed"],
            critical=ar.get("critical", False), message=ar["message"], details=ar.get("details"),
        ))
    await _db.flush()

    passed = sum(1 for a in _assertion_results if a["passed"])
    assertion_summary = json.dumps({"total": len(_assertion_results), "passed": passed, "results": [{"type": a["assertion_type"], "passed": a["passed"], "message": a["message"]} for a in _assertion_results]})

    # Worker agent analyzes the results
    worker = ReActAgent(
        name="assertion_worker",
        sys_prompt="You are an assertion evaluation worker. Analyze the assertion results and provide a brief assessment.",
        model=_make_model(), formatter=_make_formatter(),
        toolkit=Toolkit(), memory=InMemoryMemory(), max_iters=1,
    )
    res = await worker(Msg("user", f"Analyze these assertion results:\n{assertion_summary}", "user"))
    analysis = res.get_text_content() if hasattr(res, "get_text_content") else str(res)

    await _emit("phase_completed", "assertions", f"Assertions evaluated: {passed}/{len(_assertion_results)} passed", details={
        "worker_response": analysis[:3000],
        "passed": passed,
        "total": len(_assertion_results),
    })
    return _tool_response(f"Assertions evaluated: {passed}/{len(_assertion_results)} passed.\n{assertion_summary}\nAnalysis: {analysis}")


async def run_diagnostic_analysis(test_context: str) -> Any:
    """Create a diagnostic worker agent to analyze test patterns.

    Args:
        test_context: Context about execution and assertions to analyze.

    Returns:
        ToolResponse with diagnostic findings.
    """
    global _diagnostic_results
    from agentscope.agent import ReActAgent
    from agentscope.tool import Toolkit
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg

    await _emit("orchestrator_tool_call", "orchestrator", f"Master calls → run_diagnostic_analysis", details={
        "tool_name": "run_diagnostic_analysis", "tool_input": test_context[:300],
    })
    await _emit("diagnostic_phase_started", "diagnostics", "Diagnostic worker started")

    # Run deterministic diagnostics
    from app.services.test_lab.diagnostic_engine import generate_diagnostics
    from sqlalchemy import select

    result = await _db.execute(
        select(TestRunEvent).where(TestRunEvent.run_id == _run.id).order_by(TestRunEvent.timestamp)
    )
    all_events = [{"event_type": e.event_type, "details": e.details, "duration_ms": e.duration_ms} for e in result.scalars().all()]

    _diagnostic_results = generate_diagnostics(
        events=all_events, assertions=_assertion_results, expected_tools=_scenario.expected_tools,
        duration_ms=_run.duration_ms or 0, iteration_count=(_runtime_result or {}).get("iteration_count", 0),
        max_iterations=_scenario.max_iterations, timeout_seconds=_scenario.timeout_seconds,
        final_output=_run.final_output,
    )

    for dr in _diagnostic_results:
        await _emit("diagnostic_generated", "diagnostics", dr["message"], details={"code": dr["code"], "severity": dr["severity"]})
        _db.add(TestRunDiagnostic(
            run_id=_run.id, code=dr["code"], severity=dr["severity"], message=dr["message"],
            probable_causes=dr.get("probable_causes"), recommendation=dr.get("recommendation"), evidence=dr.get("evidence"),
        ))
    await _db.flush()

    diag_summary = json.dumps([{"code": d["code"], "severity": d["severity"], "message": d["message"]} for d in _diagnostic_results])

    # Worker agent analyzes diagnostics
    worker = ReActAgent(
        name="diagnostic_worker",
        sys_prompt="You are a diagnostic analysis worker. Analyze the diagnostic findings and provide recommendations.",
        model=_make_model(), formatter=_make_formatter(),
        toolkit=Toolkit(), memory=InMemoryMemory(), max_iters=1,
    )
    res = await worker(Msg("user", f"Analyze these diagnostic findings:\n{diag_summary}", "user"))
    analysis = res.get_text_content() if hasattr(res, "get_text_content") else str(res)

    await _emit("phase_completed", "diagnostics", f"Diagnostics: {len(_diagnostic_results)} findings", details={
        "worker_response": analysis[:3000],
        "findings_count": len(_diagnostic_results),
    })
    return _tool_response(f"Diagnostics: {len(_diagnostic_results)} findings.\n{diag_summary}\nAnalysis: {analysis}")


async def compute_final_verdict(all_results: str) -> Any:
    """Create a verdict worker agent to compute the final score and verdict.

    Args:
        all_results: Summary of all assertions and diagnostics.

    Returns:
        ToolResponse with final score and verdict.
    """
    from agentscope.agent import ReActAgent
    from agentscope.tool import Toolkit
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg

    await _emit("orchestrator_tool_call", "orchestrator", f"Master calls → compute_final_verdict", details={
        "tool_name": "compute_final_verdict", "tool_input": all_results[:300],
    })
    await _emit("report_phase_started", "report", "Verdict worker started")

    # Compute score deterministically
    from app.services.test_lab.scoring import compute_score_and_verdict
    score, verdict = compute_score_and_verdict(_assertion_results, _diagnostic_results)

    _run.score = score
    _run.verdict = verdict
    _run.status = "completed" if _run.status == "running" else _run.status
    _run.ended_at = datetime.now(timezone.utc)

    # Worker agent produces final summary
    worker = ReActAgent(
        name="verdict_worker",
        sys_prompt="You are a verdict worker. Produce a clear, concise final test summary.",
        model=_make_model(), formatter=_make_formatter(),
        toolkit=Toolkit(), memory=InMemoryMemory(), max_iters=1,
    )
    verdict_data = json.dumps({"score": score, "verdict": verdict, "assertions_passed": sum(1 for a in _assertion_results if a["passed"]), "assertions_total": len(_assertion_results), "diagnostics_count": len(_diagnostic_results)})
    res = await worker(Msg("user", f"Write a final test summary for:\n{verdict_data}", "user"))
    summary_text = res.get_text_content() if hasattr(res, "get_text_content") else str(res)

    _run.summary = f"Score: {score}/100 — Verdict: {verdict} — {summary_text[:200]}"

    await _emit("phase_completed", "report", f"Score: {score}/100 — Verdict: {verdict}", details={
        "worker_response": summary_text[:3000],
        "score": score,
        "verdict": verdict,
    })
    await _emit("run_completed", "orchestrator", f"Run completed: {verdict} ({score}/100)")

    return _tool_response(f"Final verdict: {verdict} — Score: {score}/100\n{summary_text}")


# ── Master orchestrator ───────────────────────────────────────────────

MASTER_PROMPT = """You are the Agentic Test Lab Master Orchestrator.

You coordinate a test scenario by delegating to 5 specialized worker agents IN ORDER:

1. prepare_test_scenario(scenario_summary) — validate the scenario
2. execute_target_agent(test_instructions) — run the real target agent
3. run_assertion_evaluation(execution_summary) — evaluate assertions on results
4. run_diagnostic_analysis(test_context) — analyze patterns and findings
5. compute_final_verdict(all_results) — compute score and verdict

Call each tool ONCE, in order. Pass relevant context from previous results to the next tool.
After all 5 tools complete, provide a brief final summary of the test.
"""


async def run_test(db: AsyncSession, scenario: TestScenario, existing_run_id: str | None = None) -> TestRun:
    """Execute a full test using the Agent-as-Tool pattern with worker agents."""
    global _db, _run, _scenario, _agent_def, _runtime_result, _assertion_results, _diagnostic_results

    from app.services import agent_registry_service

    agent = await agent_registry_service.get_agent(db, scenario.agent_id)
    if not agent:
        raise ValueError(f"Agent {scenario.agent_id} not found")

    if existing_run_id:
        run = await db.get(TestRun, existing_run_id)
        if not run:
            raise ValueError(f"Run {existing_run_id} not found")
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await db.flush()
    else:
        run = TestRun(
            scenario_id=scenario.id, agent_id=scenario.agent_id, agent_version=agent.version,
            status="running", started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        await db.flush()

    _db, _run, _scenario, _agent_def = db, run, scenario, agent
    _runtime_result, _assertion_results, _diagnostic_results = None, [], []

    await _emit("run_created", "orchestrator", "Test run created")
    await _emit("orchestrator_started", "orchestrator", "Master orchestrator started")

    try:
        master = await _create_master()
        if master:
            from agentscope.message import Msg
            await master(Msg("user", f"Execute test scenario '{scenario.name}' for agent '{scenario.agent_id}'. Input: {scenario.input_prompt[:200]}", "user"))
        else:
            # Fallback: direct sequential
            await prepare_test_scenario(f"Scenario: {scenario.name}")
            await execute_target_agent(f"Test agent {scenario.agent_id}")
            await run_assertion_evaluation("Evaluate assertions")
            await run_diagnostic_analysis("Analyze diagnostics")
            await compute_final_verdict("Compute verdict")

    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        run.status = "failed"
        run.error_message = str(e)
        run.ended_at = datetime.now(timezone.utc)
        await _emit("run_failed", "orchestrator", f"Error: {e}")

    await db.commit()
    await db.refresh(run)
    _db = _run = _scenario = _agent_def = None
    return run


async def _create_master():
    """Create the master ReActAgent orchestrator."""
    try:
        from agentscope.agent import ReActAgent
        from agentscope.tool import Toolkit
        from agentscope.memory import InMemoryMemory
        from app.llm.provider import is_agentscope_available

        if not is_agentscope_available():
            return None

        toolkit = Toolkit()
        toolkit.register_tool_function(prepare_test_scenario)
        toolkit.register_tool_function(execute_target_agent)
        toolkit.register_tool_function(run_assertion_evaluation)
        toolkit.register_tool_function(run_diagnostic_analysis)
        toolkit.register_tool_function(compute_final_verdict)

        return ReActAgent(
            name="master_orchestrator",
            sys_prompt=MASTER_PROMPT,
            model=_make_model(),
            formatter=_make_formatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=10,
        )
    except Exception as e:
        logger.warning(f"Failed to create master: {e}")
        return None
