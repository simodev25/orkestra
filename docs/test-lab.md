# Test Lab — User Reference (v0.2)

The Test Lab is a scenario-based testing system for AI agents. It runs a scenario against a real agent — using a real LLM and real MCP tools — and evaluates the output using multiple LLM sub-agents.

**Key architectural fact**: Unlike a conventional test framework, evaluation in the Test Lab is 100% LLM-driven. The deterministic engines (`scoring.py`, `assertion_engine.py`, `diagnostic_engine.py`) exist in the codebase but are not called in the v0.2 pipeline — all evaluation passes through LLM SubAgents. This means results are non-deterministic: the same scenario can produce different scores on repeated runs.

---

## Actors

| Actor | Role | Implementation | Key config |
|---|---|---|---|
| TargetAgent | The agent under test | `target_agent_runner.py` | Uses agent definition from registry |
| OrchestratorAgent | Coordinates the test run, decides tool call order | `orchestrator_agent.py` ReActAgent | `max_iters=12`, 8 tools |
| ScenarioSubAgent | Prepares a structured test plan from scenario + agent info | ReActAgent | `max_iters=1` (single LLM call) |
| JudgeSubAgent | Evaluates agent output → score (0–100) + verdict + rationale | ReActAgent | `max_iters=1` |
| RobustnessSubAgent | Proposes follow-up tests | ReActAgent | `max_iters=1` |
| PolicySubAgent | Checks governance compliance of agent output | ReActAgent | `max_iters=1` |

All 4 SubAgents are created once at the start of each run and kept alive for the run duration (not recreated per call). Each uses `max_iters=1` — they are effectively single-shot LLM calls, not ReAct loops.

---

## OrchestratorAgent tools (8)

The OrchestratorAgent's Toolkit contains these tools:

1. `get_scenario_context()` — reads TestScenario + AgentDefinition from DB
2. `run_scenario_subagent(task)` — delegates to ScenarioSubAgent
3. `run_target_agent(task)` — executes the real agent via `target_agent_runner.run_target_agent()`
4. `run_judge_subagent(task)` — delegates to JudgeSubAgent; sets run score and verdict
5. `run_robustness_subagent(task)` — delegates to RobustnessSubAgent
6. `run_policy_subagent(task)` — delegates to PolicySubAgent
7. `emit_event(type, data)` — persists events to the `TestRunEvent` table (visible in SSE stream)
8. `finalize_run(verdict, score, summary)` — writes final verdict and score to the TestRun record

---

## TargetAgent execution

The agent under test runs via `target_agent_runner.run_target_agent()`:

1. Load `AgentDefinition` from registry
2. Resolve tools via `agent_factory.get_tools_for_agent()`
3. Create a fresh `ReActAgent` (via `agent_factory.create_agentscope_agent()`)
4. Run with `asyncio.wait_for(react_agent(user_msg), timeout=timeout_seconds)`
5. Extract message history from `react_agent.memory.get_memory()`
6. Return `TargetAgentResult` (status, final_output, duration_ms, iteration_count, message_history, tool_calls, connected_mcps, discovered_tools)

If the agent raises an exception during execution, partial memory is extracted before returning a `failed` result — so the JudgeSubAgent still has something to evaluate.

---

## Execution flow (end-to-end)

```
Client: POST /api/test-lab/scenarios/{id}/run
  → API creates TestRun (status=pending)
  → Enqueues Celery task: run_test_task(run_id, scenario_id)
  → Returns {run_id}

Celery worker:
  → run_orchestrated_test(run_id, scenario_id, db)
  → Creates OrchestratorAgent + 4 SubAgents
  → Sets TestRun status=running

OrchestratorAgent (ReActAgent, max_iters=12):
  → Calls get_scenario_context()           # reads DB
  → Calls run_scenario_subagent(task)      # LLM prepares test plan
  → Calls run_target_agent(task)           # REAL agent execution
  → Calls run_judge_subagent(task)         # LLM evaluates output
  → Calls run_policy_subagent(task)        # LLM checks governance
  → Calls run_robustness_subagent(task)    # LLM proposes follow-ups (optional)
  → Calls finalize_run(verdict, score, summary)

Events streamed in real time via:
  GET /api/test-lab/runs/{id}/stream  (SSE)

Final state: TestRun.status = completed | failed | timeout
             TestRun.verdict = passed | failed | unknown
             TestRun.score = 0.0–100.0
```

---

## Scenario definition fields

| Field | Type | Description |
|---|---|---|
| `id` | str | Auto-generated slug |
| `name` | str | Display name |
| `description` | str | Human-readable purpose |
| `agent_id` | str | ID of the agent to test |
| `input_prompt` | str | Text sent to the agent |
| `assertions` | list | Expected behaviors (see below) |
| `tags` | list | Arbitrary labels |
| `allowed_tools` | list | Tool restriction (null = no restriction) |
| `timeout_seconds` | int | Agent execution timeout (default: 120) |
| `max_iterations` | int | Agent ReAct loop limit (default: 10) |
| `enabled` | bool | Whether this scenario can be run |

Assertion types in the list:

- `output_field_exists` — checks that a named JSON field is present in output
- `output_contains` — checks that a string appears in output
- `no_tool_failures` — checks that no tool calls returned errors
- `max_duration_ms` — checks that execution completed within time limit

---

## Run verdict and score

- **Score**: 0–100, produced by JudgeSubAgent. Represents the LLM judge's assessment of output quality relative to the scenario's criteria.
- **Verdict**: `passed` (score >= threshold) | `failed` (score < threshold or critical assertion failed) | `unknown` (judge could not produce a verdict)
- Assertion results are evaluated by PolicySubAgent and stored in `assertion_results` (list of {assertion_type, passed, message})

Because both score and verdict come from LLMs, they are non-deterministic. The same scenario may produce different results on different runs.

---

## Dynamic configuration

Test Lab behavior is configured via `GET/PUT /api/test-lab/config`. Each SubAgent and the OrchestratorAgent has its own config block:

| Key | Description |
|---|---|
| `orchestrator.model` | Model for OrchestratorAgent |
| `orchestrator.system_prompt` | System prompt for OrchestratorAgent |
| `workers.preparation` | ScenarioSubAgent config |
| `workers.verdict` | JudgeSubAgent config |
| `workers.diagnostic` | RobustnessSubAgent config |
| `workers.assertion` | PolicySubAgent config |

Configuration is stored in the `TestLabConfig` database table.

---

## Interactive chat (post-run)

After a test run completes, you can continue talking with the OrchestratorAgent:

```
POST /api/test-lab/runs/{id}/chat
Body: {"message": "Why did the agent fail the policy check?"}
```

The OrchestratorAgent remembers the run context and can answer follow-up questions.

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | /api/test-lab/scenarios | List scenarios |
| POST | /api/test-lab/scenarios | Create scenario |
| GET | /api/test-lab/scenarios/{id} | Get scenario |
| PATCH | /api/test-lab/scenarios/{id} | Update scenario |
| DELETE | /api/test-lab/scenarios/{id} | Delete scenario |
| POST | /api/test-lab/scenarios/{id}/run | Launch a run |
| GET | /api/test-lab/runs/{id} | Get run state |
| GET | /api/test-lab/runs/{id}/events | Get all events |
| GET | /api/test-lab/runs/{id}/stream | SSE live event stream |
| POST | /api/test-lab/runs/{id}/chat | Chat with OrchestratorAgent |
| GET | /api/test-lab/config | Get SubAgent config |
| PUT | /api/test-lab/config | Update SubAgent config |

---

## Known limitations

- **LLM evaluation is non-deterministic** — the same scenario can score differently on repeated runs
- **Concurrent runs can overload Ollama** — running 3+ scenarios simultaneously can overload a local Ollama instance (Ollama is single-threaded for inference)
- **`tool_failure_rate` not computed** — hardcoded to `0.0` in `agent_summary.py`; does not reflect actual tool failures
- **Deterministic engines not active** — `scoring.py`, `assertion_engine.py`, `diagnostic_engine.py` are present in the codebase but not called in the v0.2 pipeline
- **OrchestratorAgent has tool-call autonomy** — it may skip SubAgent calls if it decides they are unnecessary (it uses a ReAct loop and is not forced to call every tool)
