---
id: chg-BUG-2-test-plan
status: Proposed
created: 2026-04-24T16:05:26Z
last_updated: 2026-04-24T16:05:26Z
owners:
  - mbensass
service: "agent-runtime / word-mcp"
labels:
  - security
  - agent-policy
  - bug
links:
  change_spec: doc/changes/2026-04/2026-04-24--BUG-2--word-test-agent-write-bypass/chg-BUG-2-spec.md
  implementation_plan: null
  testing_strategy: .ai/rules/testing-strategy.md
version_impact: patch
summary: >-
  Validate that word_test_agent is enforced read-only by policy: write_doc is blocked
  by guarded_mcp_executor via forbidden_effects including "write", and the agent
  definition (prompt, routing_keywords, metadata) no longer invites or suggests write_doc.
---

# Test Plan - Fix: word_test_agent write_doc bypass via missing forbidden_effect

## 1. Scope and Objectives

This test plan covers the BUG-2 fix to prevent the read-only `word_test_agent` from invoking the Word MCP `write_doc` tool.

Objectives:

- Prove executor-layer enforcement: `guarded_mcp_executor` denies `write_doc` when the agent forbids the `"write"` effect.
- Validate configuration correctness: `word_test_agent` definition includes `"write"` in `forbidden_effects`.
- Validate defence-in-depth: `word_test_agent` prompt and routing keywords no longer invite or route `write_doc` intent.
- Cover all acceptance criteria (AC-*) from the change specification or explicitly mark TODO.

Out of scope (per spec): changes to `guarded_mcp_executor` logic; modifications to other agents.

## 2. References

- Change spec: `doc/changes/2026-04/2026-04-24--BUG-2--word-test-agent-write-bypass/chg-BUG-2-spec.md`
- Testing strategy: `.ai/rules/testing-strategy.md`

## 3. Coverage Overview

### 3.1 Functional Coverage (F-#, AC-#)

| Requirement | Coverage Status | Covered By |
|---|---:|---|
| F-1 Executor-level enforcement | Covered | TC-WORDTEST-001, TC-WORDTEST-002 |
| AC-F1-1 forbidden_effects contains "write" | Covered | TC-WORDTEST-003 |
| AC-F1-2 write_doc via guarded_mcp_executor returns MCPInvocation status="denied" | Covered | TC-WORDTEST-002 |
| F-2 Prompt-level guardrail | Partially covered | TC-WORDTEST-004, TC-WORDTEST-007 |
| AC-F2-1 prompt rule 4 does not invite write_doc; explicit prohibition present | Covered | TC-WORDTEST-004 |
| AC-F2-2 write_doc request to agent returns structured JSON error | TODO (automation) | TC-WORDTEST-007 (Manual until deterministic harness exists) |
| F-3 Routing keyword exclusion | Covered | TC-WORDTEST-005 |
| AC-F3-1 routing_keywords must not contain "write_doc" | Covered | TC-WORDTEST-005 |
| F-4 Accurate metadata (read-only) | Covered | TC-WORDTEST-006 |
| AC-F4-1 purpose/description describe read-only scope; no write mention | Covered | TC-WORDTEST-006 |
| AC-NFR3-1 at least one automated test asserts denied write_doc via word_test_agent | Covered | TC-WORDTEST-002 |

### 3.2 Interface Coverage (API-#, EVT-#, DM-#)

| Interface ID | What changes | Coverage Status | Covered By |
|---|---|---:|---|
| EVT-1 MCPInvocation result for write_doc via word_test_agent transitions allowed → denied | Covered | TC-WORDTEST-002 |
| DM-1 AgentDefinition.forbidden_effects adds "write" | Covered | TC-WORDTEST-003 |
| DM-2 AgentDefinition.prompt_content rule 4 replaced with explicit prohibition | Covered | TC-WORDTEST-004, TC-WORDTEST-007 |
| DM-3 AgentDefinition.routing_keywords removes "write_doc" | Covered | TC-WORDTEST-005 |
| DM-4 AgentDefinition.purpose/description updated to read-only wording | Covered | TC-WORDTEST-006 |

