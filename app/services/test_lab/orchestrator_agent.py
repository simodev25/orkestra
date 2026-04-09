"""Multi-Agent Test Orchestrator — Full LLM-driven, same pattern as orchestrateur_chat.py.

Architecture:
  OrchestratorAgent (ReActAgent, persistent)
    Tools call persistent SubAgents (created ONCE, reused):
    ├── scenario_subagent   (ScenarioSubAgent)   — generates test plan
    ├── judge_subagent      (JudgeSubAgent)      — evaluates + verdict + score
    ├── robustness_subagent (RobustnessSubAgent) — proposes follow-ups
    ├── policy_subagent     (PolicySubAgent)     — checks governance
    Plus platform tools:
    ├── run_target_agent    — executes the REAL agent under test
    ├── get_scenario_context / get_run_state — reads state
    ├── save_run_result     — persists to DB
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
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
from app.services.test_lab.trace_recorder import TraceRecorder

logger = logging.getLogger("orkestra.test_lab.orchestrator_agent")


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", str(item)) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def _run_async(coro):
    """Run async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


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


def _build_subagent(name: str, sys_prompt: str, worker_key: str) -> ReActAgent:
    """Build a persistent SubAgent (created ONCE, reused across tool calls)."""
    return ReActAgent(
        name=name,
        model=_make_model(worker_key),
        formatter=OllamaChatFormatter(),
        memory=InMemoryMemory(),
        sys_prompt=sys_prompt,
        max_iters=1,
    )


# ─── Run context ─────────────────────────────────────────────────────────────

@dataclass
class RunContext:
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
    target_output: str = ""
    target_status: str = ""
    target_duration_ms: int = 0
    target_iteration_count: int = 0
    execution_events: list[dict] = field(default_factory=list)
    score: float = 0.0
    verdict: str = ""
    summary: str = ""


# ─── Build tools + persistent subagents (same pattern as orchestrateur_chat.py)

