---
change:
  ref: BUG-2
  type: fix
  status: Proposed
  slug: word-test-agent-write-bypass
  title: "Fix: word_test_agent write_doc bypass via missing forbidden_effect"
  owners: [mbensass]
  service: agent-runtime / word-mcp
  labels: [security, agent-policy, bug]
  version_impact: patch
  audience: internal
  security_impact: medium
  risk_level: low
  dependencies:
    internal: [guarded_mcp_executor, word_test_agent, agent-registry]
    external: []
---

# CHANGE SPECIFICATION

> **PURPOSE** — Correct a policy misconfiguration in `word_test_agent` that permitted the agent to invoke the `write_doc` tool on the Word MCP, violating its intended read-only contract. The enforcement infrastructure (`guarded_mcp_executor`) was correct; only the agent definition was defective.

---

## 1. SUMMARY

`word_test_agent` is designed as a read-only agent. Due to three co-located defects in its definition — a missing `"write"` entry in `forbidden_effects`, a prompt rule that explicitly invited `write_doc` calls, and a routing keyword that directed write-intent requests to the agent — the agent could successfully invoke `write_doc` on the Word MCP. This specification captures the corrective fix and the acceptance criteria that must hold after remediation.

---

## 2. CONTEXT

### 2.1 Current State Snapshot

| Artifact | Defective value |
|---|---|
| `forbidden_effects` | `["publish", "approve", "external_act"]` |
| Prompt rule 4 | Invited `write_doc` calls |
| `routing_keywords` | Included `"write_doc"` |
| `purpose` / `description` | Did not reflect read-only scope |

`guarded_mcp_executor` evaluates MCP tool invocations against the agent's `forbidden_effects` list at runtime. If an effect category is absent from that list, the executor allows the call unconditionally.

### 2.2 Pain Points / Gaps

- **GAP-1** — `"write"` effect category absent from `forbidden_effects` → executor never blocks `write_doc`.
- **GAP-2** — Prompt instructs the agent to invoke `write_doc`, creating a behavioural expectation inconsistent with read-only intent.
- **GAP-3** — `routing_keywords` containing `"write_doc"` routes write-intent user requests to a supposedly read-only agent.
- **GAP-4** — Agent metadata (`purpose`, `description`) does not communicate the read-only contract to operators or downstream routing logic.

---

## 3. PROBLEM STATEMENT

A read-only agent (`word_test_agent`) was able to mutate Word documents because its policy definition omitted the `"write"` effect from the enforcement list consumed by `guarded_mcp_executor`. The enforcement mechanism is sound; the agent configuration is not. Left unresolved, this gap undermines the agent-permission model and could allow unintended document mutation in production.

---

## 4. GOALS

1. Ensure `write_doc` invocations by `word_test_agent` are **always blocked** by `guarded_mcp_executor`.
2. Align the agent's prompt, routing keywords, and metadata with its read-only intent.
3. Establish acceptance criteria that can be validated by automated tests.

### 4.1 Success Metrics / KPIs

| Metric | Target |
|---|---|
| `write_doc` calls blocked (denial rate) | 100 % when invoked by `word_test_agent` |
| Regression: read operations unaffected | 0 read-tool regressions |
| Test suite pass rate post-fix | 100 % |

### 4.2 Non-Goals

- Changing the `guarded_mcp_executor` enforcement logic.
- Altering any other agent's permission list.
- Adding new read capabilities to `word_test_agent`.

---

## 5. FUNCTIONAL CAPABILITIES

| ID | Capability | Rationale |
|---|---|---|
| F-1 | `word_test_agent` is enforced read-only at the executor layer | The executor is the authoritative policy gate; the agent definition must express the correct intent. |
| F-2 | `word_test_agent` prompt forbids `write_doc` and returns a structured error when attempted | Behavioural guardrail at the LLM layer, defence-in-depth. |
| F-3 | `word_test_agent` routing keywords exclude write-intent terms | Prevents write-intent requests from being routed to this agent in the first place. |
| F-4 | Agent metadata accurately advertises read-only scope | Allows operators and orchestration logic to reason correctly about agent capabilities. |

### 5.1 Capability Details

**F-1 — Executor-level enforcement**  
`forbidden_effects` for `word_test_agent` MUST include `"write"`. Any MCP tool whose effect is categorised as `write` — including `write_doc` — must be denied, returning a `denied` `MCPInvocation` result.

**F-2 — Prompt-level guardrail**  
Prompt rule 4 (previously inviting `write_doc`) MUST be replaced with an explicit prohibition. When the agent encounters a `write_doc` request it cannot fulfil, it MUST respond with a structured JSON error (e.g. `{"error": "write_doc is not permitted for this agent"}`).

**F-3 — Routing keyword exclusion**  
`routing_keywords` MUST NOT contain `"write_doc"` or any equivalent write-intent term that would cause the router to direct mutation requests to this agent.

**F-4 — Accurate metadata**  
`purpose` and `description` fields MUST describe `word_test_agent` as a read-only agent, with no mention of write capabilities.

