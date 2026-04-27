---
id: SPEC-pipeline-dag-execution
status: Current
version: 0.2.0
last_updated: 2026-04-28
links:
  related_changes:
    - GH-17
  related_features:
    - SPEC-async-pipeline-execution
---

# Pipeline DAG Execution Model

## Overview

The Orkestra pipeline executor implements a Directed Acyclic Graph (DAG) execution model to optimize wall-clock time for multi-stage pipelines. Independent stages execute concurrently, while dependent stages run sequentially.

---

## DAG Topology

```
┌─────────────┐
│  discover   │  Stage 1: Discovery
└──────┬──────┘
       │
  ┌────┴────┐
  ▼         ▼
mobility  weather    Stage 2: Parallel (independent)
  │         │
  └────┬────┘
       │
┌──────▼──────┐
│ budget_fit  │  Stage 3: Budget reconciliation
└─────────────┘
```

---

## Stage Descriptions

### Stage 1: `discover`
**Purpose**: Discover candidate hotels based on user requirements  
**Dependencies**: None (entry point)  
**Output**: List of candidate hotels with metadata

### Stage 2: `mobility` (parallel)
**Purpose**: Analyze accessibility and transport options for each candidate  
**Dependencies**: `discover` output  
**Concurrent With**: `weather`  
**Output**: Mobility/accessibility analysis per candidate

### Stage 2: `weather` (parallel)
**Purpose**: Fetch weather forecast for candidate locations  
**Dependencies**: `discover` output  
**Concurrent With**: `mobility`  
**Output**: Weather forecast per candidate

### Stage 3: `budget_fit`
**Purpose**: Rank candidates by budget fit and synthesize final recommendation  
**Dependencies**: `mobility` + `weather` outputs  
**Output**: Final ranked recommendation

---

## Concurrency Implementation

Stage 2 (`mobility` and `weather`) is executed via `asyncio.gather(return_exceptions=True)`:

```python
mobility_result, weather_result = await asyncio.gather(
    execute_stage("mobility", context),
    execute_stage("weather", context),
    return_exceptions=True
)
```

**Key Properties**:
- Both stages start concurrently (non-blocking)
- Each stage has an isolated timeout via `asyncio.wait_for`
- If one stage fails or times out, the other continues execution
- Exceptions are captured per-stage and do not propagate to siblings

---

## Performance Characteristics

**Sequential Baseline** (hypothetical):
```
Total time = discover_time + mobility_time + weather_time + budget_fit_time
```

**DAG Parallel Model** (actual):
```
Total time = discover_time + max(mobility_time, weather_time) + budget_fit_time
```

**Expected Wall-Clock Reduction**: ≥30% compared to sequential baseline, assuming `mobility_time` and `weather_time` are non-trivial and roughly balanced.

---

## Timeout Isolation

Each stage is wrapped with `asyncio.wait_for(stage_coro, timeout=<stage_timeout>)`. When a stage times out:
- The stage emits a `stage_failed` SSE event
- The timeout exception is captured and does not cancel sibling stages
- Subsequent stages receive partial results (failed stage output = None or error marker)
- The run continues to completion unless a critical dependency is missing

**Example**: If `mobility` times out but `weather` succeeds, Stage 3 (`budget_fit`) still executes using the available `weather` data and partial context from `discover`.

---

## Agent Isolation (Thread Safety)

**Constraint**: AgentScope ReActAgent is not thread-safe and must not be shared across concurrent coroutines.

**Implementation**: Each stage instantiates a dedicated, isolated agent instance:

```python
async def execute_stage(stage_name: str, context: dict):
    agent = await create_agentscope_agent(...)  # Fresh instance per stage
    try:
        result = await agent.run_async(context)
    finally:
        await close_agentscope_agent_resources(agent)  # Cleanup
```

**Guarantee**: No shared mutable state exists between concurrent stages. Each stage operates on its own agent instance with independent memory and tool state.

---

## Error Handling

- **Stage-level failure**: Captured per-stage; does not propagate to siblings or subsequent stages (where possible)
- **Critical failure**: If `discover` (Stage 1) fails, the entire run fails (no candidates to process)
- **Partial success**: If one Stage 2 task fails, the run continues with partial results

---

## Observability

Each stage lifecycle event is logged with structured fields:
- `run_id`: Unique run identifier
- `stage`: Stage name
- `status`: `started`, `completed`, `failed`
- `duration_ms`: Elapsed time in milliseconds
- `ts`: ISO-8601 UTC timestamp

SSE events mirror the same lifecycle for client-side observability.

---

## Future Extensions

- **Dynamic DAG construction**: Allow pipeline definitions to specify custom DAG topologies via configuration
- **Stage retry logic**: Automatic retry for transient failures with exponential backoff
- **Stage result caching**: Cache expensive stage outputs for reuse across similar runs

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 0.2.0 | 2026-04-28 | Initial DAG model: discover → (mobility ∥ weather) → budget_fit (GH-17) |