def _build_tools_and_subagents(ctx: RunContext) -> list:
    """Build tools with PERSISTENT subagents — created once, reused."""

    # ── Persistent SubAgents (like orchestrateur_chat.py) ────────────────
    scenario_subagent = _build_subagent(
        "ScenarioSubAgent",
        "Tu es un sous-agent de scenarisation de test.\n"
        "Tu aides l'orchestrateur a transformer un besoin de test en scenario concret.\n"
        "Reponds en francais.\n\n"
        "Format obligatoire :\n"
        "SCENARIO:\n<description courte et exploitable>\n\n"
        "SUCCESS_CRITERIA:\n- <critere 1>\n- <critere 2>\n- <critere 3>\n\n"
        "TEST_INPUT:\n<entree de test realiste>",
        "preparation",
    )

    judge_subagent = _build_subagent(
        "JudgeSubAgent",
        "Tu es un sous-agent juge.\n"
        "Tu evalues la sortie d'un agent sous test par rapport a un scenario et des criteres.\n"
        "Reponds en francais.\n\n"
        "Format obligatoire :\n"
        "VERDICT: PASS ou FAIL ou PARTIAL\n"
        "SCORE: <nombre entre 0 et 100>\n"
        "RATIONALE:\n<explication courte>",
        "verdict",
    )

    robustness_subagent = _build_subagent(
        "RobustnessSubAgent",
        "Tu es un sous-agent de robustesse.\n"
        "Tu proposes un test complementaire plus dur ou un edge case.\n"
        "Reponds en francais.\n\n"
        "Format obligatoire :\n"
        "FOLLOWUP_TEST:\n<test complementaire>\n\n"
        "WHY_IT_MATTERS:\n<pourquoi ce test est utile>",
        "diagnostic",
    )

    policy_subagent = _build_subagent(
        "PolicySubAgent",
        "Tu es un sous-agent de conformite policy.\n"
        "Tu verifies si la sortie d'un agent respecte ses contraintes de gouvernance.\n"
        "Reponds en francais.\n\n"
        "Format obligatoire :\n"
        "COMPLIANCE: OK ou VIOLATION\n"
        "DETAILS:\n<explication>",
        "assertion",
    )

    # ── Tool functions (SYNC, call persistent subagents) ─────────────────

    def get_scenario_context() -> ToolResponse:
        """Read the scenario and agent under test information."""
        return ToolResponse(content=(
            f"SCENARIO:\n"
            f"  name: {ctx.scenario_name}\n"
            f"  agent_id: {ctx.agent_id}\n"
            f"  agent_label: {ctx.agent_label}\n"
            f"  input_prompt: {ctx.input_prompt}\n"
            f"  expected_tools: {json.dumps(ctx.expected_tools)}\n"
            f"  timeout: {ctx.timeout_seconds}s\n"
            f"  max_iterations: {ctx.max_iterations}"
        ))

    def run_scenario_subagent(task: str) -> ToolResponse:
        """Ask the ScenarioSubAgent to prepare a test plan. Call BEFORE run_target_agent."""
        emit_event(ctx.run_id, "subagent_start", "preparation",
                   "ScenarioSubAgent starting",
                   details={"subagent": "ScenarioSubAgent", "prompt": task[:3000]})
        recorder = TraceRecorder.get(ctx.run_id)
        if recorder:
            recorder.record_orchestrator_tool_call("run_scenario_subagent", {"task": task})
        t0 = time.time()
        res = _run_async(scenario_subagent(Msg("user", task, "user")))
        text = _extract_text(res.content if hasattr(res, "content") else str(res))
        duration_ms = int((time.time() - t0) * 1000)
        if recorder:
            model = _get_config_sync().get("workers", {}).get("preparation", {}).get("model") \
                or _get_config_sync().get("orchestrator", {}).get("model", "mistral")
            recorder.record_subagent_call(
                subagent_name="ScenarioSubAgent", role="preparation",
                model=model, prompt=task, response=text, duration_ms=duration_ms,
            )
            recorder.record_orchestrator_tool_result("run_scenario_subagent", text, duration_ms)
        emit_event(ctx.run_id, "subagent_done", "preparation",
                   f"ScenarioSubAgent done ({duration_ms}ms)",
                   details={"subagent": "ScenarioSubAgent", "response": text[:3000],
                            "response_length": len(text)},
                   duration_ms=duration_ms)
        return ToolResponse(content=text)

    def run_target_agent(task: str) -> ToolResponse:
        """Execute the REAL agent under test. This is NOT a simulation."""
        emit_event(ctx.run_id, "phase_start", "runtime", f"Executing target agent {ctx.agent_id}")
        recorder = TraceRecorder.get(ctx.run_id)
        if recorder:
            recorder.record_orchestrator_tool_call("run_target_agent", {"task": task})

        async def _execute():
            from app.services.test_lab.target_agent_runner import run_target_agent as _run
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
            return result

        # Record start
        if recorder:
            recorder.record_target_agent_start(
                agent_id=ctx.agent_id, input_prompt=task,
                model=ctx.agent_version or "default",
                tools=[], mcps=[], skills=[],
            )

        result = _run_async(_execute())
        ctx.target_output = result.final_output
        ctx.target_status = result.status
        ctx.target_duration_ms = result.duration_ms
        ctx.target_iteration_count = result.iteration_count
        from app.services.test_lab.target_agent_runner import _build_execution_events
        ctx.execution_events = _build_execution_events(result.message_history)

        # Record end
        if recorder:
            recorder.record_target_agent_end(
                agent_id=ctx.agent_id, status=result.status,
                final_output=result.final_output, duration_ms=result.duration_ms,
                iteration_count=result.iteration_count,
                message_history=result.message_history or [],
                tool_calls=result.tool_calls or [],
                error=result.error,
            )
            recorder.record_orchestrator_tool_result(
                "run_target_agent",
                f"status={result.status}, duration={result.duration_ms}ms",
                result.duration_ms,
            )

        emit_event(ctx.run_id, "agent_done", "runtime",
                   f"Agent finished: {result.status} ({result.duration_ms}ms)",
                   duration_ms=result.duration_ms)

        # Truncate output to avoid Ollama context overflow (500 errors)
        output_preview = result.final_output[:800] if result.final_output else "empty"

        return ToolResponse(content=(
            f"EXECUTION_RESULT:\n"
            f"  status: {result.status}\n"
            f"  duration_ms: {result.duration_ms}\n"
            f"  iterations: {result.iteration_count}\n"
            f"  tool_calls: {len(result.tool_calls)}\n"
            f"  output_preview:\n{output_preview}\n"
            f"  error: {result.error or 'none'}"
        ))

    def run_judge_subagent(analysis_request: str) -> ToolResponse:
        """Ask the JudgeSubAgent to evaluate the output. Returns VERDICT, SCORE, RATIONALE. Call AFTER run_target_agent."""
        emit_event(ctx.run_id, "subagent_start", "judgment",
                   "JudgeSubAgent starting",
                   details={"subagent": "JudgeSubAgent", "prompt": analysis_request[:3000]})
        recorder = TraceRecorder.get(ctx.run_id)
        if recorder:
            recorder.record_orchestrator_tool_call("run_judge_subagent", {"analysis_request": analysis_request})

        t0 = time.time()
        res = _run_async(judge_subagent(Msg("user", analysis_request, "user")))
        text = _extract_text(res.content if hasattr(res, "content") else str(res))
        duration_ms = int((time.time() - t0) * 1000)

        score_match = re.search(r"SCORE[:\s]*(\d+)", text)
        verdict_match = re.search(r"VERDICT[:\s]*(PASS|FAIL|PARTIAL)", text, re.IGNORECASE)
        if score_match:
            ctx.score = float(score_match.group(1))
        if verdict_match:
            v = verdict_match.group(1).upper()
            ctx.verdict = {"PASS": "passed", "PARTIAL": "passed_with_warnings", "FAIL": "failed"}.get(v, "unknown")
        ctx.summary = text

        if recorder:
            model = _get_config_sync().get("workers", {}).get("verdict", {}).get("model") \
                or _get_config_sync().get("orchestrator", {}).get("model", "mistral")
            recorder.record_subagent_call(
                subagent_name="JudgeSubAgent", role="verdict",
                model=model, prompt=analysis_request, response=text,
                duration_ms=duration_ms,
                extracted={"verdict": ctx.verdict, "score": ctx.score},
            )
            recorder.record_orchestrator_tool_result("run_judge_subagent", text, duration_ms)

        emit_event(ctx.run_id, "subagent_done", "judgment",
                   f"JudgeSubAgent: {ctx.verdict} ({ctx.score}/100) in {duration_ms}ms",
                   details={"subagent": "JudgeSubAgent", "response": text[:3000],
                            "verdict": ctx.verdict, "score": ctx.score,
                            "response_length": len(text)},
                   duration_ms=duration_ms)
        return ToolResponse(content=text)

    def run_robustness_subagent(request: str) -> ToolResponse:
        """Ask the RobustnessSubAgent to propose a follow-up edge case test."""
        emit_event(ctx.run_id, "subagent_start", "diagnostic",
                   "RobustnessSubAgent starting",
                   details={"subagent": "RobustnessSubAgent", "prompt": request[:3000]})
        recorder = TraceRecorder.get(ctx.run_id)
        if recorder:
            recorder.record_orchestrator_tool_call("run_robustness_subagent", {"request": request})
        t0 = time.time()
        res = _run_async(robustness_subagent(Msg("user", request, "user")))
        text = _extract_text(res.content if hasattr(res, "content") else str(res))
        duration_ms = int((time.time() - t0) * 1000)
        if recorder:
            model = _get_config_sync().get("workers", {}).get("diagnostic", {}).get("model") \
                or _get_config_sync().get("orchestrator", {}).get("model", "mistral")
            recorder.record_subagent_call(
                subagent_name="RobustnessSubAgent", role="diagnostic",
                model=model, prompt=request, response=text, duration_ms=duration_ms,
            )
            recorder.record_orchestrator_tool_result("run_robustness_subagent", text, duration_ms)
        emit_event(ctx.run_id, "subagent_done", "diagnostic",
                   f"RobustnessSubAgent done ({duration_ms}ms)",
                   details={"subagent": "RobustnessSubAgent", "response": text[:3000]},
                   duration_ms=duration_ms)
        return ToolResponse(content=text)

    def run_policy_subagent(request: str) -> ToolResponse:
        """Ask the PolicySubAgent to check governance compliance."""
        emit_event(ctx.run_id, "subagent_start", "assertion",
                   "PolicySubAgent starting",
                   details={"subagent": "PolicySubAgent", "prompt": request[:3000]})
        recorder = TraceRecorder.get(ctx.run_id)
        if recorder:
            recorder.record_orchestrator_tool_call("run_policy_subagent", {"request": request})
        t0 = time.time()
        res = _run_async(policy_subagent(Msg("user", request, "user")))
        text = _extract_text(res.content if hasattr(res, "content") else str(res))
        duration_ms = int((time.time() - t0) * 1000)
        if recorder:
            model = _get_config_sync().get("workers", {}).get("assertion", {}).get("model") \
                or _get_config_sync().get("orchestrator", {}).get("model", "mistral")
            recorder.record_subagent_call(
                subagent_name="PolicySubAgent", role="assertion",
                model=model, prompt=request, response=text, duration_ms=duration_ms,
            )
            recorder.record_orchestrator_tool_result("run_policy_subagent", text, duration_ms)
        emit_event(ctx.run_id, "subagent_done", "assertion",
                   f"PolicySubAgent done ({duration_ms}ms)",
                   details={"subagent": "PolicySubAgent", "response": text[:3000]},
                   duration_ms=duration_ms)
        return ToolResponse(content=text)

    def get_run_state() -> ToolResponse:
        """Get the current state of the test run."""
        return ToolResponse(content=(
            f"RUN_STATE:\n"
            f"  run_id: {ctx.run_id}\n"
            f"  agent: {ctx.agent_id}\n"
            f"  target_status: {ctx.target_status or 'not_executed'}\n"
            f"  duration_ms: {ctx.target_duration_ms}\n"
            f"  verdict: {ctx.verdict or 'pending'}\n"
            f"  score: {ctx.score}\n"
            f"  output_length: {len(ctx.target_output)}"
        ))

    def save_run_result(summary: str) -> ToolResponse:
        """Persist test results to DB. ALWAYS call this as the LAST step."""
        final_summary = (summary or ctx.summary or "")[:5000]
        update_run(
            ctx.run_id, status="completed",
            verdict=ctx.verdict or "unknown", score=ctx.score,
            duration_ms=ctx.target_duration_ms,
            final_output=(ctx.target_output or "")[:10000],
            summary=final_summary,
            ended_at=datetime.now(timezone.utc),
            agent_version=ctx.agent_version,
        )
        emit_event(ctx.run_id, "run_completed", "verdict",
                   f"Test completed: {ctx.verdict} ({ctx.score}/100)")
        return ToolResponse(content=f"RUN_SAVED: run_id={ctx.run_id}, verdict={ctx.verdict}, score={ctx.score}/100")

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


