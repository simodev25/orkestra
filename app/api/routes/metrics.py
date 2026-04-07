"""Prometheus metrics endpoint."""

from fastapi import APIRouter, Response
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

router = APIRouter()

# ── Agent Test Lab metrics ─────────────────────────────────────────────

AGENT_TEST_RUNS = Counter(
    "orkestra_agent_test_runs_total",
    "Total agent test runs",
    ["agent_id", "verdict"],
)

AGENT_TEST_LATENCY = Histogram(
    "orkestra_agent_test_latency_ms",
    "Agent test run latency in milliseconds",
    ["agent_id"],
    buckets=[500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 120000],
)

AGENT_TEST_TOKENS = Counter(
    "orkestra_agent_test_tokens_total",
    "Total tokens consumed by agent test runs",
    ["agent_id", "type"],  # type = input | output
)


@router.get("/metrics")
async def prometheus_metrics():
    """Expose Prometheus metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