### 3.3 Non-Functional Coverage (NFR-#)

| NFR | Coverage Status | Covered By |
|---|---:|---|
| NFR-1 Denial latency overhead ≤ 5 ms vs baseline allow path | TODO (measurement) | TC-WORDTEST-009 (Manual performance check) |
| NFR-2 Zero regression on existing read-tool invocations | TODO (define read-tool set) | TC-WORDTEST-008 |
| NFR-3 Denial behaviour covered by ≥ 1 automated unit/integration test | Covered | TC-WORDTEST-002 |

## 4. Test Types and Layers

Aligned to `.ai/rules/testing-strategy.md`:

- **Unit tests (pytest)**: primary coverage for effect classification and executor denial logic; mock MCP invocation.
- **Static/config tests (pytest, no external services)**: validate agent definition content (forbidden_effects, routing keywords, prompt, metadata) from the source that defines `word_test_agent`.
- **Manual checks** (limited): validate the agent response format for prohibited write requests and perform the NFR-1 latency spot-check.

Test location conventions (strategy):

- `tests/test_*.py` for unit/service-level tests.
- Avoid real external services: mock MCP calls and any LLM provider interactions.

## 5. Test Scenarios

### 5.1 Scenario Index

| TC-ID | Title | Test Type(s) | Automation |
|---|---|---|---|
| TC-WORDTEST-001 | Heuristic effect classification maps write_doc → ["write"] | Unit | Automated |
| TC-WORDTEST-002 | guarded_mcp_executor denies invocation when forbidden_effects includes "write" | Unit | Automated |
| TC-WORDTEST-003 | word_test_agent forbidden_effects contains "write" | Unit (static/config) | Automated |
| TC-WORDTEST-004 | word_test_agent prompt prohibits write_doc (no invitation; explicit prohibition) | Unit (static/config) | Automated |
| TC-WORDTEST-005 | word_test_agent routing_keywords excludes "write_doc" | Unit (static/config) | Automated |
| TC-WORDTEST-006 | word_test_agent metadata is read-only (purpose/description) | Unit (static/config) | Automated |
| TC-WORDTEST-007 | Prohibited write request yields structured JSON error | Manual | Manual |
| TC-WORDTEST-008 | Read operations remain allowed (no regression) | Integration or Unit | TODO |
| TC-WORDTEST-009 | Deny-path latency overhead spot-check (≤ 5 ms) | Performance | Manual |

### 5.2 Scenario Details

#### TC-WORDTEST-001 - Heuristic effect classification maps write_doc → ["write"]

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-1, AC-F1-2
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: Unit tests for agent runtime effect classification (per strategy: `tests/test_*.py`)
**Tags**: @backend

**Preconditions**:

- Effect classification logic is available (e.g., `EffectClassifier._heuristic_classify`).

**Steps**:

1. Call the heuristic classifier with the tool name `"write_doc"`.
2. Capture the returned effect category list.

**Expected Outcome**:

- Returned effects include `"write"` (expected exact list per change request: `["write"]`).

**Notes / Clarifications**:

- This scenario also provides concrete evidence for spec Assumption #1 / OQ-1 (that write_doc maps to the write effect).

#### TC-WORDTEST-002 - guarded_mcp_executor denies invocation when forbidden_effects includes "write"

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-1, AC-F1-2, EVT-1, NFR-3, AC-NFR3-1
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: Unit tests for executor policy gate (per strategy: `tests/test_*.py`)
**Tags**: @backend, @api

**Preconditions**:

- A mocked agent definition can be constructed with `forbidden_effects=["write"]`.
- MCP execution is mockable; no real MCP server calls.

**Steps**:

