# app/services/test_lab/scoring.py
"""Deterministic scoring and verdict computation."""

from __future__ import annotations


MAX_SCORE = 100.0

PENALTIES = {
    "assertion_failed": 15.0,
    "assertion_failed_critical": 50.0,
    "tool_failure": 20.0,
    "timeout": 30.0,
    "output_invalid": 20.0,
    "excessive_iterations": 10.0,
    "slow_synthesis": 5.0,
    "no_progress": 25.0,
    "expected_tool_not_used": 8.0,
}

VERDICT_THRESHOLDS = {
    "passed": 80.0,
    "passed_with_warnings": 50.0,
    # below 50 = failed
}


def compute_score_and_verdict(
    assertions: list[dict],
    diagnostics: list[dict],
) -> tuple[float, str]:
    """Compute score and verdict from assertion results and diagnostics.

    Returns (score, verdict) tuple.
    """
    score = MAX_SCORE
    has_critical_failure = False

    # Penalize assertion failures
    for a in assertions:
        if not a["passed"]:
            if a.get("critical", False):
                score -= PENALTIES["assertion_failed_critical"]
                has_critical_failure = True
            else:
                score -= PENALTIES["assertion_failed"]

    # Penalize diagnostics
    for d in diagnostics:
        code = d["code"]
        if code in PENALTIES:
            score -= PENALTIES[code]

    score = max(0.0, round(score, 1))

    # Verdict
    if has_critical_failure:
        verdict = "failed"
    elif score >= VERDICT_THRESHOLDS["passed"]:
        verdict = "passed"
    elif score >= VERDICT_THRESHOLDS["passed_with_warnings"]:
        verdict = "passed_with_warnings"
    else:
        verdict = "failed"

    return score, verdict