# ─── OrchestratorAgent ───────────────────────────────────────────────────────

ORCHESTRATOR_PROMPT = """Tu es OrchestratorAgent, l'orchestrateur interactif de test d'agents d'Orkestra.

Mission centrale :
- tu testes des agents
- tu pilotes des sous-agents specialises
- tu executes l'agent sous test
- tu rends un verdict
- puis tu redonnes la main a l'utilisateur

Tu disposes des tools suivants :
- get_scenario_context : lis le contexte du scenario
- run_scenario_subagent : construit un scenario de test
- run_target_agent : execute le vrai agent sous test
- run_judge_subagent : juge le resultat (VERDICT + SCORE + RATIONALE)
- run_robustness_subagent : propose un test complementaire
- run_policy_subagent : verifie la conformite policy
- get_run_state : lis l'etat de session
- save_run_result : sauvegarde un run termine

Regles de comportement :
1. Tu reponds toujours en francais.
2. Tu restes direct, technique, utile.
3. Tu dois :
   - lire le contexte du scenario (get_scenario_context)
   - construire le scenario (run_scenario_subagent)
   - executer l'agent sous test (run_target_agent) avec l'input_prompt du scenario
   - faire juger le resultat (run_judge_subagent) en passant le scenario + la sortie
   - sauvegarder le run (save_run_result)
   - puis restituer un bilan
4. Apres un test termine, tu dois proposer des suites possibles :
   - test plus strict
   - cas ambigu
   - robustesse
   - comparaison
   - nouvelle variante
5. Ne fais pas de blabla.

Quand tu rends un resultat final, utilise cette structure :

RESUME:
<resume court>

STATUT:
<PASS | FAIL | PARTIAL>

AGENT_SOUS_TEST:
<agent_id>

DETAILS:
<points importants>

OPTIONS_SUIVANTES:
- <option 1>
- <option 2>
- <option 3>
"""


def build_orchestrator_agent(ctx: RunContext) -> ReActAgent:
    tools = _build_tools_and_subagents(ctx)
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


# ─── Persistent orchestrators for chat follow-ups ────────────────────────────

_active_orchestrators: dict[str, tuple[ReActAgent, RunContext]] = {}


async def chat_with_orchestrator(run_id: str, message: str) -> str:
    """Chat with the OrchestratorAgent for a given run.

    The orchestrator is stored in _active_orchestrators (in-memory dict)
    and shared with the run execution since both happen in the same process.
    If not found (e.g., after API restart), rebuild from DB with pre-populated context.
    """
    if run_id in _active_orchestrators:
        orchestrator, ctx = _active_orchestrators[run_id]
    else:
        # Rebuild (after restart) with context from DB
        orchestrator, ctx = await _rebuild_orchestrator_from_db(run_id)
        if orchestrator is None:
            return "Run not found. Cannot initialize orchestrator."
        _active_orchestrators[run_id] = (orchestrator, ctx)

    try:
        res = await asyncio.wait_for(
            orchestrator(Msg("user", message, "user")),
            timeout=120,
        )
        text = _extract_text(res.content if hasattr(res, "content") else str(res))
        emit_event(run_id, "orchestrator_chat", "interactive", f"User: {message[:100]}")
        return text
    except Exception as exc:
        logger.exception(f"chat_with_orchestrator failed for {run_id}")
        return f"Orchestrator error: {exc}"