---

## 6. USER & SYSTEM FLOWS

### Current (defective) flow
```
User / orchestrator
  → router (matches "write_doc" keyword) → word_test_agent
  → LLM (prompt rule 4: invoke write_doc)
  → guarded_mcp_executor (forbidden_effects has no "write") → ALLOWED
  → Word MCP write_doc → document mutated  ❌
```

### Target (corrected) flow
```
User / orchestrator
  → router ("write_doc" keyword absent) → write-capable agent (or rejection)

  — OR if routed to word_test_agent by other means —

  → word_test_agent LLM (prompt: write_doc forbidden) → JSON error response
  → guarded_mcp_executor (forbidden_effects includes "write") → DENIED  ✅
  → MCPInvocation{status: "denied"} returned to caller
```

---

## 7. SCOPE & BOUNDARIES

### 7.1 In Scope

- `word_test_agent` definition (forbidden_effects, prompt, routing_keywords, purpose, description)
- Automated tests verifying the denial behaviour
- Documentation update for agent policy authoring guidelines

### 7.2 Out of Scope

- [OUT] `guarded_mcp_executor` implementation changes
- [OUT] Other agents' permission lists
- [OUT] Word MCP server-side access controls
- [OUT] UI / API surface changes

### 7.3 Deferred / Maybe-Later

- Generic linting / schema validation of agent definitions to catch missing required effect categories at authoring time (separate work item).

---

## 8. INTERFACES & INTEGRATION CONTRACTS

### 8.1 REST / HTTP Endpoints

None affected.

### 8.2 Events / Messages

| ID | Event | Change |
|---|---|---|
| EVT-1 | `MCPInvocation` result for `write_doc` via `word_test_agent` | Status transitions from `allowed` → `denied` |

### 8.3 Data Model Impact

| ID | Element | Change |
|---|---|---|
| DM-1 | `AgentDefinition.forbidden_effects` (word_test_agent) | Adds `"write"` entry |
| DM-2 | `AgentDefinition.prompt_content` rule 4 | Replaces invite with explicit prohibition |
| DM-3 | `AgentDefinition.routing_keywords` | Removes `"write_doc"` |
| DM-4 | `AgentDefinition.purpose` / `.description` | Updated to read-only wording |

### 8.4 External Integrations

None.

### 8.5 Backward Compatibility

Any caller that previously relied on `word_test_agent` to perform write operations will receive a `denied` response after this fix. This is intentional and correct — such usage was a policy violation, not a supported integration.

---

## 9. NON-FUNCTIONAL REQUIREMENTS (NFRs)

| ID | Requirement | Threshold |
|---|---|---|
| NFR-1 | Denial latency overhead | `guarded_mcp_executor` denial adds ≤ 5 ms vs. baseline allow path |
| NFR-2 | Read-operation availability | Zero regression on existing read-tool invocations (0 new failures) |
| NFR-3 | Test coverage | New denial behaviour covered by ≥ 1 automated unit/integration test |

---

## 10. TELEMETRY & OBSERVABILITY REQUIREMENTS

- Existing `MCPInvocation` audit log MUST record `status: denied`, `agent: word_test_agent`, `tool: write_doc` for blocked calls.
- No new telemetry instrumentation required; existing logging is sufficient.

---

## 11. RISKS & MITIGATIONS

| ID | Risk | Impact | Probability | Mitigation | Residual Risk |
|---|---|---|---|---|---|
| RSK-1 | Other read-only agents have the same omission | H | M | Audit all agent definitions for missing `"write"` in `forbidden_effects` as a follow-up sweep | M |
| RSK-2 | Legitimate callers break when write is denied | L | L | No known legitimate write usage; denial is correct behaviour | L |
| RSK-3 | Prompt change alters unintended agent behaviour | L | L | Change is narrowly scoped to rule 4 only | L |

---

## 12. ASSUMPTIONS

1. `guarded_mcp_executor` correctly maps the `write_doc` tool to the `"write"` effect category.
2. No production workflow legitimately depends on `word_test_agent` performing writes.
3. The agent registry is the single source of truth for agent definitions; no runtime overrides exist.

---

## 13. DEPENDENCIES

| Type | Component | Nature |
|---|---|---|
| Internal | `guarded_mcp_executor` | Must correctly resolve `write_doc` → `"write"` effect (assumed stable) |
| Internal | Agent registry / loader | Must reload agent definition after fix for change to take effect |

---

## 14. OPEN QUESTIONS

| ID | Question | Owner | Due |
|---|---|---|---|
| OQ-1 | Does the effect-to-tool mapping for `write_doc` → `"write"` exist in the executor's registry, or does it need to be added? | @architect | Before merge |
| OQ-2 | Should a schema validation step be added to the agent-creation script to enforce mandatory effect categories? | @pm | Separate work item |

---

## 15. DECISION LOG