1. Arrange a mocked agent definition with `forbidden_effects` containing `"write"`.
2. Attempt to invoke the Word MCP tool `write_doc` through `guarded_mcp_executor`.
3. Capture the returned `MCPInvocation` (or equivalent result object).

**Expected Outcome**:

- The invocation result is denied (per spec: `status = "denied"`).
- The denial occurs before any real MCP tool execution is performed.

#### TC-WORDTEST-003 - word_test_agent forbidden_effects contains "write"

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-1, AC-F1-1, DM-1
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: Static/config validation test for agent definition source (per strategy: `tests/test_*.py`)
**Tags**: @backend

**Preconditions**:

- The authoritative `word_test_agent` definition is loadable from the repository (e.g., via the agent creation/registry source).

**Steps**:

1. Load or construct the `word_test_agent` definition as produced by the repository source of truth.
2. Inspect `forbidden_effects`.

**Expected Outcome**:

- `forbidden_effects` contains `"write"`.

#### TC-WORDTEST-004 - word_test_agent prompt prohibits write_doc (no invitation; explicit prohibition)

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-2, AC-F2-1, DM-2
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: Static/config validation test of word_test_agent prompt content (per strategy: `tests/test_*.py`)
**Tags**: @backend

**Preconditions**:

- The prompt content for `word_test_agent` is accessible from the agent definition source.

**Steps**:

1. Load the `word_test_agent` prompt content.
2. Assert that it does **not** instruct/invite calling `write_doc`.
3. Assert that it includes an explicit prohibition against `write_doc` (or writing operations).

**Expected Outcome**:

- Prompt content contains a clear prohibition.
- No text remains that directs the agent to use `write_doc`.

#### TC-WORDTEST-005 - word_test_agent routing_keywords excludes "write_doc"

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-3, AC-F3-1, DM-3
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: Static/config validation test of routing keywords (per strategy: `tests/test_*.py`)
**Tags**: @backend

**Preconditions**:

- The `word_test_agent` routing keywords are accessible from the agent definition source.

**Steps**:

1. Load the `word_test_agent` definition.
2. Inspect `routing_keywords`.

**Expected Outcome**:

- `routing_keywords` does not contain the literal string `"write_doc"`.

#### TC-WORDTEST-006 - word_test_agent metadata is read-only (purpose/description)

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Medium
**Related IDs**: F-4, AC-F4-1, DM-4
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: Static/config validation test of agent metadata (per strategy: `tests/test_*.py`)
**Tags**: @backend

**Preconditions**:

- The `purpose` and `description` fields are accessible from the agent definition source.

**Steps**:

1. Load the `word_test_agent` definition.
2. Inspect `purpose` and `description`.

**Expected Outcome**:

- Both fields communicate that the agent is read-only.
- Neither field claims or suggests write capability.

#### TC-WORDTEST-007 - Prohibited write request yields structured JSON error

**Scenario Type**: Edge Case
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-2, AC-F2-2, DM-2
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Manual validation of agent runtime response formatting
**Tags**: @backend

**Preconditions**:

- A way to run or simulate `word_test_agent` with a write-intent prompt/request (without executing real MCP write).

**Steps**:

1. Submit a request that clearly asks the agent to perform `write_doc`.
2. Observe the agent's response.

**Expected Outcome**:

- The agent returns a structured JSON error indicating `write_doc` is not permitted for this agent.

**Notes / Clarifications**:

- If a deterministic, testable harness is available (e.g., stubbed model that returns the agent message), convert this to an automated test and update this plan.

#### TC-WORDTEST-008 - Read operations remain allowed (no regression)

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: Medium
**Related IDs**: NFR-2
**Test Type(s)**: Integration
**Automation Level**: Semi-automated
**Target Layer / Location**: Tests validating read-tool invocations are still allowed (per strategy: mock MCP calls)
**Tags**: @backend

**Preconditions**:

- Identify the canonical read-tool(s) used by `word_test_agent` (e.g., list/read operations).

**Steps**:

1. Using `word_test_agent` (or an equivalent agent definition with `forbidden_effects` including `"write"`), attempt a representative read-tool invocation.
2. Observe the executor decision and invocation status.

**Expected Outcome**:

- Read-tool invocation is allowed and does not return `status="denied"` due to the write prohibition.

**Notes / Clarifications**:

- TODO: Confirm the specific read-tool names to use for this regression test.

#### TC-WORDTEST-009 - Deny-path latency overhead spot-check (≤ 5 ms)

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: NFR-1
**Test Type(s)**: Performance
**Automation Level**: Manual
**Target Layer / Location**: Local benchmark / timed run (non-CI)
**Tags**: @backend, @perf

**Preconditions**:

- Ability to run a small local measurement comparing allow-path vs deny-path for the same executor call shape.

**Steps**:

1. Measure baseline allow-path latency for a representative MCP invocation (mocked).
2. Measure deny-path latency for `write_doc` when forbidden_effects includes `"write"` (mocked).
3. Compare the overhead.

**Expected Outcome**:

- Deny-path adds ≤ 5 ms vs baseline allow path.

## 6. Environments and Test Data

- **Unit/static tests**: run with `pytest` as per strategy (`--asyncio-mode=auto` when relevant).
- **External dependencies**: none; MCP and LLM interactions must be mocked.
- **Test data**: synthetic tool names and minimal agent definitions; no real Word documents required.

## 7. Automation Plan and Implementation Mapping

Planned automation aligned with repository conventions:

| TC-ID | Planned test file (convention) | Key technique |
|---|---|---|
| TC-WORDTEST-001 | `tests/test_*.py` covering effect classification | Direct call to heuristic classifier; assert returned effect list |
| TC-WORDTEST-002 | `tests/test_*.py` covering executor policy | Mock agent definition; mock MCP invocation; assert denied result |
| TC-WORDTEST-003 | `tests/test_*.py` validating word_test_agent definition | Load agent definition; assert forbidden_effects contains "write" |
| TC-WORDTEST-004 | `tests/test_*.py` validating prompt content | String/content assertions: no invitation + explicit prohibition |
| TC-WORDTEST-005 | `tests/test_*.py` validating routing_keywords | Assert "write_doc" absent |
| TC-WORDTEST-006 | `tests/test_*.py` validating metadata | Assert read-only language; no write claim |
| TC-WORDTEST-007 | Manual checklist step | Run scenario; verify JSON error format |
| TC-WORDTEST-008 | `tests/test_*.py` (or `tests/services/...`) | Mock MCP read-tool invocation; assert allowed |
| TC-WORDTEST-009 | Manual benchmark notes | Local measurement; record numbers in execution log |

## 8. Risks, Assumptions, and Open Questions

**Assumptions (from spec)**:

- The effect mapping classifies `write_doc` as `"write"` (validated by TC-WORDTEST-001; aligns with spec OQ-1).

**Risks**:

- Prompt-level behaviour (AC-F2-2) may be hard to validate deterministically without an LLM harness; keep TC-WORDTEST-007 manual until an automation path exists.
- Read-tool regression coverage (NFR-2) depends on selecting the canonical read-tool(s) for `word_test_agent`.

**Open Questions**:

- OQ-1 (spec): confirm that `write_doc` is categorised as the `"write"` effect in the effect mapping used by the executor.
- Define the minimal set of read-tool invocations that must be proven unaffected for NFR-2 (inputs for TC-WORDTEST-008).

## 9. Plan Revision Log

| Date (UTC) | Author | Change |
|---|---|---|
| 2026-04-24 | mbensass | Initial test plan for BUG-2 (Proposed) |

## 10. Test Execution Log

| Date (UTC) | Executor | Build/Commit | Environment | Scope (TC-IDs) | Result | Notes |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |
