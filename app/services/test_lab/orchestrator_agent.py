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


def _make_model(worker_name: str | None = None):
    config = _get_config_sync()
    orch = config.get("orchestrator", {})

    model_name = None
    if worker_name and worker_name in config.get("workers", {}):
        model_name = config["workers"][worker_name].get("model")
    if not model_name:
        model_name = orch.get("model", "mistral")

    provider = orch.get("provider", "ollama")
    api_key = orch.get("api_key", "") or ""
    settings = get_settings()

    if provider == "openai":
        from agentscope.model import OpenAIChatModel
        base_url = orch.get("host", "") or getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")
        key = api_key or getattr(settings, "OPENAI_API_KEY", "")
        return OpenAIChatModel(model_name=model_name, api_key=key, base_url=base_url)
    else:
        from agentscope.model import OllamaChatModel
        host = orch.get("host", "") or getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
        kwargs = {"model_name": model_name, "host": host, "stream": False}
        if api_key:
            kwargs["api_key"] = api_key
        return OllamaChatModel(**kwargs)


def _build_subagent(name: str, sys_prompt: str, worker_key: str) -> ReActAgent:
    """Build a persistent SubAgent (created ONCE, reused across tool calls)."""
    model = _make_model(worker_key)
    config = _get_config_sync()
    provider = config.get("orchestrator", {}).get("provider", "ollama")
    if provider == "openai":
        from agentscope.formatter import OpenAIChatFormatter
        formatter = OpenAIChatFormatter()
    else:
        formatter = OllamaChatFormatter()
    return ReActAgent(
        name=name,
        model=model,
        formatter=formatter,
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
    assertions: list[dict] = field(default_factory=list)
    timeout_seconds: int = 120
    max_iterations: int = 5
    target_output: str = ""
    target_status: str = ""
    target_duration_ms: int = 0
    target_iteration_count: int = 0
    target_tool_calls: list[dict] = field(default_factory=list)
    execution_events: list[dict] = field(default_factory=list)
    score: float = 0.0
    verdict: str = ""
    summary: str = ""


# ─── Real SubAgent system prompts (single source of truth) ───────────────────

SUBAGENT_SYSTEM_PROMPTS: dict[str, dict[str, str]] = {
    "ScenarioSubAgent": {
        "role": "preparation",
        "prompt": (
            "Tu es un sous-agent de scenarisation de test.\n"
            "Tu aides l'orchestrateur a transformer un besoin de test en scenario concret.\n"
            "Reponds en francais.\n\n"
            "Format obligatoire :\n"
            "SCENARIO:\n<description courte et exploitable>\n\n"
            "SUCCESS_CRITERIA:\n- <critere 1>\n- <critere 2>\n- <critere 3>\n\n"
            "TEST_INPUT:\n<entree de test realiste>"
        ),
    },
    "JudgeSubAgent": {
        "role": "verdict",
        "prompt": (
            "Tu es un sous-agent juge.\n"
            "Tu evalues la sortie d'un agent sous test par rapport a un scenario et des criteres.\n"
            "Reponds en francais.\n\n"
            "Format obligatoire :\n"
            "VERDICT: PASS ou FAIL ou PARTIAL\n"
            "SCORE: <nombre entre 0 et 100>\n"
            "RATIONALE:\n<explication courte>"
        ),
    },
    "RobustnessSubAgent": {
        "role": "diagnostic",
        "prompt": (
            "Tu es un sous-agent de robustesse.\n"
            "Tu proposes un test complementaire plus dur ou un edge case.\n"
            "Reponds en francais.\n\n"
            "Format obligatoire :\n"
            "FOLLOWUP_TEST:\n<test complementaire>\n\n"
            "WHY_IT_MATTERS:\n<pourquoi ce test est utile>"
        ),
    },
    "PolicySubAgent": {
        "role": "assertion",
        "prompt": (
            "Tu es un sous-agent de conformite policy.\n"
            "Tu verifies si la sortie d'un agent respecte ses contraintes de gouvernance.\n"
            "Reponds en francais.\n\n"
            "Format obligatoire :\n"
            "COMPLIANCE: OK ou VIOLATION\n"
            "DETAILS:\n<explication>"
        ),
    },
}


# ─── Build tools + persistent subagents (same pattern as orchestrateur_chat.py)

def _build_tools_and_subagents(ctx: RunContext) -> list:
    """Build tools with PERSISTENT subagents — created once, reused."""

    # ── Persistent SubAgents (like orchestrateur_chat.py) ────────────────
    scenario_subagent = _build_subagent(
        "ScenarioSubAgent",
        SUBAGENT_SYSTEM_PROMPTS["ScenarioSubAgent"]["prompt"],
        "preparation",
    )

    judge_subagent = _build_subagent(
        "JudgeSubAgent",
        SUBAGENT_SYSTEM_PROMPTS["JudgeSubAgent"]["prompt"],
        "verdict",
    )

    robustness_subagent = _build_subagent(
        "RobustnessSubAgent",
        SUBAGENT_SYSTEM_PROMPTS["RobustnessSubAgent"]["prompt"],
        "diagnostic",
    )

    policy_subagent = _build_subagent(
        "PolicySubAgent",
        SUBAGENT_SYSTEM_PROMPTS["PolicySubAgent"]["prompt"],
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

    def run_scenario_subagent(task: str = "") -> ToolResponse:
        """Ask the ScenarioSubAgent to prepare a test plan. Call BEFORE run_target_agent."""
        # Same semantic fix as in the Judge: empty expected_tools = no constraint
        if ctx.expected_tools:
            tools_line = f"Tools attendus (obligatoires): {', '.join(ctx.expected_tools)}"
        else:
            tools_line = (
                "Tools attendus: aucune contrainte — l'agent est libre d'utiliser "
                "ou non les tools de ses MCP autorises"
            )

        # Enrich with full scenario context
        enriched = (
            f"Tu dois preparer un plan de test structure pour un agent Orkestra.\n\n"
            f"=== AGENT SOUS TEST ===\n"
            f"ID: {ctx.agent_id}\n"
            f"Nom: {ctx.agent_label}\n\n"
            f"=== SCENARIO ===\n"
            f"Nom du scenario: {ctx.scenario_name}\n"
            f"Input a envoyer a l'agent: {ctx.input_prompt}\n"
            f"{tools_line}\n"
            f"Timeout: {ctx.timeout_seconds}s\n\n"
            f"=== DEMANDE ORCHESTRATOR ===\n"
            f"{task}\n\n"
            f"Produis un plan structure : SCENARIO / SUCCESS_CRITERIA / TEST_INPUT."
        )

        emit_event(ctx.run_id, "subagent_start", "preparation",
                   "ScenarioSubAgent starting",
                   details={"subagent": "ScenarioSubAgent", "prompt": enriched[:3000]})
        recorder = TraceRecorder.get(ctx.run_id)
        if recorder:
            recorder.record_orchestrator_tool_call("run_scenario_subagent", {
                "original_task": task,
                "enriched_length": len(enriched),
            })
        t0 = time.time()
        res = _run_async(scenario_subagent(Msg("user", enriched, "user")))
        text = _extract_text(res.content if hasattr(res, "content") else str(res))
        duration_ms = int((time.time() - t0) * 1000)
        if recorder:
            model = _get_config_sync().get("workers", {}).get("preparation", {}).get("model") \
                or _get_config_sync().get("orchestrator", {}).get("model", "mistral")
            recorder.record_subagent_call(
                subagent_name="ScenarioSubAgent", role="preparation",
                model=model, prompt=enriched, response=text, duration_ms=duration_ms,
            )
            recorder.record_orchestrator_tool_result("run_scenario_subagent", text, duration_ms)
        emit_event(ctx.run_id, "subagent_done", "preparation",
                   f"ScenarioSubAgent done ({duration_ms}ms)",
                   details={"subagent": "ScenarioSubAgent", "response": text[:3000],
                            "response_length": len(text)},
                   duration_ms=duration_ms)
        return ToolResponse(content=text)

    def run_target_agent(task: str = "") -> ToolResponse:
        """Execute the REAL agent under test with the scenario's input_prompt.

        Note: the 'task' parameter is ignored — we ALWAYS use ctx.input_prompt
        from the scenario to ensure the test is reproducible and faithful.
        """
        # CRITICAL: always use the scenario's input_prompt, never the orchestrator's paraphrase
        real_input = ctx.input_prompt

        emit_event(ctx.run_id, "phase_start", "runtime", f"Executing target agent {ctx.agent_id}")
        recorder = TraceRecorder.get(ctx.run_id)
        if recorder:
            recorder.record_orchestrator_tool_call("run_target_agent", {
                "task_ignored": task,
                "actual_input_prompt": real_input,
            })

        # Resolve real tools / mcps / skills for this agent (for the trace)
        real_tools: list[str] = []
        real_mcps: list[dict] = []
        real_skills: list[str] = []
        real_system_prompt: str | None = None
        real_model: str = "default"

        async def _resolve_agent_metadata():
            """Resolve metadata BEFORE running the agent so we can record start accurately."""
            from app.services import agent_registry_service
            from app.services.mcp_tool_registry import get_tools_for_mcp
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            from sqlalchemy.orm import sessionmaker

            settings = get_settings()
            engine = create_async_engine(settings.DATABASE_URL)
            Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

            local_tools: list[str] = []
            local_mcps: list[dict] = []
            local_skills: list[str] = []
            local_system_prompt: str | None = None
            local_model: str = "default"

            try:
                async with Session() as db:
                    agent_def = await agent_registry_service.get_agent(db, ctx.agent_id)
                    if agent_def:
                        local_mcps = [{"id": m} for m in (agent_def.allowed_mcps or [])]
                        local_skills = [
                            s.skill_id for s in getattr(agent_def, "agent_skills", [])
                        ]
                        for mcp_id in (agent_def.allowed_mcps or []):
                            tools_for_mcp = get_tools_for_mcp(mcp_id) or []
                            for t in tools_for_mcp:
                                if hasattr(t, "__name__"):
                                    local_tools.append(f"{mcp_id}:{t.__name__}")
                                else:
                                    local_tools.append(f"{mcp_id}:tool")
                        local_system_prompt = agent_def.prompt_content
                        local_model = agent_def.llm_model or "platform_default"
            finally:
                await engine.dispose()

            return local_tools, local_mcps, local_skills, local_system_prompt, local_model

        async def _execute_target_and_capture_tools():
            """Run the agent and also capture the REAL toolkit tools from the AgentScope instance."""
            from app.services.test_lab.target_agent_runner import run_target_agent as _run
            from app.services.agent_factory import (
                create_agentscope_agent, get_tools_for_agent,
            )
            from app.services import agent_registry_service
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            from sqlalchemy.orm import sessionmaker

            settings = get_settings()
            engine = create_async_engine(settings.DATABASE_URL)
            Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

            runtime_tool_names: list[str] = []
            try:
                async with Session() as db:
                    # Pre-introspect the agent to get runtime tool names for the trace
                    try:
                        agent_def = await agent_registry_service.get_agent(db, ctx.agent_id)
                        if agent_def:
                            local_tools = get_tools_for_agent(agent_def) or []
                            for t in local_tools:
                                name = getattr(t, "__name__", None) or getattr(t, "name", None)
                                if name:
                                    runtime_tool_names.append(str(name))
                    except Exception as exc:
                        logger.debug(f"Could not pre-introspect tools: {exc}")

                    result = await _run(
                        db=db, agent_id=ctx.agent_id, agent_version=ctx.agent_version,
                        input_prompt=real_input, timeout_seconds=ctx.timeout_seconds,
                        max_iterations=ctx.max_iterations,
                    )
            finally:
                await engine.dispose()
            return result, runtime_tool_names

        # STEP 1: Resolve metadata and record START event BEFORE executing the agent
        (
            real_tools,
            real_mcps,
            real_skills,
            real_system_prompt,
            real_model,
        ) = _run_async(_resolve_agent_metadata())

        if recorder:
            recorder.record_target_agent_start(
                agent_id=ctx.agent_id, input_prompt=real_input,
                model=real_model,
                tools=real_tools, mcps=real_mcps, skills=real_skills,
                system_prompt=real_system_prompt,
            )

        # STEP 2: Execute the agent (recording end immediately after)
        result, runtime_tool_names = _run_async(_execute_target_and_capture_tools())

        # Enrich the start event retroactively with runtime-discovered tools/mcps
        # so that readers of the trace see the full picture even looking at "start"
        if recorder and result:
            discovered = list(getattr(result, "discovered_tools", []) or [])
            connected = list(getattr(result, "connected_mcps", []) or [])
            # Walk back through events to find the most recent target_agent start
            for ev in reversed(recorder.trace.events):
                if (ev.get("category") == "target_agent"
                        and ev.get("event_type") == "start"
                        and ev.get("name") == ctx.agent_id):
                    data = ev.setdefault("data", {})
                    if discovered:
                        # Merge without duplicates, preserving order
                        merged = list(dict.fromkeys(
                            (data.get("available_tools") or []) + discovered
                        ))
                        data["available_tools"] = merged
                    if connected:
                        # Merge mcps by id, keeping richest entry
                        existing = {m.get("id"): m for m in (data.get("available_mcps") or []) if isinstance(m, dict)}
                        for m in connected:
                            if isinstance(m, dict) and m.get("id"):
                                existing[m["id"]] = {**existing.get(m["id"], {}), **m}
                        data["available_mcps"] = list(existing.values())
                    break

        ctx.target_output = result.final_output
        ctx.target_status = result.status
        ctx.target_duration_ms = result.duration_ms
        ctx.target_iteration_count = result.iteration_count
        ctx.target_tool_calls = result.tool_calls or []
        from app.services.test_lab.target_agent_runner import _build_execution_events
        ctx.execution_events = _build_execution_events(result.message_history)

        # Emit tool_call_completed events for each tool the target agent called.
        # This is REQUIRED so the deterministic assertion engine (which reads
        # from the DB events table) can match `tool_called` / `tool_not_called`
        # assertions. Without this, assertions always see zero tool calls.
        for tc in (result.tool_calls or []):
            tool_name = tc.get("tool_name") if isinstance(tc, dict) else None
            if tool_name:
                emit_event(
                    ctx.run_id,
                    "tool_call_completed",
                    "runtime",
                    f"Tool '{tool_name}' called",
                    details={
                        "tool_name": tool_name,
                        "tool_input": (tc.get("tool_input", "") if isinstance(tc, dict) else "")[:500],
                        "output_preview": (tc.get("tool_output", "") if isinstance(tc, dict) else "")[:500],
                    },
                )

        # Record end (enriched with runtime discovery)
        if recorder:
            recorder.record_target_agent_end(
                agent_id=ctx.agent_id, status=result.status,
                final_output=result.final_output, duration_ms=result.duration_ms,
                iteration_count=result.iteration_count,
                message_history=result.message_history or [],
                tool_calls=result.tool_calls or [],
                error=result.error,
                connected_mcps=getattr(result, "connected_mcps", []) or [],
                discovered_tools=getattr(result, "discovered_tools", []) or [],
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
        # CRITICAL: enrich the Judge prompt with FULL context automatically.
        # The orchestrator can pass any request, but we always append the full
        # scenario + agent output so the Judge has everything to evaluate.
        #
        # IMPORTANT semantic fix: when ctx.expected_tools is empty, we must say
        # "no specific constraint" — NOT "(aucun)" — because some LLMs wrongly
        # interpret "aucun" as "the agent must NOT use any tools", which is
        # false (empty expected_tools = no constraint, free to use tools).
        if ctx.expected_tools:
            tools_line = (
                f"Tools attendus (obligatoires): {', '.join(ctx.expected_tools)}"
            )
        else:
            tools_line = (
                "Tools attendus: aucune contrainte — l'agent est libre d'utiliser ou "
                "non les tools de ses MCP autorises (ce n'est PAS une interdiction)"
            )

        # Build tool calls summary for the judge
        _tc_list = ctx.target_tool_calls or []
        if _tc_list:
            _tc_lines = "\n".join(
                f"  - {(tc.get('tool_name') if isinstance(tc, dict) else str(tc))}"
                for tc in _tc_list
            )
            tool_calls_section = f"Tools effectivement appeles ({len(_tc_list)}):\n{_tc_lines}"
        else:
            tool_calls_section = "Tools effectivement appeles: AUCUN"

        enriched_prompt = (
            f"Tu dois evaluer le resultat d'un test d'agent.\n\n"
            f"=== SCENARIO ===\n"
            f"Nom: {ctx.scenario_name}\n"
            f"Input envoye a l'agent: {ctx.input_prompt}\n"
            f"{tools_line}\n\n"
            f"=== AGENT SOUS TEST ===\n"
            f"ID: {ctx.agent_id}\n"
            f"Nom: {ctx.agent_label}\n\n"
            f"=== RESULTAT D'EXECUTION ===\n"
            f"Status: {ctx.target_status}\n"
            f"Duree: {ctx.target_duration_ms}ms\n"
            f"Iterations: {ctx.target_iteration_count}\n"
            f"{tool_calls_section}\n\n"
            f"=== OUTPUT COMPLET DE L'AGENT ===\n"
            f"{(ctx.target_output or 'EMPTY')[:2000]}\n\n"
            f"=== DEMANDE D'ANALYSE ===\n"
            f"{analysis_request}\n\n"
            f"Evalue si l'agent a repondu correctement au scenario.\n"
            f"REGLES D'EVALUATION:\n"
            f"- Si 'Tools attendus: aucune contrainte', NE PENALISE PAS l'agent\n"
            f"  pour avoir utilise ou non des tools. Seul le contenu de sa reponse\n"
            f"  et sa fidelite au scenario comptent.\n"
            f"- Si des tools sont listes comme obligatoires, verifie qu'ils ont\n"
            f"  effectivement ete appeles.\n"
            f"- Un agent qui tente de resoudre un probleme et explique clairement\n"
            f"  pourquoi il echoue (ex: API inaccessible) merite un score partiel\n"
            f"  (PARTIAL 40-60) et non un FAIL total.\n\n"
            f"Format de reponse OBLIGATOIRE (respecte-le EXACTEMENT) :\n"
            f"VERDICT: PASS | FAIL | PARTIAL\n"
            f"SCORE: <entier entre 0 et 100, en CHIFFRES UNIQUEMENT>\n"
            f"RATIONALE: <explication>\n\n"
            f"IMPORTANT: Le SCORE doit etre un ENTIER en chiffres (ex: 55), "
            f"JAMAIS en lettres (pas 'cinquante', pas 'fifty'). "
            f"Pas de fraction, pas d'intervalle, pas de texte autre que le nombre."
        )

        emit_event(ctx.run_id, "subagent_start", "judgment",
                   "JudgeSubAgent starting",
                   details={"subagent": "JudgeSubAgent", "prompt": enriched_prompt[:3000]})
        recorder = TraceRecorder.get(ctx.run_id)
        if recorder:
            recorder.record_orchestrator_tool_call("run_judge_subagent", {
                "original_request": analysis_request,
                "enriched_prompt_length": len(enriched_prompt),
            })

        t0 = time.time()
        try:
            res = _run_async(judge_subagent(Msg("user", enriched_prompt, "user")))
            text = _extract_text(res.content if hasattr(res, "content") else str(res))
        except Exception as judge_exc:
            duration_ms = int((time.time() - t0) * 1000)
            logger.warning(f"JudgeSubAgent LLM failed ({judge_exc}), falling back to auto-evaluate")
            auto_verdict, auto_score, auto_summary = _auto_evaluate(ctx)
            ctx.verdict = auto_verdict
            ctx.score = auto_score
            ctx.summary = f"[auto-evaluate] {auto_summary}"
            emit_event(ctx.run_id, "subagent_done", "judgment",
                       f"JudgeSubAgent failed — auto-evaluated: {auto_verdict} ({auto_score}/100)",
                       details={"error": str(judge_exc)[:200]},
                       duration_ms=duration_ms)
            return ToolResponse(content=f"VERDICT: AUTO\nSCORE: {int(auto_score)}\nRATIONALE: {auto_summary}")
        duration_ms = int((time.time() - t0) * 1000)

        # Strip AgentScope "thinking" blocks before extracting verdict/score.
        # The LLM can reason freely inside a thinking block (e.g. "SCORE 0-10?")
        # which would otherwise poison the regex. We only want to parse the
        # FINAL answer that follows the thinking.
        def _strip_thinking(raw: str) -> str:
            # Remove blocks like {'type': 'thinking', 'thinking': '...'}
            # AgentScope serializes these as plain text in front of the real answer.
            cleaned = re.sub(
                r"\{['\"]type['\"]\s*:\s*['\"]thinking['\"][^}]*\}",
                "",
                raw,
                flags=re.DOTALL,
            )
            # Also strip any leftover lines that look like thinking preamble
            return cleaned.strip()

        parse_text = _strip_thinking(text)
        # Use rfind/last-match semantics: the authoritative verdict/score is the
        # LAST one emitted by the Judge, not any earlier mention.
        score_matches = list(re.finditer(r"SCORE\s*[:=]\s*(\d{1,3})\b", parse_text, re.IGNORECASE))
        verdict_matches = list(re.finditer(r"VERDICT\s*[:=]\s*(PASS|FAIL|PARTIAL)", parse_text, re.IGNORECASE))
        if score_matches:
            raw_score = int(score_matches[-1].group(1))
            ctx.score = float(max(0, min(100, raw_score)))
        else:
            # Fallback: the LLM may have written the number in words (e.g. "fifty").
            # Map common English/French number words to digits.
            _word_to_num = {
                "zero": 0, "ten": 10, "twenty": 20, "thirty": 30, "forty": 40,
                "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
                "hundred": 100, "one hundred": 100,
                "zero ": 0, "dix": 10, "vingt": 20, "trente": 30, "quarante": 40,
                "cinquante": 50, "soixante": 60, "soixante-dix": 70, "septante": 70,
                "quatre-vingt": 80, "huitante": 80, "quatre-vingt-dix": 90, "nonante": 90,
                "cent": 100,
            }
            score_word_match = re.search(
                r"SCORE\s*[:=]\s*([a-z\-\sà-ÿ]{3,25}?)\s*(?:\n|RATIONALE|$)",
                parse_text,
                re.IGNORECASE,
            )
            if score_word_match:
                candidate = score_word_match.group(1).strip().lower()
                for word, val in sorted(_word_to_num.items(), key=lambda kv: -len(kv[0])):
                    if word in candidate:
                        ctx.score = float(val)
                        logger.info(f"Extracted score from word '{candidate}' -> {val}")
                        break
        if verdict_matches:
            v = verdict_matches[-1].group(1).upper()
            ctx.verdict = {"PASS": "passed", "PARTIAL": "passed_with_warnings", "FAIL": "failed"}.get(v, "unknown")
        ctx.summary = text

        if recorder:
            model = _get_config_sync().get("workers", {}).get("verdict", {}).get("model") \
                or _get_config_sync().get("orchestrator", {}).get("model", "mistral")
            recorder.record_subagent_call(
                subagent_name="JudgeSubAgent", role="verdict",
                model=model, prompt=enriched_prompt, response=text,
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

    # Only register the 4 mandatory tools to keep toolkit schema small.
    # Optional tools (robustness, policy, state) inflate the LLM context and
    # cause 500s on cloud models with tight context budgets.
    return [
        run_scenario_subagent,
        run_target_agent,
        run_judge_subagent,
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
3. Tu DOIS TOUJOURS, dans cet ordre precis, executer ces 3 tools (aucun ne peut etre saute) :
   a) run_scenario_subagent — pour construire le plan de test (passe 'Prepare test plan')
   b) run_target_agent      — pour executer l'agent sous test (le parametre task est ignore,
                              le vrai input_prompt du scenario est toujours utilise)
   c) run_judge_subagent    — pour juger le resultat (VERDICT + SCORE + RATIONALE)
4. Tools optionnels (tu peux les appeler si utile, mais ce n'est pas obligatoire) :
   - get_scenario_context : si tu veux relire le contexte du scenario
   - save_run_result      : Orkestra persiste le run automatiquement, mais tu peux
                            l'appeler pour forcer la sauvegarde explicite
   - run_robustness_subagent : pour proposer un test complementaire
   - run_policy_subagent    : pour verifier la conformite policy
5. Apres avoir appele les 3 tools obligatoires, tu rends le bilan final au format indique ci-dessous.
6. Apres le bilan, tu dois proposer des suites possibles :
   - test plus strict
   - cas ambigu
   - robustesse
   - comparaison
   - nouvelle variante
7. Ne fais pas de blabla. Pas de texte libre avant d'avoir appele les 3 tools obligatoires.

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


def _auto_evaluate(ctx: "RunContext") -> tuple[str, float, str]:
    """Fallback evaluation when the judge LLM is unavailable.

    Runs the scenario assertions against ctx.target_output and produces a
    verdict/score/summary without calling any LLM.

    Returns (verdict, score, summary).
    """
    output = (ctx.target_output or "").strip()
    assertions = ctx.assertions or []

    if not output:
        return "failed", 0.0, "Auto-eval: no output from target agent."

    passed, failed_critical, notes = 0, 0, []

    for a in assertions:
        atype = a.get("type", "")
        critical = a.get("critical", False)

        if atype == "output_field_exists":
            field = a.get("target", "")
            ok = field and field in output
        elif atype == "output_contains":
            expected = a.get("expected", "")
            ok = expected and expected in output
        elif atype == "no_tool_failures":
            ok = ctx.target_status != "error"
        elif atype == "max_duration_ms":
            try:
                ok = ctx.target_duration_ms <= int(a.get("expected", 9999999))
            except (TypeError, ValueError):
                ok = True
        else:
            ok = True  # unknown assertion type → don't penalise

        if ok:
            passed += 1
        else:
            notes.append(f"FAIL [{atype}]")
            if critical:
                failed_critical += 1

    total = len(assertions) or 1
    score = round((passed / total) * 100)

    if failed_critical > 0:
        verdict = "failed"
    elif score >= 80:
        verdict = "passed"
    elif score >= 40:
        verdict = "passed_with_warnings"
    else:
        verdict = "failed"

    summary = (
        f"RESUME:\nAuto-evaluation (judge LLM indisponible). "
        f"{passed}/{total} assertions passees.\n\n"
        f"STATUT:\n{verdict.upper()}\n\n"
        f"AGENT_SOUS_TEST:\n{ctx.agent_id}\n\n"
        f"DETAILS:\n"
        + ("\n".join(notes) if notes else "Toutes les assertions verifiees.")
        + f"\n\nScore: {score}/100 (calcul sur assertions, pas LLM)."
    )
    return verdict, float(score), summary


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

    Handles transient Ollama 500 errors by retrying up to 2 times before
    returning a friendly French message to the user.
    """
    if run_id in _active_orchestrators:
        orchestrator, ctx = _active_orchestrators[run_id]
    else:
        # Rebuild (after restart) with context from DB
        orchestrator, ctx = await _rebuild_orchestrator_from_db(run_id)
        if orchestrator is None:
            return "⚠️ Run introuvable. Impossible d'initialiser l'orchestrateur."
        _active_orchestrators[run_id] = (orchestrator, ctx)

    last_exc: Exception | None = None
    for attempt in range(1, 4):  # 3 tries total (1 + 2 retries)
        try:
            res = await asyncio.wait_for(
                orchestrator(Msg("user", message, "user")),
                timeout=120,
            )
            text = _extract_text(res.content if hasattr(res, "content") else str(res))
            emit_event(run_id, "orchestrator_chat", "interactive",
                       f"User: {message[:100]}")
            return text or "(L'orchestrateur n'a pas renvoye de texte)"
        except asyncio.TimeoutError:
            logger.warning(f"chat_with_orchestrator timeout (attempt {attempt}) for {run_id}")
            last_exc = Exception("timeout")
            break  # don't retry on timeout
        except Exception as exc:
            last_exc = exc
            err_str = str(exc)
            # Retry only on transient Ollama errors (5xx)
            is_transient = (
                "500" in err_str
                or "502" in err_str
                or "503" in err_str
                or "504" in err_str
                or "Internal Server Error" in err_str
            )
            if is_transient and attempt < 3:
                logger.warning(
                    f"chat_with_orchestrator transient error (attempt {attempt}/3) "
                    f"for {run_id}: {err_str[:200]}"
                )
                await asyncio.sleep(1.0 * attempt)  # 1s, 2s backoff
                continue
            logger.exception(f"chat_with_orchestrator failed for {run_id}")
            break

    # All attempts exhausted — return a friendly message
    err_str = str(last_exc) if last_exc else "unknown error"
    if "500" in err_str or "502" in err_str or "503" in err_str or "Internal Server Error" in err_str:
        return (
            "⚠️ Le service LLM (Ollama) est temporairement indisponible "
            "(erreur 5xx). J'ai reessaye 3 fois sans succes. Merci de retenter "
            "dans quelques secondes."
        )
    if "timeout" in err_str.lower():
        return (
            "⚠️ L'orchestrateur n'a pas repondu dans le delai imparti (120s). "
            "Le service LLM est peut-etre sature. Retente dans un moment."
        )
    return f"⚠️ Erreur de l'orchestrateur : {err_str[:300]}"


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

        # Record subagent configs — use the REAL runtime system prompts from
        # SUBAGENT_SYSTEM_PROMPTS (single source of truth), merged with the
        # per-worker model override from DB config.
        workers = cfg.get("workers", {})
        for sub_name, sub_def in SUBAGENT_SYSTEM_PROMPTS.items():
            role = sub_def["role"]
            real_prompt = sub_def["prompt"]
            worker_cfg = workers.get(role, {})
            sub_model = worker_cfg.get("model") or orch_model
            recorder.add_subagent_config(
                name=sub_name, role=role, model=sub_model,
                host=host, system_prompt=real_prompt, max_iters=1,
            )

        ctx = RunContext(
            run_id=run_id, scenario_id=scenario_id,
            agent_id=scenario.agent_id,
            agent_label=getattr(agent_def, "name", scenario.agent_id),
            agent_version=getattr(agent_def, "version", ""),
            scenario_name=scenario.name,
            input_prompt=scenario.input_prompt,
            expected_tools=scenario.expected_tools or [],
            assertions=[a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in (scenario.assertions or [])],
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

        # ── Deterministic assertions evaluation ─────────────────────────────
        # The LLM Judge gives a subjective verdict/score; here we run the
        # deterministic assertion engine on the scenario's declared assertions
        # so users get objective pass/fail rules too.
        assertion_results: list[dict] = []
        if scenario.assertions:
            try:
                from app.services.test_lab.assertion_engine import evaluate_assertions
                from app.models.test_lab import TestRunAssertion, TestRunEvent
                from sqlalchemy import select as _select
                from sqlalchemy.ext.asyncio import create_async_engine as _cae, AsyncSession as _AS
                from sqlalchemy.orm import sessionmaker as _sm

                # Fetch all events recorded by execution_engine.emit_event
                _eng2 = _cae(settings.DATABASE_URL)
                _Session2 = _sm(_eng2, class_=_AS, expire_on_commit=False)
                async with _Session2() as db2:
                    res = await db2.execute(
                        _select(TestRunEvent)
                        .where(TestRunEvent.run_id == run_id)
                        .order_by(TestRunEvent.timestamp)
                    )
                    all_events_rows = res.scalars().all()
                    all_events = [
                        {
                            "event_type": e.event_type,
                            "details": e.details,
                            "duration_ms": e.duration_ms,
                        }
                        for e in all_events_rows
                    ]

                    assertion_results = evaluate_assertions(
                        assertion_defs=scenario.assertions or [],
                        events=all_events,
                        final_output=ctx.target_output or "",
                        duration_ms=ctx.target_duration_ms,
                        iteration_count=ctx.target_iteration_count,
                        final_status=ctx.target_status or "completed",
                    )

                    for ar in assertion_results:
                        db2.add(
                            TestRunAssertion(
                                run_id=run_id,
                                assertion_type=ar["assertion_type"],
                                target=ar.get("target"),
                                expected=str(ar.get("expected")) if ar.get("expected") is not None else None,
                                actual=ar.get("actual"),
                                passed=ar["passed"],
                                critical=ar.get("critical", False),
                                message=ar["message"],
                                details=ar.get("details"),
                            )
                        )
                    await db2.commit()
                await _eng2.dispose()

                passed = sum(1 for a in assertion_results if a["passed"])
                total = len(assertion_results)
                emit_event(
                    run_id,
                    "phase_completed",
                    "assertions",
                    f"Assertions: {passed}/{total} passed",
                    details={"passed": passed, "total": total},
                )
                recorder.record_lifecycle(
                    "assertions_evaluated",
                    {
                        "passed": passed,
                        "total": total,
                        "results": [
                            {
                                "type": a["assertion_type"],
                                "passed": a["passed"],
                                "critical": a.get("critical", False),
                                "message": a["message"],
                            }
                            for a in assertion_results
                        ],
                    },
                )
            except Exception as assertion_exc:
                logger.warning(
                    f"Assertion evaluation failed for {run_id}: {assertion_exc}"
                )
                emit_event(
                    run_id,
                    "assertion_phase_failed",
                    "assertions",
                    f"Assertion engine error: {assertion_exc}",
                )

        # Always persist the final run state to DB (idempotent with save_run_result).
        # This guarantees the run transitions out of "running" even if the LLM
        # orchestrator skipped calling save_run_result.
        update_run(
            run_id,
            status="completed",
            verdict=ctx.verdict or "unknown",
            score=ctx.score or 0,
            duration_ms=ctx.target_duration_ms,
            final_output=(ctx.target_output or "")[:10000],
            summary=(final_text or ctx.summary or "")[:5000],
            ended_at=datetime.now(timezone.utc),
            agent_version=ctx.agent_version,
        )
        emit_event(run_id, "run_completed", "verdict",
                   f"Test completed: {ctx.verdict or 'unknown'} ({ctx.score}/100)")

        # Record run_completed lifecycle event BEFORE finalizing the trace
        recorder.record_lifecycle("run_completed", {
            "verdict": ctx.verdict or "unknown",
            "score": ctx.score,
            "target_duration_ms": ctx.target_duration_ms,
            "target_iteration_count": ctx.target_iteration_count,
            "final_output_length": len(ctx.target_output or ""),
        })

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
            # Try assertion-based auto-evaluation instead of giving a 0 score
            auto_verdict, auto_score, auto_summary = _auto_evaluate(ctx)
            update_run(run_id, status="completed",
                       verdict=auto_verdict, score=auto_score,
                       duration_ms=ctx.target_duration_ms,
                       final_output=(ctx.target_output or "")[:10000],
                       summary=auto_summary,
                       error_message=f"Judge unavailable (LLM 500): {str(exc)[:200]}",
                       ended_at=datetime.now(timezone.utc))
            emit_event(run_id, "run_completed", "verdict",
                       f"Auto-evaluated (judge crashed): {auto_verdict} {auto_score}/100")
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
