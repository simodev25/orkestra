"""Tests unitaires pour assertion_engine.py — fonctions pures, pas de DB."""

import pytest

from app.services.test_lab.assertion_engine import (
    _check_final_status,
    _check_max_duration,
    _check_max_iterations,
    _check_no_tool_failures,
    _check_output_contains,
    _check_output_field_exists,
    _check_output_schema,
    _check_tool_called,
    _check_tool_not_called,
    _extract_json,
    evaluate_assertions,
)


# ── _extract_json ─────────────────────────────────────────────────────────────


class TestExtractJson:
    def test_plain_json_unchanged(self):
        raw = '{"key": "value"}'
        assert _extract_json(raw) == '{"key": "value"}'

    def test_json_fence_extracted(self):
        raw = '```json\n{"key": "value"}\n```'
        assert _extract_json(raw) == '{"key": "value"}'

    def test_plain_fence_extracted(self):
        raw = '```\n{"key": "value"}\n```'
        assert _extract_json(raw) == '{"key": "value"}'

    def test_unclosed_fence_extracts_from_line1(self):
        raw = '```json\n{"key": "value"}'
        result = _extract_json(raw)
        assert '{"key": "value"}' in result

    def test_strips_whitespace(self):
        raw = '  {"key": "value"}  '
        assert _extract_json(raw) == '{"key": "value"}'

    def test_multiline_json_fence(self):
        raw = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
        result = _extract_json(raw)
        assert '"a": 1' in result
        assert '"b": 2' in result


# ── _check_tool_called ────────────────────────────────────────────────────────


class TestCheckToolCalled:
    def _make_event(self, event_type: str, tool_name: str) -> dict:
        return {"event_type": event_type, "details": {"tool_name": tool_name}}

    def test_tool_found_passes(self):
        events = [self._make_event("tool_call_completed", "search")]
        result = _check_tool_called(events, "search")
        assert result["passed"] is True
        assert result["actual"] == "search"

    def test_tool_not_found_fails(self):
        events = [self._make_event("tool_call_completed", "search")]
        result = _check_tool_called(events, "other_tool")
        assert result["passed"] is False
        assert result["actual"] is None

    def test_empty_events_fails(self):
        result = _check_tool_called([], "search")
        assert result["passed"] is False

    def test_wrong_event_type_ignored(self):
        events = [self._make_event("tool_call_started", "search")]
        result = _check_tool_called(events, "search")
        assert result["passed"] is False  # started, not completed

    def test_none_tool_name(self):
        events = [{"event_type": "tool_call_completed", "details": {"tool_name": None}}]
        result = _check_tool_called(events, None)
        assert result["passed"] is True


# ── _check_tool_not_called ───────────────────────────────────────────────────


class TestCheckToolNotCalled:
    def _make_event(self, event_type: str, tool_name: str) -> dict:
        return {"event_type": event_type, "details": {"tool_name": tool_name}}

    def test_tool_absent_passes(self):
        events = [self._make_event("tool_call_completed", "other")]
        result = _check_tool_not_called(events, "forbidden")
        assert result["passed"] is True

    def test_tool_completed_fails(self):
        events = [self._make_event("tool_call_completed", "forbidden")]
        result = _check_tool_not_called(events, "forbidden")
        assert result["passed"] is False

    def test_tool_started_also_fails(self):
        events = [self._make_event("tool_call_started", "forbidden")]
        result = _check_tool_not_called(events, "forbidden")
        assert result["passed"] is False

    def test_empty_events_passes(self):
        result = _check_tool_not_called([], "forbidden")
        assert result["passed"] is True


# ── _check_output_field_exists ────────────────────────────────────────────────


