"""Tests unitaires pour diagnostic_engine.py — fonctions pures, pas de DB."""

import pytest

from app.services.test_lab.diagnostic_engine import generate_diagnostics


def _call(
    events=None,
    assertions=None,
    expected_tools=None,
    duration_ms=1000,
    iteration_count=1,
    max_iterations=10,
    timeout_seconds=60,
    final_output=None,
):
    return generate_diagnostics(
        events=events or [],
        assertions=assertions or [],
        expected_tools=expected_tools,
        duration_ms=duration_ms,
        iteration_count=iteration_count,
        max_iterations=max_iterations,
        timeout_seconds=timeout_seconds,
        final_output=final_output,
    )


class TestGenerateDiagnostics:
    def test_no_issues_returns_empty(self):
        findings = _call(final_output='{"ok": true}')
        assert findings == []

    # ── Pattern 1: expected_tool_not_used ──────────────────────────────────

    def test_expected_tool_not_used(self):
        findings = _call(expected_tools=["search"])
        codes = [f["code"] for f in findings]
        assert "expected_tool_not_used" in codes

    def test_expected_tool_used_no_finding(self):
        events = [{"event_type": "tool_call_completed", "details": {"tool_name": "search"}}]
        findings = _call(events=events, expected_tools=["search"])
        codes = [f["code"] for f in findings]
        assert "expected_tool_not_used" not in codes

    def test_expected_tools_none_skipped(self):
        findings = _call(expected_tools=None)
        codes = [f["code"] for f in findings]
        assert "expected_tool_not_used" not in codes

    def test_expected_tools_empty_list_skipped(self):
        findings = _call(expected_tools=[])
        codes = [f["code"] for f in findings]
        assert "expected_tool_not_used" not in codes

    def test_expected_tool_finding_contains_evidence(self):
        findings = _call(expected_tools=["missing_tool"])
        finding = next(f for f in findings if f["code"] == "expected_tool_not_used")
        assert "missing_tool" in finding["evidence"]["expected"]
        assert isinstance(finding["evidence"]["used_tools"], list)

    # ── Pattern 2: tool_failure_detected ──────────────────────────────────

    def test_tool_failure_detected(self):
        events = [{"event_type": "tool_call_failed", "details": {"tool_name": "db"}}]
        findings = _call(events=events)
        codes = [f["code"] for f in findings]
        assert "tool_failure_detected" in codes

    def test_tool_failure_finding_contains_tool_name(self):
        events = [{"event_type": "tool_call_failed", "details": {"tool_name": "mydb"}}]
        findings = _call(events=events)
        finding = next(f for f in findings if f["code"] == "tool_failure_detected")
        assert "mydb" in finding["message"]
        assert finding["severity"] == "error"

    def test_multiple_tool_failures_multiple_findings(self):
        events = [
            {"event_type": "tool_call_failed", "details": {"tool_name": "tool_a"}},
            {"event_type": "tool_call_failed", "details": {"tool_name": "tool_b"}},
        ]
        findings = _call(events=events)
        failure_codes = [f for f in findings if f["code"] == "tool_failure_detected"]
        assert len(failure_codes) == 2

    # ── Pattern 3: run_timed_out ───────────────────────────────────────────

    def test_run_timed_out(self):
        findings = _call(duration_ms=61_000, timeout_seconds=60)
        codes = [f["code"] for f in findings]
        assert "run_timed_out" in codes

    def test_run_exactly_at_timeout_not_triggered(self):
        # duration_ms > timeout * 1000 (strict greater than)
        findings = _call(duration_ms=60_000, timeout_seconds=60)
        codes = [f["code"] for f in findings]
        assert "run_timed_out" not in codes

    def test_run_within_timeout_not_triggered(self):
        findings = _call(duration_ms=30_000, timeout_seconds=60)
        codes = [f["code"] for f in findings]
        assert "run_timed_out" not in codes

    def test_run_timed_out_severity_critical(self):
        findings = _call(duration_ms=61_000, timeout_seconds=60)
        finding = next(f for f in findings if f["code"] == "run_timed_out")
        assert finding["severity"] == "critical"

    # ── Pattern 4: output_schema_invalid ──────────────────────────────────

    def test_invalid_json_output_triggers_diagnostic(self):
        findings = _call(final_output="not valid JSON at all")
        codes = [f["code"] for f in findings]
        assert "output_schema_invalid" in codes

    def test_valid_json_output_no_diagnostic(self):
        findings = _call(final_output='{"result": "ok"}')
        codes = [f["code"] for f in findings]
        assert "output_schema_invalid" not in codes

    def test_none_output_no_diagnostic(self):
        findings = _call(final_output=None)
        codes = [f["code"] for f in findings]
        assert "output_schema_invalid" not in codes

    # ── Pattern 5: excessive_iterations ──────────────────────────────────

    def test_max_iterations_reached(self):
        findings = _call(iteration_count=10, max_iterations=10)
        codes = [f["code"] for f in findings]
        assert "excessive_iterations" in codes

    def test_one_below_max_not_triggered(self):
        findings = _call(iteration_count=9, max_iterations=10)
        codes = [f["code"] for f in findings]
        assert "excessive_iterations" not in codes

    # ── Pattern 6: slow_final_synthesis ──────────────────────────────────

    def test_slow_last_llm_call(self):
        events = [
            {"event_type": "llm_request_completed", "duration_ms": 31_000},
        ]
        findings = _call(events=events)
        codes = [f["code"] for f in findings]
        assert "slow_final_synthesis" in codes

    def test_fast_last_llm_call_no_diagnostic(self):
        events = [
            {"event_type": "llm_request_completed", "duration_ms": 5_000},
        ]
        findings = _call(events=events)
        codes = [f["code"] for f in findings]
        assert "slow_final_synthesis" not in codes

    def test_exactly_at_30s_not_triggered(self):
        events = [{"event_type": "llm_request_completed", "duration_ms": 30_000}]
        findings = _call(events=events)
        codes = [f["code"] for f in findings]
        assert "slow_final_synthesis" not in codes

    def test_no_llm_events_skipped(self):
        findings = _call(events=[])
        codes = [f["code"] for f in findings]
        assert "slow_final_synthesis" not in codes

    def test_only_last_llm_event_checked(self):
        events = [
            {"event_type": "llm_request_completed", "duration_ms": 35_000},  # old - slow
            {"event_type": "llm_request_completed", "duration_ms": 1_000},   # last - fast
        ]
        findings = _call(events=events)
        codes = [f["code"] for f in findings]
        # Only last is checked → no slow_final_synthesis
        assert "slow_final_synthesis" not in codes

    # ── Pattern 7: no_progress_detected ──────────────────────────────────

    def test_no_iteration_events_and_slow_triggers_diagnostic(self):
        findings = _call(events=[], duration_ms=6_000)
        codes = [f["code"] for f in findings]
        assert "no_progress_detected" in codes

    def test_no_iteration_events_but_fast_run_no_diagnostic(self):
        findings = _call(events=[], duration_ms=3_000)
        codes = [f["code"] for f in findings]
        assert "no_progress_detected" not in codes

    def test_iteration_events_present_no_diagnostic(self):
        events = [
            {"event_type": "agent_iteration_started"},
            {"event_type": "agent_iteration_completed"},
        ]
        findings = _call(events=events, duration_ms=10_000)
        codes = [f["code"] for f in findings]
        assert "no_progress_detected" not in codes

    # ── Multiple diagnostics at once ──────────────────────────────────────

    def test_multiple_issues_all_reported(self):
        events = [{"event_type": "tool_call_failed", "details": {"tool_name": "x"}}]
        findings = _call(
            events=events,
            expected_tools=["missing"],
            duration_ms=61_000,
            timeout_seconds=60,
            final_output="bad output",
            iteration_count=10,
            max_iterations=10,
        )
        codes = {f["code"] for f in findings}
        assert "tool_failure_detected" in codes
        assert "expected_tool_not_used" in codes
        assert "run_timed_out" in codes
        assert "output_schema_invalid" in codes
        assert "excessive_iterations" in codes

    def test_finding_structure_complete(self):
        events = [{"event_type": "tool_call_failed", "details": {"tool_name": "x"}}]
        findings = _call(events=events)
        f = findings[0]
        assert "code" in f
        assert "severity" in f
        assert "message" in f
        assert "probable_causes" in f
        assert "recommendation" in f
        assert "evidence" in f
