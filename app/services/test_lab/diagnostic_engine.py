# app/services/test_lab/diagnostic_engine.py
"""Pattern-based diagnostic analysis on run events."""

from __future__ import annotations

import logging

logger = logging.getLogger("orkestra.test_lab.diagnostics")


def generate_diagnostics(
    events: list[dict],
    assertions: list[dict],
    expected_tools: list[str] | None,
    duration_ms: int,
    iteration_count: int,
    max_iterations: int,
    timeout_seconds: int,
    final_output: str | None,
) -> list[dict]:
    """Generate deterministic diagnostics from event patterns."""
    findings: list[dict] = []

    # 1. Expected tool not used
    if expected_tools:
        tool_events = [e for e in events if e.get("event_type") == "tool_call_completed"]
        used_tools = {e.get("details", {}).get("tool_name") for e in tool_events}
        for tool in expected_tools:
            if tool not in used_tools:
                findings.append({
                    "code": "expected_tool_not_used",
                    "severity": "warning",
                    "message": f"Expected tool '{tool}' was not called during execution",
                    "probable_causes": [
                        "Agent decided the tool was not needed for this input",
                        "Agent was not aware of the tool availability",
                        "Input prompt did not trigger the expected tool usage path",
                    ],
                    "recommendation": f"Verify that the agent's prompt instructs it to use '{tool}' for this type of input.",
                    "evidence": {"expected": tool, "used_tools": list(used_tools)},
                })

    # 2. Tool failure detected
    tool_failures = [e for e in events if e.get("event_type") == "tool_call_failed"]
    for fail in tool_failures:
        tool_name = fail.get("details", {}).get("tool_name", "unknown")
        findings.append({
            "code": "tool_failure_detected",
            "severity": "error",
            "message": f"Tool '{tool_name}' failed during execution",
            "probable_causes": [
                "Tool server is unavailable or returned an error",
                "Tool input was malformed by the agent",
                "Network timeout connecting to the tool server",
            ],
            "recommendation": f"Check the tool server '{tool_name}' logs and verify connectivity.",
            "evidence": fail.get("details", {}),
        })

    # 3. Run timed out
    if duration_ms > timeout_seconds * 1000:
        findings.append({
            "code": "run_timed_out",
            "severity": "critical",
            "message": f"Run exceeded timeout of {timeout_seconds}s (actual: {duration_ms}ms)",
            "probable_causes": [
                "Agent entered a reasoning loop without converging",
                "Tool calls took too long to respond",
                "LLM inference was slow due to model size or load",
            ],
            "recommendation": "Increase timeout, reduce max_iterations, or check LLM/tool performance.",
            "evidence": {"timeout_seconds": timeout_seconds, "actual_ms": duration_ms},
        })

    # 4. Output schema invalid
    if final_output:
        import json
        try:
            json.loads(final_output)
        except (json.JSONDecodeError, TypeError):
            findings.append({
                "code": "output_schema_invalid",
                "severity": "error",
                "message": "Final output is not valid JSON",
                "probable_causes": [
                    "Agent produced free-text instead of structured output",
                    "Agent's prompt does not enforce JSON output format",
                ],
                "recommendation": "Add output format instructions to the agent's prompt or use structured_model.",
                "evidence": {"output_preview": (final_output or "")[:200]},
            })

    # 5. Excessive iterations
    if iteration_count >= max_iterations:
        findings.append({
            "code": "excessive_iterations",
            "severity": "warning",
            "message": f"Agent used all {max_iterations} iterations",
            "probable_causes": [
                "Task is too complex for the iteration budget",
                "Agent is exploring tools without converging",
                "Agent is stuck in a reasoning loop",
            ],
            "recommendation": "Increase max_iterations or simplify the task.",
            "evidence": {"iterations": iteration_count, "max": max_iterations},
        })

    # 6. Slow final synthesis
    llm_events = [e for e in events if e.get("event_type") == "llm_request_completed" and e.get("duration_ms")]
    if llm_events:
        last_llm = llm_events[-1]
        if last_llm.get("duration_ms", 0) > 30000:
            findings.append({
                "code": "slow_final_synthesis",
                "severity": "warning",
                "message": f"Final LLM call took {last_llm['duration_ms']}ms",
                "probable_causes": [
                    "Large context window with accumulated tool results",
                    "LLM model is slow or overloaded",
                ],
                "recommendation": "Consider a lighter model or reduce context size.",
                "evidence": {"duration_ms": last_llm["duration_ms"]},
            })

    # 7. No progress detected
    iteration_events = [e for e in events if e.get("event_type") in ("agent_iteration_started", "agent_iteration_completed")]
    if len(iteration_events) == 0 and duration_ms > 5000:
        findings.append({
            "code": "no_progress_detected",
            "severity": "error",
            "message": "No agent iteration events detected despite execution time",
            "probable_causes": [
                "Agent creation failed silently",
                "Runtime adapter did not capture events",
                "Agent stalled before first iteration",
            ],
            "recommendation": "Check runtime adapter and agent factory logs.",
            "evidence": {"duration_ms": duration_ms, "iteration_events": 0},
        })

    return findings