async def _rebuild_orchestrator_from_db(run_id: str):
    """Rebuild an OrchestratorAgent from a completed run in the DB.

    Loads the run, scenario, and agent, then creates a new orchestrator
    whose RunContext is pre-populated with the run's previous results.
    The orchestrator can answer questions about the run without re-executing it.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from app.models.test_lab import TestRun, TestScenario
    from app.services import agent_registry_service

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with Session() as db:
            run = (await db.execute(
                select(TestRun).where(TestRun.id == run_id)
            )).scalar_one_or_none()
            if not run:
                return None, None

            scenario = (await db.execute(
                select(TestScenario).where(TestScenario.id == run.scenario_id)
            )).scalar_one_or_none()
            if not scenario:
                return None, None

            agent_def = await agent_registry_service.get_agent(db, scenario.agent_id)
            if not agent_def:
                return None, None

        ctx = RunContext(
            run_id=run_id,
            scenario_id=run.scenario_id,
            agent_id=scenario.agent_id,
            agent_label=getattr(agent_def, "name", scenario.agent_id),
            agent_version=run.agent_version or getattr(agent_def, "version", ""),
            scenario_name=scenario.name,
            input_prompt=scenario.input_prompt,
            expected_tools=scenario.expected_tools or [],
            timeout_seconds=scenario.timeout_seconds or 120,
            max_iterations=scenario.max_iterations or 5,
            # Pre-populate from the previous run
            target_output=run.final_output or "",
            target_status=run.status or "",
            target_duration_ms=run.duration_ms or 0,
            score=run.score or 0.0,
            verdict=run.verdict or "",
            summary=run.summary or "",
        )

        orchestrator = build_orchestrator_agent(ctx)

        # Seed the orchestrator's memory with context about the completed run
        context_msg = Msg(
            "system",
            f"Un test a deja ete execute pour cet agent. Voici le contexte:\n"
            f"- Scenario: {ctx.scenario_name}\n"
            f"- Agent: {ctx.agent_id}\n"
            f"- Input: {ctx.input_prompt[:500]}\n"
            f"- Verdict: {ctx.verdict}\n"
            f"- Score: {ctx.score}/100\n"
            f"- Duration: {ctx.target_duration_ms}ms\n"
            f"- Output (preview): {ctx.target_output[:1000]}\n"
            f"- Summary: {ctx.summary[:1000]}\n\n"
            f"L'utilisateur peut te poser des questions sur ce resultat ou te demander des follow-ups. "
            f"Reponds en francais.",
            "system",
        )
        try:
            await orchestrator.memory.add(context_msg)
        except Exception:
            pass

        return orchestrator, ctx
    finally:
        await engine.dispose()


# ─── Main entry point ────────────────────────────────────────────────────────

async def run_orchestrated_test(run_id: str, scenario_id: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from app.models.test_lab import TestScenario
    from app.services import agent_registry_service

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Start trace recorder FIRST so all events are captured
    recorder = TraceRecorder.start(run_id)
    ctx: RunContext | None = None

    try:
        update_run(run_id, status="running", started_at=datetime.now(timezone.utc))
        emit_event(run_id, "run_started", "orchestration", "OrchestratorAgent starting")
        recorder.record_lifecycle("run_started")

        async with Session() as db:
            scenario = (await db.execute(
                select(TestScenario).where(TestScenario.id == scenario_id)
            )).scalar_one_or_none()
            if not scenario:
                raise ValueError(f"Scenario {scenario_id} not found")
            agent_def = await agent_registry_service.get_agent(db, scenario.agent_id)
            if not agent_def:
                raise ValueError(f"Agent {scenario.agent_id} not found")

        # Record context in trace
        recorder.set_scenario(scenario)
        recorder.set_agent_under_test(agent_def)
        recorder.record_lifecycle("loaded_scenario_and_agent")

        # Record orchestrator config from dynamic config
        cfg = _get_config_sync()
        orch_model = cfg.get("orchestrator", {}).get("model", "mistral")
        settings_local = get_settings()
        host = getattr(settings_local, "OLLAMA_HOST", "http://localhost:11434")
        recorder.set_orchestrator_config(
            model=orch_model, host=host,
            system_prompt=ORCHESTRATOR_PROMPT, max_iters=12,
        )

        # Record subagent configs
        workers = cfg.get("workers", {})
        for role, sub_name in [
            ("preparation", "ScenarioSubAgent"),
            ("verdict", "JudgeSubAgent"),
            ("diagnostic", "RobustnessSubAgent"),
            ("assertion", "PolicySubAgent"),
        ]:
            worker_cfg = workers.get(role, {})
            sub_model = worker_cfg.get("model") or orch_model
            recorder.add_subagent_config(
                name=sub_name, role=role, model=sub_model,
                host=host, system_prompt=worker_cfg.get("prompt", ""), max_iters=1,
            )

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
        _active_orchestrators[run_id] = (orchestrator, ctx)
        recorder.record_lifecycle("orchestrator_built")

        user_msg_text = (
            f"Lance le test du scenario '{ctx.scenario_name}' pour l'agent '{ctx.agent_id}'. "
            f"Input: {ctx.input_prompt}"
        )
        user_msg = Msg("user", user_msg_text, "user")
        recorder.record_orchestrator_start(user_msg_text)

        response = await asyncio.wait_for(
            orchestrator(user_msg),
            timeout=ctx.timeout_seconds + 180,
        )

        final_text = _extract_text(response.content if hasattr(response, "content") else str(response))

        if not ctx.verdict:
            update_run(run_id, status="completed", verdict="unknown", score=0,
                       duration_ms=ctx.target_duration_ms,
                       final_output=(ctx.target_output or "")[:10000],
                       summary=final_text[:5000],
                       ended_at=datetime.now(timezone.utc))

        # Finalize and save trace
        recorder.finalize(
            verdict=ctx.verdict or "unknown",
            score=ctx.score,
            summary=final_text or ctx.summary,
            final_output=ctx.target_output or "",
        )
        trace_path = recorder.save()
        emit_event(run_id, "trace_saved", "lifecycle", f"Trace saved to {trace_path}",
                   details={"trace_path": trace_path})

    except Exception as exc:
        logger.exception(f"OrchestratorAgent failed for run {run_id}")
        import traceback as _tb
        recorder.record_error("lifecycle", "orchestrator_failed",
                              str(exc), _tb.format_exc())

        # Save partial results if target agent ran before the crash
        if ctx and ctx.target_output and not ctx.verdict:
            update_run(run_id, status="completed", verdict="error",
                       score=0, duration_ms=ctx.target_duration_ms,
                       final_output=(ctx.target_output or "")[:10000],
                       summary=f"OrchestratorAgent crashed after target agent execution: {exc}",
                       error_message=str(exc)[:1000],
                       ended_at=datetime.now(timezone.utc))
            emit_event(run_id, "run_completed", "error",
                       f"Partial result saved (orchestrator crashed): {exc}")
        else:
            update_run(run_id, status="failed", error_message=str(exc)[:1000],
                       ended_at=datetime.now(timezone.utc))
            emit_event(run_id, "run_failed", "error", f"Run failed: {exc}")

        # Save trace even on failure
        try:
            recorder.finalize(
                verdict=ctx.verdict if ctx else "error",
                score=ctx.score if ctx else 0.0,
                summary=str(exc),
                final_output=ctx.target_output if ctx else "",
                error=str(exc),
            )
            trace_path = recorder.save()
            emit_event(run_id, "trace_saved", "lifecycle", f"Trace saved (failed run) to {trace_path}",
                       details={"trace_path": trace_path})
        except Exception as trace_exc:
            logger.error(f"Failed to save trace after failure: {trace_exc}")
    finally:
        # Cleanup recorder
        TraceRecorder.remove(run_id)
        await engine.dispose()
