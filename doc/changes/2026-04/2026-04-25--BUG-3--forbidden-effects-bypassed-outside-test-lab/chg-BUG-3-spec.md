---
change:
  ref: BUG-3
  type: fix
  status: Proposed
  slug: forbidden-effects-bypassed-outside-test-lab
  title: "Forbidden Effects Enforcement Bypassed Outside Test Lab"
  owners: [mbensass]
  service: agent-factory
  labels: [security, enforcement, agent-factory, forbidden-effects]
  version_impact: patch
  audience: internal
  security_impact: high
  risk_level: medium
  dependencies:
    internal: [agent-factory, effect-classifier, subagent-executor, test-lab]
    external: []
---

# CHANGE SPECIFICATION

> **PURPOSE**: Define the requirements and acceptance criteria for fixing BUG-3 — `forbidden_effects` enforcement is silently bypassed for all agent execution paths outside of an explicit Test Lab run, exposing agents to tool misuse in production and normal subagent workflows.

---

## 1. SUMMARY

`forbidden_effects` is an agent-level safety contract: it declares which effect categories (e.g., `"write"`, `"delete"`) a given agent must never invoke. This enforcement is entirely absent during normal agent execution (subagent, pipeline, standalone). It only fires when a Test Lab `test_run_id` is present. As a result, agents that are explicitly configured to block write-capable tools operate without any restriction in production, making the `forbidden_effects` field semantically meaningless outside of testing.

This fix removes the `test_run_id` gate from the enforcement condition so that `forbidden_effects` is honored unconditionally whenever it is set on an agent definition, regardless of execution context.

---

## 2. CONTEXT

### 2.1 Current State Snapshot

- **`agent_factory.py`** builds agent tool registries. It contains a conditional block that checks for forbidden effects and strips matching tools from the registry. The condition requires `test_run_id` to be truthy before enforcement is applied.
- **`guarded_mcp_executor.py`** exists as a standalone module providing a `guarded_invoke_mcp()` function. It is never called by any part of the codebase and is effectively dead code.
- **`effect_classifier.py`** classifies tool names into effect categories (e.g., `"write"`, `"read"`). It uses a process-level cache keyed on `tool_name` only. This cache behavior is known but considered a separate, lower-priority concern.
- **Test Lab** is the only execution context that passes a `test_run_id` to `create_agentscope_agent`. All other callers (subagent executor, pipeline runners) omit this parameter.
- **`subagent_executor.py`** calls `create_agentscope_agent` without a `test_run_id`, meaning no forbidden-effects enforcement occurs for subagents.

### 2.2 Pain Points / Gaps

- Agents with `forbidden_effects` configured behave differently in test vs. production, breaking the principle of consistent agent contracts.
- A security boundary intended to prevent tool misuse silently does not apply during production runs.
- The presence of `guarded_mcp_executor.py` as dead code creates confusion about where enforcement actually occurs.
- Engineers cannot trust `forbidden_effects` as a reliable safety mechanism unless they know the Test Lab context is active.

---

## 3. PROBLEM STATEMENT

The `forbidden_effects` field on an agent definition is the authoritative declaration that certain tool effect categories must never be accessible to that agent. However, the enforcement of this contract is gated on a runtime condition (`test_run_id` being present) that is only satisfied in Test Lab executions. All production and subagent execution paths skip this enforcement entirely. An agent configured with `forbidden_effects=["write"]` will have write-capable tools fully registered and available during normal operation — the exact behavior the field is supposed to prevent.

---

## 4. GOALS

- **G-1**: `forbidden_effects` enforcement is unconditional — it applies whenever an agent definition declares forbidden effects, in every execution context.
- **G-2**: When enforcement is active outside a Test Lab run, a structured warning is emitted to the application log so operators can audit blocked tool attempts.
- **G-3**: When enforcement is active inside a Test Lab run (with `test_run_id` and `db` available), the existing audit behavior (persisted `MCPInvocation` record + `mcp.denied` event) is preserved.
- **G-4**: Dead code (`guarded_mcp_executor.py`) is removed to eliminate confusion about the enforcement architecture.
- **G-5**: Agents without `forbidden_effects` configured are completely unaffected by this change.

### 4.1 Success Metrics / KPIs

| Metric | Target |
|---|---|
| Enforcement activation rate (non-test-lab) | 100% of agents with `forbidden_effects` set |
| Regression rate on agents without `forbidden_effects` | 0% |
| Test Lab audit trail preservation | 100% — no MCPInvocation records lost |
| Dead code files remaining | 0 (`guarded_mcp_executor.py` deleted) |
| Warning log entries for blocked tools (non-test-lab) | 1 per blocked tool per agent construction |

