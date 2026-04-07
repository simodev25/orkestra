"""Multi-Agent Test Orchestrator — Full LLM-driven evaluation.

Architecture:
  OrchestratorAgent (ReActAgent)
    ├── get_scenario_context      — reads scenario + agent info
    ├── run_scenario_subagent     — generates test plan (LLM)
    ├── run_target_agent          — executes the REAL agent under test
    ├── run_judge_subagent        — evaluates quality, verdict, score (LLM)
    ├── run_robustness_subagent   — proposes follow-up tests (LLM)
    ├── run_policy_subagent       — checks governance compliance (LLM)
    ├── get_run_state             — reads current run state
    ├── save_run_result           — persists final results to DB
    ├── respond_to_user           — sends a message back to the user

All evaluation is LLM-driven. The OrchestratorAgent decides the flow.
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
    emit_event,
    update_run,
)

logger = logging.getLogger("orkestra.test_lab.orchestrator_agent")


# ─── Run context ─────────────────────────────────────────────────────────────

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
    timeout_seconds: int = 120
    max_iterations: int = 5

    # Filled during execution
    target_output: str = ""
    target_status: str = ""
    target_duration_ms: int = 0
    target_iteration_count: int = 0
    execution_events: list[dict] = field(default_factory=list)
    score: float = 0.0
    verdict: str = ""
    summary: str = ""

    # Conversation with user (for interactive follow-ups)
    user_messages: list[dict] = field(default_factory=list)


# ─── Tool functions ──────────────────────────────────────────────────────────

def _build_tools(ctx: RunContext) -> list:
    """Build tool functions bound to the run context."""

    async def get_scenario_context() -> ToolResponse:
        """Read the scenario and agent under test information."""
        return ToolResponse(content=(
            f"SCENARIO:\n"
            f"  name: {ctx.scenario_name}\n"
            f"  agent_id: {ctx.agent_id}\n"
            f"  agent_label: {ctx.agent_label}\n"
            f"  agent_version: {ctx.agent_version}\n"
            f"  input_prompt: {ctx.input_prompt}\n"
            f"  expected_tools: {json.dumps(ctx.expected_tools)}\n"
            f"  timeout: {ctx.timeout_seconds}s\n"
            f"  max_iterations: {ctx.max_iterations}"
        ))

    async def run_scenario_subagent(objective: str) -> ToolResponse:
        """Generate a structured test plan. Call BEFORE executing the target agent."""
        emit_event(ctx.run_id, "subagent_start", "preparation", "ScenarioSubAgent starting")
        model = _make_model("preparation")
        agent = ReActAgent(
            name="ScenarioSubAgent",
            model=model, formatter=OllamaChatFormatter(),
            memory=InMemoryMemory(),
            sys_prompt=(
                "Tu es un sous-agent de scenarisation de test. "
                "Tu transformes un besoin de test en scenario concret. "
                "Reponds en francais.\n"
                "Format:\nSCENARIO: <description>\nSUCCESS_CRITERIA:\n- <critere>\nTEST_INPUT: <entree>"
            ),
            max_iters=1,
        )
        res = agent(Msg("user", objective, "user"))
        text = res.content if hasattr(res, "content") else str(res)
        emit_event(ctx.run_id, "subagent_done", "preparation", "ScenarioSubAgent done")
        return ToolResponse(content=text)

    async def run_target_agent(task: str) -> ToolResponse:
        """Execute the REAL agent under test. This is NOT a simulation."""
        emit_event(ctx.run_id, "phase_start", "runtime", f"Executing target agent {ctx.agent_id}")

        from app.services.test_lab.target_agent_runner import run_target_agent as _run
        from app.services.test_lab.target_agent_runner import _build_execution_events
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        settings = get_settings()
        engine = create_async_engine(settings.DATABASE_URL)
        Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as db:
            result = await _run(
                db=db, agent_id=ctx.agent_id, agent_version=ctx.agent_version,
                input_prompt=task, timeout_seconds=ctx.timeout_seconds,
                max_iterations=ctx.max_iterations,
            )
        await engine.dispose()

        ctx.target_output = result.final_output
        ctx.target_status = result.status
        ctx.target_duration_ms = result.duration_ms
        ctx.target_iteration_count = result.iteration_count
        ctx.execution_events = _build_execution_events(result.message_history)

        emit_event(ctx.run_id, "agent_done", "runtime",
                   f"Agent finished: {result.status} ({result.duration_ms}ms)",
                   duration_ms=result.duration_ms)

        return ToolResponse(content=(
            f"EXECUTION_RESULT:\n"
            f"  status: {result.status}\n"
            f"  duration_ms: {result.duration_ms}\n"
            f"  iterations: {result.iteration_count}\n"
            f"  tool_calls: {len(result.tool_calls)}\n"
            f"  output:\n{result.final_output[:2000]}\n"
            f"  error: {result.error or 'none'}"
        ))

    async def run_judge_subagent(analysis_request: str) -> ToolResponse:
        """Evaluate the target agent output. Produce a verdict (PASS/FAIL/PARTIAL), a score (0-100), and a rationale. Call AFTER run_target_agent."""
        emit_event(ctx.run_id, "subagent_start", "judgment", "JudgeSubAgent starting")
        model = _make_model("verdict")
        agent = ReActAgent(
            name="JudgeSubAgent",
            model=model, formatter=OllamaChatFormatter(),
            memory=InMemoryMemory(),
            sys_prompt=(
                "Tu es un sous-agent juge pour un systeme de test d'agents IA.\n"
                "Tu evalues la sortie d'un agent sous test.\n"
                "Tu dois donner:\n"
                "- VERDICT: PASS, FAIL ou PARTIAL\n"
                "- SCORE: un nombre entre 0 et 100\n"
                "- RATIONALE: une explication courte et technique\n"
                "- ISSUES: liste des problemes detectes (si applicable)\n"
                "- RECOMMENDATIONS: suggestions d'amelioration\n\n"
                "Sois strict mais juste. Reponds en francais."
            ),
            max_iters=1,
        )
        res = agent(Msg("user", analysis_request, "user"))
        text = res.content if hasattr(res, "content") else str(res)

        # Try to extract score and verdict from response
        import re
        score_match = re.search(r"SCORE[:\s]*(\d+)", text)
        verdict_match = re.search(r"VERDICT[:\s]*(PASS|FAIL|PARTIAL)", text, re.IGNORECASE)
        if score_match:
            ctx.score = float(score_match.group(1))
        if verdict_match:
            ctx.verdict = verdict_match.group(1).lower()
            if ctx.verdict == "pass":
                ctx.verdict = "passed"
            elif ctx.verdict == "partial":
                ctx.verdict = "passed_with_warnings"
            elif ctx.verdict == "fail":
                ctx.verdict = "failed"
        ctx.summary = text

        emit_event(ctx.run_id, "subagent_done", "judgment",
                   f"JudgeSubAgent: {ctx.verdict} ({ctx.score}/100)")
        return ToolResponse(content=text)

    async def run_robustness_subagent(request: str) -> ToolResponse:
        """Propose a follow-up edge case or robustness test."""
        model = _make_model("diagnostic")
        agent = ReActAgent(
            name="RobustnessSubAgent",
            model=model, formatter=OllamaChatFormatter(),
            memory=InMemoryMemory(),
            sys_prompt=(
                "Tu es un sous-agent de robustesse. "
                "Tu proposes des tests complementaires plus durs ou des edge cases. "
                "Reponds en francais.\nFormat: FOLLOWUP_TEST / WHY_IT_MATTERS"
            ),
            max_iters=1,
        )
        res = agent(Msg("user", request, "user"))
        return ToolResponse(content=res.content if hasattr(res, "content") else str(res))

    async def run_policy_subagent(request: str) -> ToolResponse:
        """Check if the agent output respects governance constraints (forbidden effects, scope, etc.)."""
        model = _make_model("assertion")
        agent = ReActAgent(
            name="PolicySubAgent",
            model=model, formatter=OllamaChatFormatter(),
            memory=InMemoryMemory(),
            sys_prompt=(
                "Tu es un sous-agent de conformite policy.\n"
                "Tu verifies si la sortie d'un agent respecte ses contraintes de gouvernance:\n"
                "- effets interdits (forbidden_effects)\n"
                "- perimetre de competence\n"
                "- regles de la famille\n"
                "Reponds en francais.\nFormat: COMPLIANCE: OK/VIOLATION / DETAILS"
            ),
            max_iters=1,
        )
        res = agent(Msg("user", request, "user"))
        return ToolResponse(content=res.content if hasattr(res, "content") else str(res))

    async def get_run_state() -> ToolResponse:
        """Get the current state of the test run."""
        return ToolResponse(content=(
            f"RUN_STATE:\n"
            f"  run_id: {ctx.run_id}\n"
            f"  agent: {ctx.agent_id} ({ctx.agent_label})\n"
            f"  target_status: {ctx.target_status or 'not_executed'}\n"
            f"  target_duration_ms: {ctx.target_duration_ms}\n"
            f"  verdict: {ctx.verdict or 'pending'}\n"
            f"  score: {ctx.score}\n"
            f"  output_length: {len(ctx.target_output)}\n"
            f"  events: {len(ctx.execution_events)}"
        ))

    async def save_run_result(summary: str) -> ToolResponse:
        """Persist test results to DB. Call this as the LAST step."""
        update_run(
            ctx.run_id,
            status="completed",
            verdict=ctx.verdict or "unknown",
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
            f"RUN_SAVED: run_id={ctx.run_id}, verdict={ctx.verdict}, score={ctx.score}/100"
        ))

    return [
        get_scenario_context,
        run_scenario_subagent,
        run_target_agent,
        run_judge_subagent,
        run_robustness_subagent,
        run_policy_subagent,
        get_run_state,
        save_run_result,
    ]


# ─── Model factory ───────────────────────────────────────────────────────────

def _make_model(worker_name: str | None = None) -> OllamaChatModel:
    config = _get_config_sync()
    model_name = None
    if worker_name and worker_name in config.get("workers", {}):
        model_name = config["workers"][worker_name].get("model")
    if not model_name:
        model_name = config.get("orchestrator", {}).get("model", "mistral")
    settings = get_settings()
    host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
    return OllamaChatModel(model_name=model_name, host=host, stream=False)


# ─── OrchestratorAgent ───────────────────────────────────────────────────────

ORCHESTRATOR_PROMPT = """Tu es OrchestratorAgent, l'orchestrateur de test d'agents d'Orkestra.

