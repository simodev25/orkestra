"""Multi-Agent Test Orchestrator — OrchestratorAgent with SubAgent tools.

This module creates a ReActAgent-based orchestrator that coordinates test
execution using tools, following the same pattern as scripts/orchestrateur_chat.py
but connected to the real Orkestra platform (DB, agent registry, execution engine).

Architecture:
  OrchestratorAgent (ReActAgent)
    ├── get_scenario_context      — reads scenario + agent info
    ├── run_scenario_subagent     — generates/adapts test plan
    ├── run_target_agent          — executes the REAL agent under test
    ├── run_assertion_engine      — deterministic assertion evaluation
    ├── run_diagnostic_engine     — deterministic diagnostic analysis
    ├── run_scoring_engine        — deterministic scoring + verdict
    ├── run_judge_subagent        — explains verdict in natural language
    ├── run_robustness_subagent   — proposes follow-up edge cases
    ├── save_run_result           — persists final results to DB

The deterministic engines (assertions, diagnostics, scoring) remain authoritative.
SubAgents are assistive — they generate scenarios, explain verdicts, propose follow-ups.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agentscope.agent import ReActAgent
from agentscope.formatter import OllamaChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import OllamaChatModel
from agentscope.tool import Toolkit, ToolResponse

from app.core.config import get_settings
from app.services.test_lab.execution_engine import (
    _get_config_sync,
    _get_sync_engine,
    emit_event,
    update_run,
)

logger = logging.getLogger("orkestra.test_lab.orchestrator_agent")


# ─── Run context (shared mutable state for one test run) ─────────────────────

@dataclass
class RunContext:
    """Mutable context shared across all tools during a single test run."""
    run_id: str
    scenario_id: str
    agent_id: str
    agent_label: str = ""
    agent_version: str = ""
    scenario_name: str = ""
    input_prompt: str = ""
    expected_tools: list[str] = field(default_factory=list)
    assertions_defs: list[dict] = field(default_factory=list)
    timeout_seconds: int = 120
    max_iterations: int = 5

    # Filled during execution
    target_output: str = ""
    target_status: str = ""
    target_duration_ms: int = 0
    target_iteration_count: int = 0
    execution_events: list[dict] = field(default_factory=list)
    assertion_results: list[dict] = field(default_factory=list)
    diagnostics: list[dict] = field(default_factory=list)
    score: float = 0.0
    verdict: str = ""
    summary: str = ""


# ─── Tool functions (connected to real platform) ─────────────────────────────

def _build_tools(ctx: RunContext) -> list:
    """Build the list of tool functions bound to the run context."""

    async def get_scenario_context() -> ToolResponse:
        """Read the current scenario and agent information."""
        return ToolResponse(content=(
            f"SCENARIO:\n"
            f"  name: {ctx.scenario_name}\n"
            f"  agent_id: {ctx.agent_id}\n"
            f"  agent_label: {ctx.agent_label}\n"
            f"  agent_version: {ctx.agent_version}\n"
            f"  input_prompt: {ctx.input_prompt}\n"
            f"  expected_tools: {json.dumps(ctx.expected_tools)}\n"
            f"  assertions: {len(ctx.assertions_defs)}\n"
            f"  timeout: {ctx.timeout_seconds}s\n"
            f"  max_iterations: {ctx.max_iterations}\n"
        ))

    async def run_scenario_subagent(objective: str) -> ToolResponse:
        """Generate a structured test plan from the scenario. Call this before executing the target agent."""
        emit_event(ctx.run_id, "subagent_start", "preparation", "ScenarioSubAgent starting")
        model = _make_model("preparation")
        agent = ReActAgent(
            name="ScenarioSubAgent",
            model=model,
            formatter=OllamaChatFormatter(),
            memory=InMemoryMemory(),
            sys_prompt=(
                "Tu es un sous-agent de scénarisation de test. "
                "Tu transformes un besoin de test en scénario concret et structuré. "
                "Réponds en français. Format: SCENARIO / SUCCESS_CRITERIA / TEST_INPUT."
            ),
            max_iters=1,
        )
        res = agent(Msg("user", objective, "user"))
        text = res.content if hasattr(res, "content") else str(res)
        emit_event(ctx.run_id, "subagent_done", "preparation", "ScenarioSubAgent done",
                   details={"response_length": len(text)})
        return ToolResponse(content=text)

    async def run_target_agent(task: str) -> ToolResponse:
        """Execute the REAL agent under test with the given task. This calls the actual agent, not a simulation."""
        emit_event(ctx.run_id, "phase_start", "runtime", f"Executing target agent {ctx.agent_id}")

        from app.services.test_lab.target_agent_runner import run_target_agent as _run_target
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        settings = get_settings()
        engine = create_async_engine(settings.DATABASE_URL)
        Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as db:
            result = await _run_target(
                db=db,
                agent_id=ctx.agent_id,
                agent_version=ctx.agent_version,
                input_prompt=task,
                timeout_seconds=ctx.timeout_seconds,
                max_iterations=ctx.max_iterations,
            )
        await engine.dispose()

        ctx.target_output = result.final_output
        ctx.target_status = result.status
        ctx.target_duration_ms = result.duration_ms
        ctx.target_iteration_count = result.iteration_count

        from app.services.test_lab.target_agent_runner import _build_execution_events
        ctx.execution_events = _build_execution_events(result.message_history)

        emit_event(ctx.run_id, "agent_execution_done", "runtime",
                   f"Agent finished: {result.status} ({result.duration_ms}ms)",
                   duration_ms=result.duration_ms)

        return ToolResponse(content=(
            f"EXECUTION_RESULT:\n"
            f"  status: {result.status}\n"
            f"  duration_ms: {result.duration_ms}\n"
            f"  iterations: {result.iteration_count}\n"
            f"  tool_calls: {len(result.tool_calls)}\n"
            f"  output_preview: {result.final_output[:500]}\n"
            f"  error: {result.error or 'none'}"
        ))

    async def run_assertion_engine() -> ToolResponse:
        """Run DETERMINISTIC assertion evaluation on the target agent output. Call this after run_target_agent."""
        emit_event(ctx.run_id, "phase_start", "assertions", "Running deterministic assertions")
        from app.services.test_lab.assertion_engine import evaluate_assertions

        ctx.assertion_results = evaluate_assertions(
            assertion_defs=ctx.assertions_defs,
            events=ctx.execution_events,
            final_output=ctx.target_output,
            duration_ms=ctx.target_duration_ms,
            iteration_count=ctx.target_iteration_count,
            final_status=ctx.target_status,
        )

        passed = sum(1 for a in ctx.assertion_results if a["passed"])
        total = len(ctx.assertion_results)
        emit_event(ctx.run_id, "assertions_done", "assertions", f"Assertions: {passed}/{total} passed")

        lines = [f"ASSERTIONS: {passed}/{total} passed"]
        for a in ctx.assertion_results:
            status = "PASS" if a["passed"] else "FAIL"
            lines.append(f"  [{status}] {a['assertion_type']}: {a.get('message', '')}")
        return ToolResponse(content="\n".join(lines))

    async def run_diagnostic_engine() -> ToolResponse:
        """Run DETERMINISTIC diagnostic analysis. Call this after assertions."""
        emit_event(ctx.run_id, "phase_start", "diagnostics", "Running deterministic diagnostics")
        from app.services.test_lab.diagnostic_engine import generate_diagnostics

        ctx.diagnostics = generate_diagnostics(
            events=ctx.execution_events,
            assertions=ctx.assertion_results,
            expected_tools=ctx.expected_tools,
            duration_ms=ctx.target_duration_ms,
            iteration_count=ctx.target_iteration_count,
            max_iterations=ctx.max_iterations,
            timeout_seconds=ctx.timeout_seconds,
            final_output=ctx.target_output,
        )

        emit_event(ctx.run_id, "diagnostics_done", "diagnostics", f"{len(ctx.diagnostics)} findings")

        lines = [f"DIAGNOSTICS: {len(ctx.diagnostics)} findings"]
        for d in ctx.diagnostics:
            lines.append(f"  [{d['severity'].upper()}] {d['code']}: {d['message']}")
        return ToolResponse(content="\n".join(lines))

    async def run_scoring_engine() -> ToolResponse:
        """Compute DETERMINISTIC score and verdict. Call this after assertions + diagnostics."""
        from app.services.test_lab.scoring import compute_score_and_verdict

        ctx.score, ctx.verdict = compute_score_and_verdict(ctx.assertion_results, ctx.diagnostics)
        emit_event(ctx.run_id, "phase_start", "verdict", f"Score: {ctx.score}/100, Verdict: {ctx.verdict}")

        return ToolResponse(content=(
            f"SCORING:\n"
            f"  score: {ctx.score}/100\n"
            f"  verdict: {ctx.verdict}\n"
            f"  assertions_passed: {sum(1 for a in ctx.assertion_results if a['passed'])}/{len(ctx.assertion_results)}\n"
            f"  diagnostics: {len(ctx.diagnostics)}"
        ))

    async def run_judge_subagent(analysis_request: str) -> ToolResponse:
        """Generate a human-readable verdict explanation. Call after scoring."""
        emit_event(ctx.run_id, "subagent_start", "verdict", "JudgeSubAgent starting")
        model = _make_model("verdict")
        agent = ReActAgent(
            name="JudgeSubAgent",
            model=model,
            formatter=OllamaChatFormatter(),
            memory=InMemoryMemory(),
            sys_prompt=(
                "Tu es un sous-agent juge. Tu évalues les résultats d'un test d'agent. "
                "Réponds en français. Format: VERDICT / SCORE / RATIONALE."
            ),
            max_iters=1,
        )
        res = agent(Msg("user", analysis_request, "user"))
        text = res.content if hasattr(res, "content") else str(res)
        ctx.summary = text
        emit_event(ctx.run_id, "subagent_done", "verdict", "JudgeSubAgent done")
        return ToolResponse(content=text)

    async def run_robustness_subagent(request: str) -> ToolResponse:
        """Propose a follow-up edge case or robustness test. Optional — call after verdict."""
        model = _make_model("diagnostic")
        agent = ReActAgent(
            name="RobustnessSubAgent",
            model=model,
            formatter=OllamaChatFormatter(),
            memory=InMemoryMemory(),
            sys_prompt=(
                "Tu es un sous-agent de robustesse. "
                "Tu proposes des tests complémentaires plus durs ou des edge cases. "
                "Réponds en français. Format: FOLLOWUP_TEST / WHY_IT_MATTERS."
            ),
            max_iters=1,
        )
        res = agent(Msg("user", request, "user"))
        return ToolResponse(content=res.content if hasattr(res, "content") else str(res))

    async def save_run_result(summary: str) -> ToolResponse:
        """Persist the test run results to the database. Call this as the LAST step."""
        from app.models.test_lab import TestRunAssertion, TestRunDiagnostic
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        # Persist assertions and diagnostics
        settings = get_settings()
        engine = create_async_engine(settings.DATABASE_URL)
        Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as db:
            for ar in ctx.assertion_results:
                db.add(TestRunAssertion(
                    run_id=ctx.run_id,
                    assertion_type=ar["assertion_type"],
                    target=ar.get("target"),
                    expected=str(ar.get("expected")),
                    actual=str(ar.get("actual")),
                    passed=ar["passed"],
                    critical=ar.get("critical", False),
                    message=ar.get("message", ""),
                ))
            for diag in ctx.diagnostics:
                db.add(TestRunDiagnostic(
                    run_id=ctx.run_id,
                    code=diag["code"],
                    severity=diag["severity"],
                    message=diag["message"],
                    probable_causes=diag.get("probable_causes"),
                    recommendation=diag.get("recommendation"),
                    evidence=diag.get("evidence"),
                ))
            await db.commit()
        await engine.dispose()

        # Update run record
        update_run(
            ctx.run_id,
            status="completed",
            verdict=ctx.verdict,
            score=ctx.score,
            duration_ms=ctx.target_duration_ms,
            final_output=ctx.target_output,
            summary=summary or ctx.summary,
            ended_at=datetime.now(timezone.utc),
            agent_version=ctx.agent_version,
        )

        emit_event(ctx.run_id, "run_completed", "verdict",
                   f"Test completed: {ctx.verdict} ({ctx.score}/100)")

        return ToolResponse(content=(
            f"RUN_SAVED:\n"
            f"  run_id: {ctx.run_id}\n"
            f"  verdict: {ctx.verdict}\n"
            f"  score: {ctx.score}/100\n"
            f"  status: completed"
        ))

    return [
        get_scenario_context,
        run_scenario_subagent,
        run_target_agent,
        run_assertion_engine,
        run_diagnostic_engine,
        run_scoring_engine,
        run_judge_subagent,
        run_robustness_subagent,
        save_run_result,
    ]


# ─── Model factory ───────────────────────────────────────────────────────────

def _make_model(worker_name: str | None = None) -> OllamaChatModel:
    """Create an OllamaChatModel, reading config from DB."""
    config = _get_config_sync()
    model_name = None
    if worker_name and worker_name in config.get("workers", {}):
        model_name = config["workers"][worker_name].get("model")
    if not model_name:
        model_name = config.get("orchestrator", {}).get("model", "mistral")

    settings = get_settings()
    host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
    return OllamaChatModel(model_name=model_name, host=host, stream=False)


# ─── Build the OrchestratorAgent ─────────────────────────────────────────────

ORCHESTRATOR_SYSTEM_PROMPT = """Tu es OrchestratorAgent, l'orchestrateur de test d'agents d'Orkestra.