class TestCheckOutputFieldExists:
    def test_field_present_passes(self):
        result = _check_output_field_exists('{"name": "Alice", "age": 30}', "name")
        assert result["passed"] is True
        assert "Alice" in result["actual"]

    def test_field_absent_fails(self):
        result = _check_output_field_exists('{"name": "Alice"}', "email")
        assert result["passed"] is False

    def test_none_output_fails(self):
        result = _check_output_field_exists(None, "name")
        assert result["passed"] is False

    def test_invalid_json_fails(self):
        result = _check_output_field_exists("not json", "name")
        assert result["passed"] is False

    def test_none_field_fails(self):
        result = _check_output_field_exists('{"name": "Alice"}', None)
        assert result["passed"] is False

    def test_json_fence_handled(self):
        output = '```json\n{"status": "ok"}\n```'
        result = _check_output_field_exists(output, "status")
        assert result["passed"] is True


# ── _check_output_schema ──────────────────────────────────────────────────────


class TestCheckOutputSchema:
    def test_all_required_fields_present_passes(self):
        output = '{"name": "Alice", "age": 30, "email": "a@b.com"}'
        schema = '{"required": ["name", "age"]}'
        result = _check_output_schema(output, schema)
        assert result["passed"] is True

    def test_missing_required_field_fails(self):
        output = '{"name": "Alice"}'
        schema = '{"required": ["name", "age"]}'
        result = _check_output_schema(output, schema)
        assert result["passed"] is False
        assert "age" in result["message"]

    def test_no_schema_valid_json_passes(self):
        output = '{"anything": true}'
        result = _check_output_schema(output, None)
        assert result["passed"] is True

    def test_none_output_fails(self):
        result = _check_output_schema(None, '{"required": ["x"]}')
        assert result["passed"] is False

    def test_invalid_output_json_fails(self):
        result = _check_output_schema("not json", '{"required": ["x"]}')
        assert result["passed"] is False

    def test_invalid_schema_json_fails(self):
        result = _check_output_schema('{"x": 1}', "not json schema")
        assert result["passed"] is False

    def test_empty_required_list_passes(self):
        output = '{"anything": 1}'
        schema = '{"required": []}'
        result = _check_output_schema(output, schema)
        assert result["passed"] is True


# ── _check_max_duration ───────────────────────────────────────────────────────


class TestCheckMaxDuration:
    def test_within_limit_passes(self):
        result = _check_max_duration(5000, 10000)
        assert result["passed"] is True

    def test_exactly_at_limit_passes(self):
        result = _check_max_duration(10000, 10000)
        assert result["passed"] is True

    def test_over_limit_fails(self):
        result = _check_max_duration(10001, 10000)
        assert result["passed"] is False
        assert "10001ms" in result["message"]

    def test_zero_limit(self):
        result = _check_max_duration(1, 0)
        assert result["passed"] is False


# ── _check_max_iterations ─────────────────────────────────────────────────────


class TestCheckMaxIterations:
    def test_within_limit_passes(self):
        result = _check_max_iterations(3, 5)
        assert result["passed"] is True

    def test_exactly_at_limit_passes(self):
        result = _check_max_iterations(5, 5)
        assert result["passed"] is True

    def test_over_limit_fails(self):
        result = _check_max_iterations(6, 5)
        assert result["passed"] is False

    def test_zero_iterations_passes(self):
        result = _check_max_iterations(0, 5)
        assert result["passed"] is True


# ── _check_final_status ───────────────────────────────────────────────────────


class TestCheckFinalStatus:
    def test_matching_status_passes(self):
        result = _check_final_status("completed", "completed")
        assert result["passed"] is True

    def test_different_status_fails(self):
        result = _check_final_status("failed", "completed")
        assert result["passed"] is False
        assert "failed" in result["message"]

    def test_empty_both_passes(self):
        result = _check_final_status("", "")
        assert result["passed"] is True


# ── _check_output_contains ────────────────────────────────────────────────────