| ID | Decision | Rationale | Date |
|---|---|---|---|
| DEC-1 | Fix in agent definition only; do not modify `guarded_mcp_executor` | Executor logic is correct; the defect is in configuration, not enforcement code | 2026-04-24 |
| DEC-2 | Add `"write"` to `forbidden_effects` rather than removing `write_doc` from allowed tools | Effect-based blocking is the intended policy model; tool-level allow-lists are not the pattern used | 2026-04-24 |

---

## 16. AFFECTED COMPONENTS (HIGH-LEVEL)

- **word_test_agent** definition (primary change)
- **guarded_mcp_executor** (no code change; behaviour changes as a downstream effect of F-1)
- **Agent router** (no code change; routing changes as a downstream effect of F-3)
- **Test suite** for agent policy enforcement

---

## 17. ACCEPTANCE CRITERIA

| ID | Criterion |
|---|---|
| AC-F1-1 | **Given** the `word_test_agent` definition, **When** `forbidden_effects` is inspected, **Then** it MUST contain `"write"` |
| AC-F1-2 | **Given** `word_test_agent` attempts to invoke `write_doc`, **When** `guarded_mcp_executor` evaluates the call, **Then** the returned `MCPInvocation` has `status = "denied"` |
| AC-F2-1 | **Given** the `word_test_agent` prompt, **When** rule 4 is inspected, **Then** it MUST NOT invite `write_doc` and MUST include an explicit prohibition |
| AC-F2-2 | **Given** a `write_doc` request reaches the agent LLM, **When** the agent responds, **Then** the response MUST be a structured JSON error indicating the operation is not permitted |
| AC-F3-1 | **Given** the `word_test_agent` definition, **When** `routing_keywords` is inspected, **Then** it MUST NOT contain `"write_doc"` |
| AC-F4-1 | **Given** the `word_test_agent` definition, **When** `purpose` and `description` are inspected, **Then** they MUST describe the agent as read-only with no mention of write capabilities |
| AC-NFR3-1 | **Given** the post-fix test suite, **When** tests run, **Then** at least one test explicitly asserts the `denied` outcome for `write_doc` via `word_test_agent` |

---

## 18. ROLLOUT & CHANGE MANAGEMENT (HIGH-LEVEL)

- Change is a configuration-only fix with no schema migration or deployment dependency.
- Agent definition reloads on service restart; no hot-reload mechanism required.
- Regression test run required before merge.
- No feature flag needed — the fix must be active unconditionally.

---

## 19. DATA MIGRATION / SEEDING (IF APPLICABLE)

Not applicable. No persistent data is affected.

---

## 20. PRIVACY / COMPLIANCE REVIEW

Not applicable. Fix reduces agent capability; no new data access paths introduced.

---

## 21. SECURITY REVIEW HIGHLIGHTS

- This fix closes a privilege-escalation path: a designated read-only agent was able to perform write operations.
- Post-fix, `word_test_agent` is correctly sandboxed to read-only MCP operations.
- Security impact of the original defect: **medium** (internal agent, document mutation, no external data exfiltration).
- Residual risk after fix: **low**.

---

## 22. MAINTENANCE & OPERATIONS IMPACT

- Operators must restart (or hot-reload) the agent service to pick up the updated definition.
- No monitoring threshold changes required.
- Any future agent definitions MUST include all relevant effect categories in `forbidden_effects`; see OQ-2 for a proposed enforcement mechanism.

---

## 23. GLOSSARY

| Term | Definition |
|---|---|
| `forbidden_effects` | List of effect category strings that `guarded_mcp_executor` uses to block MCP tool calls for a given agent |
| `guarded_mcp_executor` | Orkestra middleware component that evaluates and enforces agent-level MCP permission policies |
| `MCPInvocation` | Data structure representing the result of an MCP tool call, including a `status` field (`allowed` / `denied`) |
| `routing_keywords` | Agent definition field used by the request router to match user intent to a specific agent |
| `write_doc` | Word MCP tool that creates or updates a Word document |

---

## 24. APPENDICES

None.

---

## 25. DOCUMENT HISTORY

| Version | Date | Author | Notes |
|---|---|---|---|
| 0.1 | 2026-04-24 | mbensass | Initial draft — Proposed |

---

## AUTHORING GUIDELINES

- All IDs (F-, AC-, NFR-, RSK-, DEC-, OQ-, EVT-, DM-) must be stable and unique within their category.
- Acceptance Criteria must use Given/When/Then and reference at least one F-/NFR- ID.
- NFRs must be quantified.
- Risks must declare Impact and Probability (H/M/L).
- No file paths, implementation tasks, or code-level instructions in this document.

## VALIDATION CHECKLIST

- [x] `change.ref` == `BUG-2`
- [x] `owners` ≥ 1
- [x] `status` == "Proposed"
- [x] Section order matches spec_structure
- [x] All AC entries use Given/When/Then and reference an F-/NFR- ID
- [x] NFRs include measurable thresholds
- [x] Risks include Impact & Probability
- [x] No implementation file paths present
- [x] Only this spec file staged & committed