### 4.2 Non-Goals

- **NG-1**: Fixing or changing the process-level cache in `effect_classifier.py` (tracked separately).
- **NG-2**: Introducing runtime blocking of tool calls after agent construction (enforcement remains at construction time).
- **NG-3**: Creating `MCPInvocation` records for non-Test Lab blocked tools (would produce orphan records without a valid `run_id`).
- **NG-4**: Modifying any caller of `create_agentscope_agent` other than enforcing the contract consistently.
- **NG-5**: Changes to the Test Lab execution path or its audit trail.

---

## 5. FUNCTIONAL CAPABILITIES

| ID | Capability | Rationale |
|---|---|---|
| F-1 | Unconditional forbidden-effects enforcement at agent construction | Ensures `forbidden_effects` is a reliable safety contract in all execution contexts |
| F-2 | Context-aware audit trail on enforcement | Maintains full audit in Test Lab; emits warning log in non-test-lab contexts, avoiding orphan DB records |
| F-3 | Removal of dead enforcement module | Eliminates architectural confusion; establishes `agent_factory` as the single enforcement point |

### 5.1 Capability Details

**F-1 — Unconditional forbidden-effects enforcement**
The enforcement condition in `agent_factory` must evaluate to true based solely on whether `agent_def.forbidden_effects` is non-empty. The presence or absence of a `test_run_id` must not affect whether tools matching forbidden effect categories are excluded from the agent's registered toolkit.

**F-2 — Context-aware audit trail**
When a tool is excluded due to a forbidden effect:
- If `test_run_id` and `db` are both available: persist an `MCPInvocation` record and emit the `mcp.denied` event (unchanged behavior).
- Otherwise: emit a structured warning log entry identifying the agent, the tool name, and the matched forbidden effect category.

**F-3 — Dead code removal**
`guarded_mcp_executor.py` is removed from the codebase. No imports reference this module, so no import updates are required. Post-removal, `agent_factory` is the sole location where forbidden-effects enforcement logic resides.

---

## 6. USER & SYSTEM FLOWS

### Flow A — Subagent construction with forbidden effects (fixed behavior)

```
Caller (subagent_executor)
  │
  ├─► create_agentscope_agent(agent_def, db=db, tools=tools)
  │         │
  │         ├─ agent_def.forbidden_effects is set → enforcement active (F-1)
  │         ├─ test_run_id is None
  │         │
  │         ├─ For each tool:
  │         │     classify effect → matches forbidden? → exclude from toolkit
  │         │     log WARNING: "Tool <name> excluded for agent <id>: forbidden effect <category>" (F-2)
  │         │
  │         └─ Return agent with restricted toolkit
  └─► Agent operates without forbidden-effect-matching tools
```

### Flow B — Test Lab construction with forbidden effects (unchanged behavior)

```
Test Lab runner
  │
  ├─► create_agentscope_agent(agent_def, db=db, tools=tools, test_run_id=run_id)
  │         │
  │         ├─ agent_def.forbidden_effects is set → enforcement active (F-1)
  │         ├─ test_run_id and db present → full audit path (F-2)
  │         │
  │         ├─ For each tool:
  │         │     classify effect → matches forbidden? → exclude
  │         │     persist MCPInvocation + emit mcp.denied event
  │         │
  │         └─ Return agent with restricted toolkit
  └─► Test result includes denied-tool records
```

### Flow C — Agent construction without forbidden effects (unchanged)

```
Any caller
  │
  ├─► create_agentscope_agent(agent_def, ...)
  │         │
  │         └─ agent_def.forbidden_effects is empty/None → no enforcement, all tools registered
  └─► Agent operates with full toolkit
```

---

## 7. SCOPE & BOUNDARIES

### 7.1 In Scope

- Enforcement condition in `agent_factory` (removal of `test_run_id` gate)
- Audit branching logic in `agent_factory` (log vs. DB record based on context)
- Deletion of `guarded_mcp_executor.py`

### 7.2 Out of Scope

- `[OUT]` `effect_classifier.py` cache behavior
- `[OUT]` Any caller modifications beyond receiving the corrected enforcement output
- `[OUT]` Test Lab audit trail mechanics
- `[OUT]` New `MCPInvocation` creation for non-test-lab contexts

### 7.3 Deferred / Maybe-Later

- Scope the `EffectClassifier` cache per agent or per execution context to avoid cross-agent cache pollution (low priority, separate ticket)
- Runtime (post-construction) enforcement of forbidden effects for dynamic tool invocations