Mission :
- Tu testes un agent sous test en coordonnant des sous-agents specialises.
- TOUT est evalue par LLM, pas de moteur deterministe.

Tools disponibles :
- get_scenario_context : lis le contexte du scenario
- run_scenario_subagent : fais preparer un plan de test
- run_target_agent : execute le VRAI agent sous test (PAS une simulation)
- run_judge_subagent : fais evaluer la sortie (verdict + score + rationale)
- run_robustness_subagent : fais proposer des tests complementaires
- run_policy_subagent : fais verifier la conformite policy
- get_run_state : lis l'etat courant du run
- save_run_result : sauvegarde les resultats (TOUJOURS appeler en dernier)

Workflow :
1. get_scenario_context
2. run_scenario_subagent — prepare le plan de test
3. run_target_agent — execute le vrai agent avec l'input du scenario
4. run_judge_subagent — evalue la sortie de l'agent
5. (optionnel) run_policy_subagent — verifie la conformite
6. save_run_result — sauvegarde

Regles :
1. Reponds en francais.
2. TOUJOURS executer run_target_agent — c'est le vrai agent.
3. TOUJOURS executer run_judge_subagent — c'est l'evaluation.
4. TOUJOURS finir par save_run_result.
5. Apres save, donne un resume structure.

Format du resume final :
RESUME: <resume court>
STATUT: <PASS | FAIL | PARTIAL>
AGENT_SOUS_TEST: <agent_id>
SCORE: <score>/100
DETAILS: <points importants>
OPTIONS_SUIVANTES:
- test plus strict
- edge case
- test policy
- rejouer
"""


def build_orchestrator_agent(ctx: RunContext) -> ReActAgent:
    tools = _build_tools(ctx)
    toolkit = Toolkit()
    for fn in tools:
        toolkit.register_tool_function(fn)
    model = _make_model()
    return ReActAgent(
        name="OrchestratorAgent",
        model=model, formatter=OllamaChatFormatter(),
        memory=InMemoryMemory(), toolkit=toolkit,
        sys_prompt=ORCHESTRATOR_PROMPT, max_iters=12,
    )


# ─── Orchestrator with persistent memory (for chat follow-ups) ───────────────

_active_orchestrators: dict[str, tuple[ReActAgent, RunContext]] = {}


def get_or_create_orchestrator(run_id: str, scenario_id: str | None = None) -> tuple[ReActAgent, RunContext]:
    """Get existing orchestrator for follow-up, or create new one."""
    if run_id in _active_orchestrators:
        return _active_orchestrators[run_id]
    # Will be populated by run_orchestrated_test
    return None, None


async def chat_with_orchestrator(run_id: str, message: str) -> str:
    """Send a follow-up message to the orchestrator for a completed run."""
    if run_id not in _active_orchestrators:
        return "No active orchestrator for this run. Start a new run first."

    orchestrator, ctx = _active_orchestrators[run_id]
    try:
        user_msg = Msg("user", message, "user")
        response = await asyncio.wait_for(
            orchestrator(user_msg),
            timeout=120,
        )
        text = response.content if hasattr(response, "content") else str(response)
        emit_event(run_id, "orchestrator_chat", "interactive", f"User: {message[:100]}",
                   details={"response_length": len(text)})
        return text
    except Exception as exc:
        return f"Orchestrator error: {exc}"


# ─── Main entry point ────────────────────────────────────────────────────────

async def run_orchestrated_test(run_id: str, scenario_id: str) -> None:
    """Execute a test run using the multi-agent OrchestratorAgent."""
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
        emit_event(run_id, "run_started", "orchestration", "OrchestratorAgent starting")

        async with Session() as db:
            scenario = (await db.execute(
                select(TestScenario).where(TestScenario.id == scenario_id)
            )).scalar_one_or_none()
            if not scenario:
                raise ValueError(f"Scenario {scenario_id} not found")
            agent_def = await agent_registry_service.get_agent(db, scenario.agent_id)
            if not agent_def:
                raise ValueError(f"Agent {scenario.agent_id} not found")

        ctx = RunContext(
            run_id=run_id, scenario_id=scenario_id,
            agent_id=scenario.agent_id,
            agent_label=getattr(agent_def, "name", scenario.agent_id),
            agent_version=getattr(agent_def, "version", ""),
            scenario_name=scenario.name,
            input_prompt=scenario.input_prompt,
            expected_tools=scenario.expected_tools or [],
            timeout_seconds=scenario.timeout_seconds or 120,
            max_iterations=scenario.max_iterations or 5,
        )

        orchestrator = build_orchestrator_agent(ctx)

        # Store for follow-up chat
        _active_orchestrators[run_id] = (orchestrator, ctx)

        user_msg = Msg(
            "user",
            f"Lance le test du scenario '{ctx.scenario_name}' pour l'agent '{ctx.agent_id}'. "
            f"Input: {ctx.input_prompt}",
            "user",
        )

        response = await asyncio.wait_for(
            orchestrator(user_msg),
            timeout=ctx.timeout_seconds + 180,
        )

        final_text = response.content if hasattr(response, "content") else str(response)

        # Fallback if orchestrator didn't save
        if not ctx.verdict:
            update_run(run_id, status="completed", verdict="unknown", score=0,
                       duration_ms=ctx.target_duration_ms, final_output=ctx.target_output,
                       summary=final_text,
                       ended_at=datetime.now(timezone.utc))

    except Exception as exc:
        logger.exception(f"OrchestratorAgent failed for run {run_id}")
        update_run(run_id, status="failed", error_message=str(exc),
                   ended_at=datetime.now(timezone.utc))
        emit_event(run_id, "run_failed", "error", f"Run failed: {exc}")
        raise
    finally:
        await engine.dispose()
