---
id: OPS-async-pipeline-troubleshooting
status: Current
version: 0.2.0
last_updated: 2026-04-28
links:
  related_changes:
    - GH-17
  related_features:
    - SPEC-async-pipeline-execution
---

# Operational Guide: Async Pipeline Troubleshooting

## Overview

This guide provides operational procedures for monitoring, troubleshooting, and maintaining the async pipeline execution system.

---

## Monitoring

### Key Metrics

**Run Submission Rate**
- Metric: `orkestra_runs_submitted_total`
- Expected: < 100 runs/min under normal load
- Alert threshold: > 500 runs/min (potential DoS or misconfiguration)

**Run Completion Rate**
- Metric: `orkestra_runs_completed_total`
- Expected: ≥95% completion rate
- Alert threshold: < 80% completion rate over 5 minutes

**SSE Connection Count**
- Metric: `orkestra_sse_active_connections`
- Expected: < 100 concurrent SSE connections
- Alert threshold: > 500 (file descriptor exhaustion risk)

**In-Memory Run Store Size**
- Metric: `orkestra_run_store_size`
- Expected: < 500 active runs
- Alert threshold: > 900 (approaching max_runs guardrail)

**Stage Timeout Rate**
- Metric: `orkestra_stage_timeouts_total` (per stage)
- Expected: < 5% per stage
- Alert threshold: > 20% for any stage over 10 minutes

---

## Structured Log Fields

All stage lifecycle events emit structured logs with the following fields:

```json
{
  "run_id": "uuid",
  "stage": "discover | mobility | weather | budget_fit",
  "status": "started | completed | failed",
  "duration_ms": 1234,
  "ts": "2026-04-28T10:00:00Z",
  "agent_id": "hotel_orchestrateur"
}
```

**Log Aggregation**: Index on `run_id`, `stage`, `status` for fast troubleshooting queries.

---

## Common Issues

### Issue: SSE connection drops mid-run

**Symptoms**:
- Client reports missing events
- SSE stream terminates without `run_complete` event

**Root Causes**:
1. Network timeout (client or proxy)
2. Server-side queue overflow (too many queued events)

**Troubleshooting**:
1. Check client network logs for timeout or disconnect
2. Query run status endpoint: `GET /api/agents/{id}/runs/{run_id}`
3. Verify run completed successfully despite SSE drop
4. Confirm SSE queue was not full (log: `orkestra_sse_queue_full`)

**Resolution**:
- Client-side: Implement reconnect logic and poll status endpoint on disconnect
- Server-side: Increase SSE queue size or implement queue overflow alerting

---

### Issue: Stage timeout cascades

**Symptoms**:
- Multiple stages fail with timeout errors
- Run never reaches `completed` state

**Root Causes**:
1. Upstream service (LLM, MCP) is slow or unresponsive
2. Per-stage timeout too aggressive for current load

**Troubleshooting**:
1. Check stage duration distribution: `grep duration_ms <run_id>`
2. Identify consistently slow stages
3. Verify upstream service health (Ollama, Tavily MCP)

**Resolution**:
- Short-term: Increase per-stage timeout for affected stages
- Long-term: Optimize stage logic or scale upstream services

---

### Issue: Run store memory exhaustion

**Symptoms**:
- Log: `orkestra_run_store_evicted_oldest_terminal`
- Run submission latency increases
- Old completed runs return 404

**Root Causes**:
1. TTL too long for current run rate
2. max_runs guardrail too low
3. High run submission rate without proportional completion rate

**Troubleshooting**:
1. Check current run store size: `orkestra_run_store_size`
2. Calculate run churn rate: (submissions - completions) per minute
3. Verify TTL eviction is functioning: check `expires_at` timestamps

**Resolution**:
- Adjust TTL downward (e.g., 1800s → 900s)
- Increase `max_runs` guardrail if memory permits
- Investigate why runs are not completing (stage hangs, timeout issues)

---

### Issue: Parallel stages not concurrent

**Symptoms**:
- Stage 2 duration ≈ mobility_time + weather_time (sequential, not parallel)
- No concurrency benefit observed

**Root Causes**:
1. Blocking I/O in stage execution (not using async)
2. Event loop starvation (too many concurrent runs)
3. `asyncio.gather` not used or misconfigured

**Troubleshooting**:
1. Examine stage timestamps: `started_at`, `completed_at` for mobility and weather
2. Calculate overlap: if mobility completes before weather starts → sequential
3. Check event loop metrics: `asyncio.active_tasks`

**Resolution**:
- Verify `asyncio.gather` is used for Stage 2 execution
- Ensure stage implementations are fully async (no blocking calls)
- Limit concurrent run count if event loop is saturated

---

### Issue: Agent instance shared across stages

**Symptoms**:
- Intermittent stage failures with unexpected tool state
- Race conditions in agent memory or tool calls

**Root Causes**:
1. Agent factory reusing pre-created agent instance
2. Shared mutable state in closure-captured variables

**Troubleshooting**:
1. Add debug logging to agent factory: log agent instance ID per stage
2. Verify distinct agent IDs for concurrent stages in same run
3. Check for shared mutable data structures in pipeline executor

**Resolution**:
- Ensure `create_agentscope_agent()` is called per-stage (not reused)
- Verify agent cleanup via `close_agentscope_agent_resources()` after stage completion
- Add assertions in tests: `TC-PIPELINE-303` (agent isolation)

---

## Known Limitations (v1)

### Run records lost on restart
**Impact**: In-memory run store; no persistence  
**Mitigation**: Document in user-facing API docs; deferred to v2 (Redis-backed store)

### No run cancellation endpoint
**Impact**: Long-running or hung runs cannot be cancelled by client  
**Mitigation**: Rely on per-stage timeouts; manual cancellation via admin tooling (future)

### SSE queue overflow not handled gracefully
**Impact**: If event emission exceeds queue capacity, events may be dropped  
**Mitigation**: Monitor `orkestra_sse_queue_full` metric; increase queue size if needed

---

## Runbook: Restart Service Without Losing Runs

**Not supported in v1** — run records are ephemeral and lost on restart.

**Workaround**:
1. Drain active runs: stop accepting new submissions (feature flag or maintenance mode)
2. Wait for all active runs to complete (poll `orkestra_runs_active`)
3. Restart service
4. Re-enable run submission

**Future**: Redis-backed run store (v2) will enable graceful restarts.

---

## Debugging Commands

### Retrieve run status
```bash
curl -X GET http://localhost:8000/api/agents/{agent_id}/runs/{run_id}
```

### Tail SSE events for a run
```bash
curl -N -X GET http://localhost:8000/api/agents/{agent_id}/runs/{run_id}/events
```

### Query all logs for a run
```bash
grep "run_id={run_id}" /var/log/orkestra.log | jq .
```

### Check active SSE connections
```bash
lsof -i :8000 | grep ESTABLISHED | wc -l
```

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 0.2.0 | 2026-04-28 | Initial operational guide for async pipeline (GH-17) |