---

## 8. INTERFACES & INTEGRATION CONTRACTS

### 8.1 REST / HTTP Endpoints

No REST endpoints are introduced or modified by this change.

### 8.2 Events / Messages

| ID | Event | Change |
|---|---|---|
| EVT-1 | `mcp.denied` | Unchanged — still emitted when `test_run_id` + `db` are present |
| EVT-2 | Application warning log | **New** — structured warning emitted when a tool is excluded outside Test Lab context |

EVT-2 log entry structure (informational, not a wire event):
- Level: `WARNING`
- Fields: `agent_id`, `tool_name`, `forbidden_effect`, `execution_context` (e.g., `"subagent"`)

### 8.3 Data Model Impact

| ID | Element | Change |
|---|---|---|
| DM-1 | `MCPInvocation` | No schema change; records continue to be created only when `test_run_id` is present |

No new columns, tables, or migrations are required.

### 8.4 External Integrations

None.

### 8.5 Backward Compatibility

- **Test Lab behavior**: fully preserved (EVT-1, DM-1 unaffected).
- **Agents without `forbidden_effects`**: unaffected; no enforcement runs.
- **Agents with `forbidden_effects` in non-test-lab contexts**: behavior changes from "no enforcement" to "enforcement active." This is the intentional fix. Callers that relied on the bypass (implicitly or explicitly) will now observe tools being excluded. This is a **breaking behavioral fix**, not a regression.

---

## 9. NON-FUNCTIONAL REQUIREMENTS (NFRs)

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Correctness | 100% of agents with non-empty `forbidden_effects` must have matching tools excluded from their toolkit at construction time, regardless of `test_run_id` |
| NFR-2 | Performance | Agent construction latency increase due to this change ≤ 5 ms at p99 (enforcement logic already present; only condition gate removed) |
| NFR-3 | Observability | Every tool exclusion in a non-test-lab context must produce exactly one WARNING log entry with `agent_id`, `tool_name`, and `forbidden_effect` |
| NFR-4 | Data integrity | No `MCPInvocation` records must be created without a valid `test_run_id`; orphan records must remain at 0 |
| NFR-5 | Maintainability | After this change, there must be exactly one location in the codebase where forbidden-effects enforcement logic resides |
| NFR-6 | Test coverage | Unit tests must cover: (a) enforcement without `test_run_id`, (b) enforcement with `test_run_id`, (c) no enforcement when `forbidden_effects` is empty |

---

## 10. TELEMETRY & OBSERVABILITY REQUIREMENTS

- **Log — tool exclusion warning** (EVT-2): emitted at WARNING level whenever a tool is excluded due to a forbidden effect outside Test Lab. Must include structured fields: `agent_id`, `tool_name`, `forbidden_effect`, `context`.
- **Existing telemetry preserved**: `mcp.denied` event and `MCPInvocation` persistence in Test Lab context remain unchanged.
- No new metrics counters or distributed traces are required for this bug fix.

---

## 11. RISKS & MITIGATIONS

| ID | Risk | Impact | Probability | Mitigation | Residual Risk |
|---|---|---|---|---|---|
| RSK-1 | Agents that implicitly depend on the enforcement bypass break in production | H | M | Audit all callers of `create_agentscope_agent` to identify agents with `forbidden_effects`; verify expected tool sets in unit tests before deploying | L |
| RSK-2 | False-positive tool exclusions due to stale `EffectClassifier` cache | M | L | Existing cache behavior unchanged; cache resets on process restart; low-traffic edge case deferred to separate ticket | M |
| RSK-3 | Test Lab audit trail inadvertently broken | H | L | Audit path is branched, not replaced; existing condition `test_run_id and db` is preserved as the inner branch | L |

---

## 12. ASSUMPTIONS

- `guarded_mcp_executor.py` has no callers at the time of deletion (confirmed by static analysis: zero references).
- `create_agentscope_agent` is the only construction path for agents subject to `forbidden_effects`; no parallel factory or builder bypasses it.
- The `EffectClassifier` correctly classifies tool names into effect categories; no misclassification bugs are in scope here.
- Application logging infrastructure is available and reliable in all execution contexts (subagent, pipeline, test lab).

---

## 13. DEPENDENCIES

| Dependency | Type | Notes |
|---|---|---|
| `agent_factory` | Internal | Primary change site; owns enforcement logic post-fix |
| `effect_classifier` | Internal | Consumed by `agent_factory` for tool classification; no changes |
| `subagent_executor` | Internal | Key affected caller; will now receive correctly restricted agent toolkits |
| `test_lab` | Internal | Existing audit trail must be preserved; no changes required |

---

## 14. OPEN QUESTIONS

| ID | Question | Owner | Status |
|---|---|---|---|
| OQ-1 | Are there any other callers of `create_agentscope_agent` beyond `subagent_executor` and Test Lab that pass `test_run_id`? If so, do they expect full audit or log-only? | mbensass | Open |
| OQ-2 | Should the WARNING log for non-test-lab enforcement be rate-limited or deduplicated per agent construction to prevent log flooding? | mbensass | Open |

---

## 15. DECISION LOG

| ID | Decision | Rationale | Date |
|---|---|---|---|
| DEC-1 | Remove `test_run_id` gate from enforcement condition; enforce unconditionally when `forbidden_effects` is set | `forbidden_effects` is a semantic contract, not a test-only hint; enforcement must be universal | 2026-04-25 |
| DEC-2 | Delete `guarded_mcp_executor.py` | Dead code; no callers; keeping it creates false confidence that a parallel enforcement path exists | 2026-04-25 |
| DEC-3 | Log warning (not persist record) for non-test-lab enforcement | Persisting `MCPInvocation` without a `run_id` would create orphan records; logging preserves audit value without data integrity risk | 2026-04-25 |
| DEC-4 | Defer `EffectClassifier` cache scoping to a separate ticket | Low probability of real-world impact; out of scope for this bug fix; introducing cache changes increases risk without necessity | 2026-04-25 |

---

## 16. AFFECTED COMPONENTS (HIGH-LEVEL)

| Component | Nature of Change |
|---|---|
| Agent Factory (`agent_factory`) | Enforcement condition updated; audit branching added |
| Guarded MCP Executor (`guarded_mcp_executor`) | Deleted (dead code) |
| Subagent Executor (`subagent_executor`) | Indirectly affected — will now receive correctly restricted agent toolkits; no direct code changes |
| Test Lab | Indirectly affected — behavior preserved; no direct code changes |
| Application Logs | New WARNING entries emitted for non-test-lab enforcement events |

---

## 17. ACCEPTANCE CRITERIA

**AC-F1-1**: Given an agent definition with `forbidden_effects=["write"]`, when `create_agentscope_agent` is called without a `test_run_id`, then all tools classified under the `"write"` effect are absent from the agent's registered toolkit.
*References*: F-1, NFR-1

**AC-F1-2**: Given an agent definition with `forbidden_effects=["write"]`, when `create_agentscope_agent` is called with a valid `test_run_id` and `db`, then all tools classified under the `"write"` effect are absent from the agent's registered toolkit AND an `MCPInvocation` record is persisted AND an `mcp.denied` event is emitted.
*References*: F-1, F-2, EVT-1, DM-1

**AC-F1-3**: Given an agent definition with an empty or null `forbidden_effects`, when `create_agentscope_agent` is called with or without a `test_run_id`, then all tools are registered and the agent toolkit is unmodified.
*References*: F-1, NFR-1

**AC-F2-1**: Given an agent with `forbidden_effects` set, when a tool is excluded during construction outside a Test Lab context (no `test_run_id`), then exactly one WARNING log entry is emitted containing `agent_id`, `tool_name`, and the matched `forbidden_effect` category.
*References*: F-2, NFR-3, EVT-2

**AC-F2-2**: Given an agent with `forbidden_effects` set, when a tool is excluded during construction outside a Test Lab context, then no `MCPInvocation` record is created.
*References*: F-2, NFR-4, DM-1

**AC-F3-1**: Given the codebase after this change is applied, when searching for `guarded_mcp_executor`, then no file with that name exists and no import referencing it exists.
*References*: F-3, NFR-5

**AC-NFR-2-1**: Given normal agent construction workload, when enforcement is applied (with or without test_run_id), then the p99 latency increase attributable to this change is ≤ 5 ms compared to the pre-fix baseline.
*References*: NFR-2

---

## 18. ROLLOUT & CHANGE MANAGEMENT (HIGH-LEVEL)

- **Deployment strategy**: Standard deploy; no feature flag required. The fix is unconditionally active.
- **Rollback**: Revert the single condition change in `agent_factory`; dead-code deletion (`guarded_mcp_executor.py`) does not require rollback.
- **Pre-deploy validation**: Run full unit and integration test suite. Verify WARNING log entries appear for subagent construction with `forbidden_effects` in a staging environment.
- **Monitoring post-deploy**: Watch application logs for unexpected WARNING volume spikes that may indicate agents with `forbidden_effects` that were previously bypassing enforcement in production.

