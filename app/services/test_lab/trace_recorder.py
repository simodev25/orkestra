"""Trace Recorder for Test Lab runs.

Captures every interaction during a run:
- OrchestratorAgent: system prompt, messages, tool calls, reasoning
- SubAgents: prompts, responses, duration, model used
- Target Agent: prompt, output, tools available, MCP servers, skills, message history
- Tool calls: name, input, output, duration
- MCP calls: server, tool, input, output

Writes a structured JSON file at debug-scenarios/<run_id>_<timestamp>.json
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("orkestra.test_lab.trace_recorder")


def _safe_truncate(s: any, max_len: int = 10000) -> any:
    """Truncate strings for JSON storage, preserve structure."""
    if isinstance(s, str) and len(s) > max_len:
        return s[:max_len] + f"... [truncated {len(s) - max_len} chars]"
    return s


@dataclass
class TraceEvent:
    """A single event in the trace."""
    timestamp: str
    elapsed_ms: int
    category: str                    # orchestrator/subagent/target_agent/tool_call/mcp_call/lifecycle
    event_type: str                  # start/end/call/response/error
    name: str                        # agent/tool/subagent name
    data: dict = field(default_factory=dict)


@dataclass
class ScenarioContext:
    """The scenario being tested."""
    scenario_id: str
    name: str
    description: str | None
    input_prompt: str
    expected_tools: list[str]
    assertions: list[dict]
    tags: list[str]
    timeout_seconds: int
    max_iterations: int


@dataclass
class AgentUnderTestSnapshot:
    """Snapshot of the agent being tested."""
    agent_id: str
    agent_name: str
    agent_version: str
    family_id: str | None
    purpose: str | None
    description: str | None
    skill_ids: list[str]
    allowed_mcps: list[str]
    forbidden_effects: list[str]
    criticality: str | None
    cost_profile: str | None
    llm_provider: str | None
    llm_model: str | None
    prompt_content: str | None
    skills_content: str | None
    soul_content: str | None
    limitations: list[str]


@dataclass
class SubAgentConfig:
    """Configuration of a SubAgent used during the run."""
    name: str                        # ScenarioSubAgent, JudgeSubAgent, etc.
    role: str                        # preparation, judgment, diagnostic, assertion
    model: str
    host: str
    system_prompt: str
    max_iters: int


@dataclass
class RunTrace:
    """Complete trace of a test run."""
    run_id: str
    trace_version: str = "1.0"
    started_at: str = ""
    ended_at: str = ""
    total_duration_ms: int = 0

    # Context
    scenario: dict = field(default_factory=dict)
    agent_under_test: dict = field(default_factory=dict)

    # Configuration
    orchestrator_config: dict = field(default_factory=dict)
    subagents_config: list[dict] = field(default_factory=list)

    # Final results
    verdict: str = ""
    score: float = 0.0
    summary: str = ""
    final_output: str = ""
    error: str | None = None

    # Full timeline
    events: list[dict] = field(default_factory=list)

    # Aggregated stats
    stats: dict = field(default_factory=dict)


# ─── Recorder (in-memory, per run_id) ────────────────────────────────────────

_active_traces: dict[str, "TraceRecorder"] = {}
_lock = threading.Lock()


class TraceRecorder:
    """Records all interactions for a single test run.

    Usage:
        recorder = TraceRecorder.start(run_id)
        recorder.set_scenario(...)
        recorder.set_agent_under_test(...)
        recorder.record_subagent_call(...)
        recorder.record_target_agent_run(...)
        recorder.finalize(verdict, score)
        recorder.save()
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.trace = RunTrace(run_id=run_id)
        self._t0 = time.time()
        self.trace.started_at = datetime.now(timezone.utc).isoformat()

    # ── Factory / lookup ─────────────────────────────────────────────────

    @classmethod
    def start(cls, run_id: str) -> "TraceRecorder":
        with _lock:
            recorder = cls(run_id)
            _active_traces[run_id] = recorder
            return recorder

    @classmethod
    def get(cls, run_id: str) -> "TraceRecorder | None":
        with _lock:
            return _active_traces.get(run_id)

    @classmethod
    def remove(cls, run_id: str) -> None:
        with _lock:
            _active_traces.pop(run_id, None)

    # ── Elapsed ──────────────────────────────────────────────────────────

    def _elapsed_ms(self) -> int:
        return int((time.time() - self._t0) * 1000)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Setters for context ──────────────────────────────────────────────

    def set_scenario(self, scenario_obj) -> None:
        """scenario_obj = TestScenario ORM model."""
        self.trace.scenario = {
            "scenario_id": scenario_obj.id,
            "name": scenario_obj.name,
            "description": scenario_obj.description,
            "input_prompt": scenario_obj.input_prompt,
            "input_payload": scenario_obj.input_payload,
            "expected_tools": scenario_obj.expected_tools or [],
            "allowed_tools": scenario_obj.allowed_tools or [],
            "assertions": scenario_obj.assertions or [],
            "tags": scenario_obj.tags or [],
            "timeout_seconds": scenario_obj.timeout_seconds,
            "max_iterations": scenario_obj.max_iterations,
        }

    def set_agent_under_test(self, agent_def) -> None:
        """agent_def = AgentDefinition ORM model."""
        self.trace.agent_under_test = {
            "agent_id": agent_def.id,
            "agent_name": agent_def.name,
            "agent_version": agent_def.version,
            "status": agent_def.status,
            "family_id": agent_def.family_id,
            "purpose": agent_def.purpose,
            "description": agent_def.description,
            "skill_ids": getattr(agent_def, "skill_ids", None) or [],
            "allowed_mcps": agent_def.allowed_mcps or [],
            "forbidden_effects": agent_def.forbidden_effects or [],
            "limitations": agent_def.limitations or [],
            "criticality": agent_def.criticality,
            "cost_profile": agent_def.cost_profile,
            "llm_provider": agent_def.llm_provider,
            "llm_model": agent_def.llm_model,
            "prompt_content": _safe_truncate(agent_def.prompt_content),
            "skills_content": _safe_truncate(agent_def.skills_content),
            "soul_content": _safe_truncate(agent_def.soul_content),
            "prompt_ref": agent_def.prompt_ref,
            "skills_ref": agent_def.skills_ref,
            "input_contract_ref": agent_def.input_contract_ref,
            "output_contract_ref": agent_def.output_contract_ref,
        }

    def set_orchestrator_config(self, model: str, host: str, system_prompt: str, max_iters: int) -> None:
        self.trace.orchestrator_config = {
            "model": model,
            "host": host,
            "system_prompt": _safe_truncate(system_prompt, 5000),
            "max_iters": max_iters,
        }

    def add_subagent_config(self, name: str, role: str, model: str,
                            host: str, system_prompt: str, max_iters: int) -> None:
        self.trace.subagents_config.append({
            "name": name,
            "role": role,
            "model": model,
            "host": host,
            "system_prompt": _safe_truncate(system_prompt, 3000),
            "max_iters": max_iters,
        })

    # ── Event recording ──────────────────────────────────────────────────

    def record_event(self, category: str, event_type: str, name: str, data: dict | None = None) -> None:
        event = TraceEvent(
            timestamp=self._now(),
            elapsed_ms=self._elapsed_ms(),
            category=category,
            event_type=event_type,
            name=name,
            data=data or {},
        )
        self.trace.events.append(asdict(event))

    # Specific helpers ---

    def record_orchestrator_start(self, user_message: str) -> None:
        self.record_event("orchestrator", "start", "OrchestratorAgent", {
            "user_message": _safe_truncate(user_message, 5000),
        })

    def record_orchestrator_tool_call(self, tool_name: str, tool_input: dict) -> None:
        self.record_event("orchestrator", "tool_call", tool_name, {
            "input": _safe_truncate(json.dumps(tool_input) if not isinstance(tool_input, str) else tool_input, 5000),
        })

    def record_orchestrator_tool_result(self, tool_name: str, result: str, duration_ms: int) -> None:
        self.record_event("orchestrator", "tool_result", tool_name, {
            "result": _safe_truncate(result, 10000),
            "duration_ms": duration_ms,
        })

    def record_subagent_call(self, subagent_name: str, role: str, model: str,
                             prompt: str, response: str, duration_ms: int,
                             extracted: dict | None = None) -> None:
        """Record a complete SubAgent LLM call."""
        self.record_event("subagent", "call", subagent_name, {
            "role": role,
            "model": model,
            "prompt": _safe_truncate(prompt, 10000),
            "response": _safe_truncate(response, 20000),
            "response_length": len(response) if response else 0,
            "duration_ms": duration_ms,
            "extracted": extracted or {},
        })

    def record_target_agent_start(self, agent_id: str, input_prompt: str,
                                  model: str, tools: list[str], mcps: list[dict],
                                  skills: list[str], system_prompt: str | None = None) -> None:
        self.record_event("target_agent", "start", agent_id, {
            "input_prompt": _safe_truncate(input_prompt, 10000),
            "model": model,
            "available_tools": tools,
            "available_mcps": mcps,
            "skills": skills,
            "system_prompt": _safe_truncate(system_prompt, 10000) if system_prompt else None,
        })

    def record_target_agent_end(self, agent_id: str, status: str, final_output: str,
                                duration_ms: int, iteration_count: int,
                                message_history: list[dict], tool_calls: list[dict],
                                error: str | None = None,
                                connected_mcps: list[dict] | None = None,
                                discovered_tools: list[str] | None = None) -> None:
        self.record_event("target_agent", "end", agent_id, {
            "status": status,
            "final_output": _safe_truncate(final_output, 20000),
            "duration_ms": duration_ms,
            "iteration_count": iteration_count,
            "tool_calls_count": len(tool_calls),
            "tool_calls": [_safe_truncate(json.dumps(tc), 3000) for tc in tool_calls[:20]],
            "message_history": [
                {
                    "role": m.get("role", "unknown"),
                    "name": m.get("name"),
                    "content": _safe_truncate(m.get("content", ""), 5000),
                }
                for m in (message_history or [])[:50]
            ],
            "connected_mcps": connected_mcps or [],
            "discovered_tools": discovered_tools or [],
            "error": error,
        })

    def record_mcp_call(self, mcp_id: str, tool_name: str,
                        input_data: dict, output: str, duration_ms: int | None = None) -> None:
        self.record_event("mcp_call", "call", mcp_id, {
            "tool_name": tool_name,
            "input": _safe_truncate(json.dumps(input_data) if not isinstance(input_data, str) else input_data, 3000),
            "output": _safe_truncate(output, 5000),
            "duration_ms": duration_ms,
        })

    def record_tool_call(self, tool_name: str, input_data: any, output: str,
                         duration_ms: int | None = None) -> None:
        self.record_event("tool_call", "call", tool_name, {
            "input": _safe_truncate(json.dumps(input_data) if not isinstance(input_data, str) else str(input_data), 3000),
            "output": _safe_truncate(output, 5000),
            "duration_ms": duration_ms,
        })

    def record_error(self, category: str, name: str, error: str, traceback: str | None = None) -> None:
        self.record_event(category, "error", name, {
            "error": _safe_truncate(error, 2000),
            "traceback": _safe_truncate(traceback, 5000) if traceback else None,
        })

    def record_lifecycle(self, event: str, data: dict | None = None) -> None:
        """Lifecycle events: loaded_scenario, built_orchestrator, etc."""
        self.record_event("lifecycle", event, event, data or {})

    # ── Finalization ─────────────────────────────────────────────────────

    def finalize(self, verdict: str, score: float, summary: str,
                 final_output: str = "", error: str | None = None) -> None:
        self.trace.verdict = verdict
        self.trace.score = score
        self.trace.summary = _safe_truncate(summary, 10000)
        self.trace.final_output = _safe_truncate(final_output, 20000)
        self.trace.error = error
        self.trace.ended_at = self._now()
        self.trace.total_duration_ms = self._elapsed_ms()

        # Compute stats
        events_by_category: dict[str, int] = {}
        subagent_calls: dict[str, int] = {}
        total_llm_time_ms = 0
        for e in self.trace.events:
            events_by_category[e["category"]] = events_by_category.get(e["category"], 0) + 1
            if e["category"] == "subagent" and e["event_type"] == "call":
                name = e["name"]
                subagent_calls[name] = subagent_calls.get(name, 0) + 1
                total_llm_time_ms += e.get("data", {}).get("duration_ms", 0) or 0

        self.trace.stats = {
            "total_events": len(self.trace.events),
            "events_by_category": events_by_category,
            "subagent_calls": subagent_calls,
            "total_llm_time_ms": total_llm_time_ms,
            "run_wall_time_ms": self.trace.total_duration_ms,
        }

    def save(self, output_dir: str | None = None) -> str:
        """Write the trace to a JSON file. Returns the file path."""
        if output_dir is None:
            # Default: /app/storage/debug-scenarios (mounted to ./debug-scenarios on host)
            output_dir = os.environ.get(
                "ORKESTRA_TRACE_DIR",
                "/app/storage/debug-scenarios",
            )

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.run_id}_{ts}.json"
        filepath = Path(output_dir) / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(asdict(self.trace), f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Trace saved: {filepath}")
        except Exception as exc:
            logger.error(f"Failed to save trace {filepath}: {exc}")
            return ""

        return str(filepath)

    def to_dict(self) -> dict:
        return asdict(self.trace)
