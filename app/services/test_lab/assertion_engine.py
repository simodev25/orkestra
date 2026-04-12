# app/services/test_lab/assertion_engine.py
"""Deterministic assertion evaluation."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("orkestra.test_lab.assertions")


def evaluate_assertions(
    assertion_defs: list[dict],
    events: list[dict],
    final_output: str | None,
    duration_ms: int,
    iteration_count: int,
    final_status: str,
) -> list[dict]:
    """Evaluate all assertions deterministically. Returns list of result dicts."""
    results = []
    for adef in assertion_defs:
        atype = adef.get("type", "")
        target = adef.get("target")
        expected = adef.get("expected")
        critical = adef.get("critical", False)

        if atype == "tool_called":
            result = _check_tool_called(events, target)
        elif atype == "tool_not_called":
            result = _check_tool_not_called(events, target)
        elif atype == "output_field_exists":
            result = _check_output_field_exists(final_output, target)
        elif atype == "output_schema_matches":
            result = _check_output_schema(final_output, expected)
        elif atype == "max_duration_ms":
            result = _check_max_duration(duration_ms, int(expected or 0))
        elif atype == "max_iterations":
            result = _check_max_iterations(iteration_count, int(expected or 0))
        elif atype == "final_status_is":
            result = _check_final_status(final_status, expected or "")
        elif atype == "no_tool_failures":
            result = _check_no_tool_failures(events)
        elif atype == "output_contains":
            result = _check_output_contains(final_output, expected)
        else:
            result = {"passed": False, "message": f"Unknown assertion type: {atype}", "actual": None, "details": None}

        results.append({
            "assertion_type": atype,
            "target": target,
            "expected": expected,
            "actual": result.get("actual"),
            "passed": result["passed"],
            "critical": critical,
            "message": result["message"],
            "details": result.get("details"),
        })
    return results


def _check_tool_called(events: list[dict], tool_name: str | None) -> dict:
    called = [e for e in events if e.get("event_type") == "tool_call_completed" and e.get("details", {}).get("tool_name") == tool_name]
    if called:
        return {"passed": True, "message": f"Tool '{tool_name}' was called", "actual": tool_name}
    return {"passed": False, "message": f"Tool '{tool_name}' was NOT called", "actual": None}


def _check_tool_not_called(events: list[dict], tool_name: str | None) -> dict:
    called = [e for e in events if e.get("event_type") in ("tool_call_started", "tool_call_completed") and e.get("details", {}).get("tool_name") == tool_name]
    if not called:
        return {"passed": True, "message": f"Tool '{tool_name}' was correctly not called", "actual": None}
    return {"passed": False, "message": f"Tool '{tool_name}' was called but should not have been", "actual": tool_name}


def _extract_json(output: str) -> str:
    """Strip markdown code fences and return the raw JSON string."""
    stripped = output.strip()
    # ```json ... ``` or ``` ... ```
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # drop first line (```json or ```) and last line (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        return "\n".join(inner).strip()
    return stripped


def _check_output_field_exists(output: str | None, field: str | None) -> dict:
    if not output or not field:
        return {"passed": False, "message": "Output or field not provided", "actual": None}
    try:
        parsed = json.loads(_extract_json(output))
        if field in parsed:
            return {"passed": True, "message": f"Field '{field}' exists in output", "actual": str(parsed[field])[:200]}
        return {"passed": False, "message": f"Field '{field}' missing from output", "actual": None}
    except (json.JSONDecodeError, TypeError):
        return {"passed": False, "message": "Output is not valid JSON", "actual": None}


def _check_output_schema(output: str | None, schema_json: str | None) -> dict:
    if not output:
        return {"passed": False, "message": "No output to validate", "actual": None}
    try:
        parsed = json.loads(_extract_json(output))
        if not schema_json:
            return {"passed": True, "message": "No schema specified, output is valid JSON", "actual": "valid_json"}
        schema = json.loads(schema_json)
        missing = [k for k in schema.get("required", []) if k not in parsed]
        if missing:
            return {"passed": False, "message": f"Missing required fields: {missing}", "actual": json.dumps(list(parsed.keys())), "details": {"missing": missing}}
        return {"passed": True, "message": "Output matches schema", "actual": json.dumps(list(parsed.keys()))}
    except (json.JSONDecodeError, TypeError) as e:
        return {"passed": False, "message": f"Schema validation error: {e}", "actual": None}


def _check_max_duration(actual_ms: int, max_ms: int) -> dict:
    if actual_ms <= max_ms:
        return {"passed": True, "message": f"Duration {actual_ms}ms within limit {max_ms}ms", "actual": str(actual_ms)}
    return {"passed": False, "message": f"Duration {actual_ms}ms exceeds limit {max_ms}ms", "actual": str(actual_ms)}


def _check_max_iterations(actual: int, max_iters: int) -> dict:
    if actual <= max_iters:
        return {"passed": True, "message": f"Iterations {actual} within limit {max_iters}", "actual": str(actual)}
    return {"passed": False, "message": f"Iterations {actual} exceeds limit {max_iters}", "actual": str(actual)}


def _check_final_status(actual_status: str, expected: str) -> dict:
    if actual_status == expected:
        return {"passed": True, "message": f"Final status is '{expected}'", "actual": actual_status}
    return {"passed": False, "message": f"Expected status '{expected}', got '{actual_status}'", "actual": actual_status}


def _check_output_contains(output: str | None, expected: str | None) -> dict:
    if not output:
        return {"passed": False, "message": "No output to check", "actual": None}
    if not expected:
        return {"passed": False, "message": "No expected string specified", "actual": None}
    if expected in output:
        return {"passed": True, "message": f"Output contains '{expected}'", "actual": expected}
    return {"passed": False, "message": f"Output does not contain '{expected}'", "actual": None}


def _check_no_tool_failures(events: list[dict]) -> dict:
    failures = [e for e in events if e.get("event_type") == "tool_call_failed"]
    if not failures:
        return {"passed": True, "message": "No tool failures detected", "actual": "0"}
    names = [e.get("details", {}).get("tool_name", "unknown") for e in failures]
    return {"passed": False, "message": f"{len(failures)} tool failure(s): {names}", "actual": str(len(failures)), "details": {"failed_tools": names}}
