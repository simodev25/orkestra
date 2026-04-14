"""Tests unitaires pour scoring.py — fonctions pures, pas de DB."""

import pytest

from app.services.test_lab.scoring import (
    MAX_SCORE,
    PENALTIES,
    VERDICT_THRESHOLDS,
    compute_score_and_verdict,
)


def _make_assertion(passed: bool, critical: bool = False) -> dict:
    return {"passed": passed, "critical": critical}


def _make_diagnostic(code: str) -> dict:
    return {"code": code}


class TestComputeScoreAndVerdict:
    def test_perfect_score_no_failures(self):
        score, verdict = compute_score_and_verdict([], [])
        assert score == 100.0
        assert verdict == "passed"

    def test_one_non_critical_failure(self):
        assertions = [_make_assertion(passed=False, critical=False)]
        score, verdict = compute_score_and_verdict(assertions, [])
        assert score == MAX_SCORE - PENALTIES["assertion_failed"]
        assert score == 85.0
        assert verdict == "passed"  # 85 >= 80

    def test_one_critical_failure_forces_failed_verdict(self):
        assertions = [_make_assertion(passed=False, critical=True)]
        score, verdict = compute_score_and_verdict(assertions, [])
        # Score = 100 - 50 = 50, but has_critical_failure → "failed"
        assert score == 50.0
        assert verdict == "failed"

    def test_passing_assertions_do_not_penalize(self):
        assertions = [_make_assertion(passed=True), _make_assertion(passed=True)]
        score, verdict = compute_score_and_verdict(assertions, [])
        assert score == 100.0
        assert verdict == "passed"

    def test_score_clamped_to_zero(self):
        # 7 non-critical failures: 7 × 15 = 105 > 100
        assertions = [_make_assertion(passed=False) for _ in range(7)]
        score, verdict = compute_score_and_verdict(assertions, [])
        assert score == 0.0
        assert verdict == "failed"

    def test_threshold_exactly_80_is_passed(self):
        # 1 tool_failure diagnostic = -20 → score = 80
        diagnostics = [_make_diagnostic("tool_failure")]
        score, verdict = compute_score_and_verdict([], diagnostics)
        assert score == 80.0
        assert verdict == "passed"

    def test_score_77_is_passed_with_warnings(self):
        # 1 non-critical (15) + 1 expected_tool_not_used (8) = 23 → 77
        assertions = [_make_assertion(passed=False)]
        diagnostics = [_make_diagnostic("expected_tool_not_used")]
        score, verdict = compute_score_and_verdict(assertions, diagnostics)
        assert score == 77.0
        assert verdict == "passed_with_warnings"

    def test_threshold_exactly_50_is_passed_with_warnings(self):
        # 2 non-critical (30) + 1 tool_failure (20) = 50 → passed_with_warnings
        assertions = [_make_assertion(False), _make_assertion(False)]
        diagnostics = [_make_diagnostic("tool_failure")]
        score, verdict = compute_score_and_verdict(assertions, diagnostics)
        assert score == 50.0
        assert verdict == "passed_with_warnings"

    def test_score_below_50_is_failed(self):
        # 3 non-critical (45) + 1 tool_failure (20) = 65 → 100 - 65 = 35
        assertions = [_make_assertion(False) for _ in range(3)]
        diagnostics = [_make_diagnostic("tool_failure")]
        score, verdict = compute_score_and_verdict(assertions, diagnostics)
        assert score == 35.0
        assert verdict == "failed"

    def test_diagnostic_timeout_penalizes(self):
        diagnostics = [_make_diagnostic("timeout")]
        score, verdict = compute_score_and_verdict([], diagnostics)
        assert score == MAX_SCORE - PENALTIES["timeout"]
        assert score == 70.0
        assert verdict == "passed_with_warnings"

    def test_unknown_diagnostic_code_ignored(self):
        diagnostics = [_make_diagnostic("some_unknown_code")]
        score, verdict = compute_score_and_verdict([], diagnostics)
        assert score == 100.0  # unknown → no penalty

    def test_multiple_diagnostics_cumulative(self):
        diagnostics = [
            _make_diagnostic("tool_failure"),            # -20
            _make_diagnostic("expected_tool_not_used"),  # -8
        ]
        score, verdict = compute_score_and_verdict([], diagnostics)
        assert score == 72.0
        assert verdict == "passed_with_warnings"

    def test_score_rounded_to_one_decimal(self):
        assertions = [_make_assertion(False)]  # -15
        score, _ = compute_score_and_verdict(assertions, [])
        assert score == round(score, 1)

    def test_mixed_assertions_and_diagnostics(self):
        assertions = [
            _make_assertion(True),          # +0
            _make_assertion(False, False),  # -15
        ]
        diagnostics = [_make_diagnostic("slow_synthesis")]  # -5
        score, verdict = compute_score_and_verdict(assertions, diagnostics)
        assert score == 80.0
        assert verdict == "passed"