Mission :
- Tu testes un agent sous test en coordonnant des sous-agents spécialisés.
- Tu suis un workflow structuré mais tu peux adapter l'ordre si nécessaire.

Workflow standard :
1. get_scenario_context — lis le contexte du scénario et de l'agent
2. run_scenario_subagent — fais préparer un plan de test
3. run_target_agent — exécute le VRAI agent sous test avec l'input du scénario
4. run_assertion_engine — évalue les assertions de manière DÉTERMINISTE
5. run_diagnostic_engine — analyse les diagnostics de manière DÉTERMINISTE
6. run_scoring_engine — calcule le score et le verdict de manière DÉTERMINISTE
7. run_judge_subagent — fais expliquer le verdict en langage naturel
8. save_run_result — sauvegarde les résultats dans la base

Règles :
1. Tu réponds en français.
2. Tu dois TOUJOURS exécuter run_target_agent — c'est le vrai agent, pas une simulation.
3. Tu dois TOUJOURS exécuter run_assertion_engine, run_diagnostic_engine, run_scoring_engine — ce sont les évaluations déterministes officielles.
4. Tu dois TOUJOURS finir par save_run_result.
5. Tu restes direct et technique.
6. Après save_run_result, tu donnes un résumé structuré avec le verdict et les options suivantes.