class TestCheckOutputContains:
    def test_string_found_passes(self):
        result = _check_output_contains("The answer is 42", "42")
        assert result["passed"] is True

    def test_string_not_found_fails(self):
        result = _check_output_contains("The answer is 42", "99")
        assert result["passed"] is False

    def test_none_output_fails(self):
        result = _check_output_contains(None, "42")
        assert result["passed"] is False

    def test_none_expected_fails(self):
        result = _check_output_contains("some output", None)
        assert result["passed"] is False

    def test_empty_output_fails(self):
        result = _check_output_contains("", "something")
        assert result["passed"] is False


# ── _check_no_tool_failures ───────────────────────────────────────────────────


class TestCheckNoToolFailures:
    def test_no_failures_passes(self):
        events = [
            {"event_type": "tool_call_completed", "details": {"tool_name": "search"}},
        ]
        result = _check_no_tool_failures(events)
        assert result["passed"] is True
        assert result["actual"] == "0"

    def test_one_failure_fails(self):
        events = [
            {"event_type": "tool_call_failed", "details": {"tool_name": "search"}},
        ]
        result = _check_no_tool_failures(events)
        assert result["passed"] is False
        assert "1" in result["message"]
        assert "search" in result["message"]

    def test_multiple_failures_reported(self):
        events = [
            {"event_type": "tool_call_failed", "details": {"tool_name": "search"}},
            {"event_type": "tool_call_failed", "details": {"tool_name": "database"}},
        ]
        result = _check_no_tool_failures(events)
        assert result["passed"] is False
        assert "2" in result["message"]

    def test_empty_events_passes(self):
        result = _check_no_tool_failures([])
        assert result["passed"] is True


# ── evaluate_assertions (orchestration) ──────────────────────────────────────


class TestEvaluateAssertions:
    def test_empty_list_returns_empty(self):
        results = evaluate_assertions([], [], None, 0, 0, "completed")
        assert results == []

    def test_unknown_type_fails(self):
        defs = [{"type": "nonexistent_type", "target": None, "expected": None, "critical": False}]
        results = evaluate_assertions(defs, [], None, 0, 0, "completed")
        assert len(results) == 1
        assert results[0]["passed"] is False
        assert "Unknown assertion type" in results[0]["message"]

    def test_tool_called_assertion_passes(self):
        events = [{"event_type": "tool_call_completed", "details": {"tool_name": "search"}}]
        defs = [{"type": "tool_called", "target": "search", "expected": None, "critical": False}]
        results = evaluate_assertions(defs, events, None, 0, 0, "completed")
        assert results[0]["passed"] is True

    def test_critical_flag_preserved(self):
        defs = [{"type": "tool_called", "target": "missing", "expected": None, "critical": True}]
        results = evaluate_assertions(defs, [], None, 0, 0, "completed")
        assert results[0]["critical"] is True
        assert results[0]["passed"] is False

    def test_multiple_assertions_evaluated(self):
        defs = [
            {"type": "final_status_is", "target": None, "expected": "completed", "critical": False},
            {"type": "max_duration_ms", "target": None, "expected": "5000", "critical": False},
        ]
        results = evaluate_assertions(defs, [], None, 1000, 0, "completed")
        assert len(results) == 2
        assert results[0]["passed"] is True  # status matches
        assert results[1]["passed"] is True  # 1000ms < 5000ms

    def test_max_duration_fails_when_over(self):
        defs = [{"type": "max_duration_ms", "target": None, "expected": "1000", "critical": False}]
        results = evaluate_assertions(defs, [], None, 2000, 0, "completed")
        assert results[0]["passed"] is False

    def test_result_structure_complete(self):
        defs = [{"type": "final_status_is", "target": None, "expected": "completed", "critical": False}]
        results = evaluate_assertions(defs, [], None, 0, 0, "completed")
        r = results[0]
        assert "assertion_type" in r
        assert "target" in r
        assert "expected" in r
        assert "actual" in r
        assert "passed" in r
        assert "critical" in r
        assert "message" in r
        assert "details" in r