---

## 19. DATA MIGRATION / SEEDING (IF APPLICABLE)

No data migration or seeding is required. No schema changes. Existing `MCPInvocation` records are unaffected.

---

## 20. PRIVACY / COMPLIANCE REVIEW

No personal data is processed or stored by this change. The new WARNING log entry includes `agent_id`, `tool_name`, and `forbidden_effect` — all internal operational metadata with no PII.

---

## 21. SECURITY REVIEW HIGHLIGHTS

- **Fix closes a security gap**: Without this fix, `forbidden_effects` provides no protection in production. Any agent configured to block write-capable tools could be exploited or misused through non-test-lab execution paths.
- **Post-fix guarantee**: Tool exclusion based on effect classification is unconditional; it cannot be bypassed by omitting a `test_run_id`.
- **No new attack surface introduced**: The change removes a gate; it does not add new endpoints, new data flows, or new external integrations.
- **Audit trail**: Test Lab retains full `MCPInvocation` persistence. Non-test-lab enforcement emits WARNING logs, providing an operator-visible audit trail without database orphan risk.

---

## 22. MAINTENANCE & OPERATIONS IMPACT

- **Reduced confusion**: Deleting `guarded_mcp_executor.py` removes misleading dead code. Engineers will not waste time tracing a non-existent enforcement path.
- **Single enforcement point**: All forbidden-effects logic lives in `agent_factory`. Future changes to enforcement behavior have one location to update.
- **Log volume**: Operators should expect new WARNING log entries for any agent with `forbidden_effects` constructed outside Test Lab. This volume depends on deployment patterns; monitor during initial rollout.

---

## 23. GLOSSARY

| Term | Definition |
|---|---|
| `forbidden_effects` | A list of effect categories (e.g., `"write"`, `"delete"`) declared on an agent definition that the agent must never invoke |
| Effect category | A classification of a tool's action type, determined by `EffectClassifier` (e.g., `"read"`, `"write"`) |
| `MCPInvocation` | A database record that audits a tool invocation event within a Test Lab run |
| `mcp.denied` | An application event emitted when a tool invocation is blocked due to a forbidden effect in a Test Lab context |
| Test Lab | Orkestra's controlled execution environment for agent evaluation; the only context that previously received forbidden-effects enforcement |
| `test_run_id` | An identifier passed to `create_agentscope_agent` to associate agent construction with a Test Lab run |
| Dead code | Code that exists in the repository but is never called or reachable at runtime |

---

## 24. APPENDICES

### Appendix A — Confirmed Code Findings

**Finding 1 — `guarded_mcp_executor.py` is dead code**
`guarded_invoke_mcp()` is defined but never called. There are zero import references to this module in the codebase.

**Finding 2 — Enforcement gate in `agent_factory.py`**
The condition at line 368:
```
if agent_def.forbidden_effects and test_run_id and db:
```
requires `test_run_id` to be truthy. `subagent_executor.py` (line 102) calls `create_agentscope_agent` without this parameter, meaning enforcement never fires for subagent-constructed agents.

**Finding 3 — `EffectClassifier` process-level cache (deferred)**
Cache is keyed on `tool_name` only. A stale or incorrect classification persists for the process lifetime. Acceptable risk for now; deferred to a separate work item.

---

## 25. DOCUMENT HISTORY

| Version | Date | Author | Notes |
|---|---|---|---|
| 0.1 | 2026-04-25 | mbensass | Initial draft — Proposed |

---

## AUTHORING GUIDELINES

- Use `F-`, `API-`, `EVT-`, `DM-`, `NFR-`, `AC-`, `DEC-`, `RSK-`, `OQ-` prefixes for all identifiable items.
- Acceptance Criteria must follow Given/When/Then format and reference at least one ID.
- NFRs must include measurable thresholds.
- Out-of-scope items must begin with `[OUT]`.
- No file paths, implementation tasks, or code-level instructions in this document.

## VALIDATION CHECKLIST

- [x] `change.ref` matches `BUG-3`
- [x] `owners` has at least one entry
- [x] `status` is `Proposed`
- [x] Section order matches `<spec_structure>`
- [x] All ID prefixes are unique within category
- [x] All Acceptance Criteria use Given/When/Then and reference at least one ID
- [x] All NFRs include measurable values
- [x] All Risks include Impact and Probability
- [x] Out-of-scope items begin with `[OUT]`
- [x] No implementation tasks, file paths, or code instructions present
- [x] Only spec file staged and committed