Format du résumé final :
RÉSUMÉ: <résumé court>
STATUT: <PASS | FAIL | PARTIAL>
AGENT_SOUS_TEST: <agent_id>
SCORE: <score>/100
DÉTAILS: <points importants>
OPTIONS_SUIVANTES:
- test plus strict
- edge case / robustesse
- test policy
- rejouer
"""


def build_orchestrator_agent(ctx: RunContext) -> ReActAgent:
    """Build the OrchestratorAgent with all tools bound to the run context."""
    tools = _build_tools(ctx)
    toolkit = Toolkit()
    for tool_fn in tools:
        toolkit.register_tool_function(tool_fn)

    model = _make_model()
    return ReActAgent(
        name="OrchestratorAgent",
        model=model,
        formatter=OllamaChatFormatter(),
        memory=InMemoryMemory(),
        toolkit=toolkit,
        sys_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        max_iters=12,
    )


# ─── Main entry point ────────────────────────────────────────────────────────

async def run_orchestrated_test(run_id: str, scenario_id: str) -> None:
    """Execute a test run using the multi-agent OrchestratorAgent.

    This is the replacement for the sequential pipeline.
    The OrchestratorAgent decides the flow, but deterministic engines
    (assertions, diagnostics, scoring) remain authoritative.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from app.models.test_lab import TestScenario
    from app.services import agent_registry_service

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        update_run(run_id, status="running", started_at=datetime.now(timezone.utc))
        emit_event(run_id, "run_started", "orchestration", "OrchestratorAgent starting multi-agent test")

        # Load scenario and agent
        async with Session() as db:
            scenario = (await db.execute(
                select(TestScenario).where(TestScenario.id == scenario_id)
            )).scalar_one_or_none()
            if not scenario:
                raise ValueError(f"Scenario {scenario_id} not found")

            agent_def = await agent_registry_service.get_agent(db, scenario.agent_id)
            if not agent_def:
                raise ValueError(f"Agent {scenario.agent_id} not found")

        # Build run context
        ctx = RunContext(
            run_id=run_id,
            scenario_id=scenario_id,
            agent_id=scenario.agent_id,
            agent_label=getattr(agent_def, "name", scenario.agent_id),
            agent_version=getattr(agent_def, "version", ""),
            scenario_name=scenario.name,
            input_prompt=scenario.input_prompt,
            expected_tools=scenario.expected_tools or [],
            assertions_defs=scenario.assertions or [],
            timeout_seconds=scenario.timeout_seconds or 120,
            max_iterations=scenario.max_iterations or 5,
        )

        # Build and run the OrchestratorAgent
        orchestrator = build_orchestrator_agent(ctx)

        user_msg = Msg(
            "user",
            f"Lance le test du scénario '{ctx.scenario_name}' pour l'agent '{ctx.agent_id}'. "
            f"Input: {ctx.input_prompt}",
            "user",
        )

        emit_event(run_id, "orchestrator_start", "orchestration", "OrchestratorAgent processing")

        # Run in thread (AgentScope agents are sync)
        response = await asyncio.wait_for(
            asyncio.to_thread(orchestrator, user_msg),
            timeout=ctx.timeout_seconds + 120,  # extra time for subagents
        )

        final_text = response.content if hasattr(response, "content") else str(response)

        # If the orchestrator didn't save (e.g., it failed mid-way), ensure we save
        if ctx.verdict == "":
            # Orchestrator didn't reach save_run_result — run deterministic engines manually
            logger.warning("OrchestratorAgent did not complete full workflow, running fallback")
            from app.services.test_lab.assertion_engine import evaluate_assertions
            from app.services.test_lab.diagnostic_engine import generate_diagnostics
            from app.services.test_lab.scoring import compute_score_and_verdict

            if not ctx.assertion_results:
                ctx.assertion_results = evaluate_assertions(
                    ctx.assertions_defs, ctx.execution_events, ctx.target_output,
                    ctx.target_duration_ms, ctx.target_iteration_count, ctx.target_status,
                )
            if not ctx.diagnostics:
                ctx.diagnostics = generate_diagnostics(
                    ctx.execution_events, ctx.assertion_results, ctx.expected_tools,
                    ctx.target_duration_ms, ctx.target_iteration_count,
                    ctx.max_iterations, ctx.timeout_seconds, ctx.target_output,
                )
            ctx.score, ctx.verdict = compute_score_and_verdict(ctx.assertion_results, ctx.diagnostics)

            update_run(
                run_id, status="completed", verdict=ctx.verdict, score=ctx.score,
                duration_ms=ctx.target_duration_ms, final_output=ctx.target_output,
                summary=final_text, ended_at=datetime.now(timezone.utc),
            )
            emit_event(run_id, "run_completed", "verdict",
                       f"Fallback completed: {ctx.verdict} ({ctx.score}/100)")

    except Exception as exc:
        logger.exception(f"OrchestratorAgent failed for run {run_id}")
        update_run(run_id, status="failed", error_message=str(exc),
                   ended_at=datetime.now(timezone.utc))
        emit_event(run_id, "run_failed", "error", f"Run failed: {exc}")
        raise

    finally:
        await engine.dispose()
