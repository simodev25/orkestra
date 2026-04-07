# app/services/test_lab/agent_summary.py
"""Agent-level test evaluation — aggregates runs for lifecycle readiness."""

from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_lab import TestRun


async def get_agent_test_summary(db: AsyncSession, agent_id: str) -> dict:
    """Compute agent-level test summary across all runs."""
    runs_q = select(TestRun).where(TestRun.agent_id == agent_id)
    result = await db.execute(runs_q)
    runs = list(result.scalars().all())

    if not runs:
        return {
            "agent_id": agent_id,
            "total_runs": 0,
            "passed_runs": 0,
            "failed_runs": 0,
            "warning_runs": 0,
            "pass_rate": 0.0,
            "average_score": 0.0,
            "last_run_at": None,
            "last_verdict": None,
            "tool_failure_rate": 0.0,
            "timeout_rate": 0.0,
            "average_duration_ms": 0.0,
            "eligible_for_tested": False,
        }

    completed = [r for r in runs if r.status == "completed"]
    passed = [r for r in completed if r.verdict == "passed"]
    warnings = [r for r in completed if r.verdict == "passed_with_warnings"]
    failed = [r for r in completed if r.verdict == "failed"]
    timed_out = [r for r in runs if r.status == "timed_out"]

    total = len(runs)
    pass_rate = len(passed) / total * 100 if total > 0 else 0.0
    scores = [r.score for r in completed if r.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    durations = [r.duration_ms for r in runs if r.duration_ms is not None]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    sorted_runs = sorted(runs, key=lambda r: r.created_at, reverse=True)
    last_run = sorted_runs[0]

    # Eligibility: at least 3 runs, pass rate >= 80%, no recent failures in last 3
    recent_3 = sorted_runs[:3]
    recent_all_pass = all(r.verdict in ("passed", "passed_with_warnings") for r in recent_3 if r.status == "completed")
    eligible = len(completed) >= 3 and pass_rate >= 80.0 and recent_all_pass

    return {
        "agent_id": agent_id,
        "total_runs": total,
        "passed_runs": len(passed),
        "failed_runs": len(failed),
        "warning_runs": len(warnings),
        "pass_rate": round(pass_rate, 1),
        "average_score": round(avg_score, 1),
        "last_run_at": last_run.created_at.isoformat() if last_run.created_at else None,
        "last_verdict": last_run.verdict,
        "tool_failure_rate": 0.0,  # TODO: compute from events
        "timeout_rate": round(len(timed_out) / total * 100, 1) if total > 0 else 0.0,
        "average_duration_ms": round(avg_duration, 0),
        "eligible_for_tested": eligible,
    }
