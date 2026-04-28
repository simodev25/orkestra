"""Unit tests for async DAG execution behavior."""

import asyncio
import time

from app.services.pipeline_executor import _sanitize_stage_error, execute_pipeline_dag


async def test_stage2_parallelism_timing_envelope():
    pipeline_agent_ids = ["discover", "mobility", "weather", "budget_fit"]

    async def stage_runner(stage: str, _agent_id: str, _prompt: str) -> str:
        if stage == "discover":
            await asyncio.sleep(0.01)
            return "discover-ok"
        if stage == "mobility":
            await asyncio.sleep(0.15)
            return "mobility-ok"
        if stage == "weather":
            await asyncio.sleep(0.12)
            return "weather-ok"
        await asyncio.sleep(0.01)
        return "budget-ok"

    t0 = time.perf_counter()
    results, _ = await execute_pipeline_dag(
        db=None,
        pipeline_agent_ids=pipeline_agent_ids,
        user_message="hello",
        stage_timeout_seconds=1,
        stage_runner=stage_runner,
    )
    elapsed = time.perf_counter() - t0

    assert results["mobility"].status == "completed"
    assert results["weather"].status == "completed"
    # Rough envelope: discover(10ms) + max(stage2=150ms) + budget(10ms) + overhead.
    assert elapsed < 0.30


async def test_timeout_isolation_keeps_weather_and_budget_fit_running():
    pipeline_agent_ids = ["discover", "mobility", "weather", "budget_fit"]
    called: list[str] = []

    async def stage_runner(stage: str, _agent_id: str, _prompt: str) -> str:
        called.append(stage)
        if stage == "mobility":
            await asyncio.sleep(0.06)
            return "too-late"
        await asyncio.sleep(0.01)
        return f"{stage}-ok"

    results, final = await execute_pipeline_dag(
        db=None,
        pipeline_agent_ids=pipeline_agent_ids,
        user_message="hello",
        stage_timeout_seconds=0.02,
        stage_runner=stage_runner,
    )

    assert results["mobility"].status == "failed"
    assert results["weather"].status == "completed"
    assert results["budget_fit"].status == "completed"
    assert "budget_fit" in called
    assert final == "budget_fit-ok"


async def test_stage_agent_ids_are_distinct_for_parallel_stage2():
    pipeline_agent_ids = ["discover_agent", "mobility_agent", "weather_agent", "budget_fit_agent"]
    stage_ids: dict[str, str] = {}

    async def stage_runner(stage: str, agent_id: str, _prompt: str) -> str:
        stage_ids[stage] = agent_id
        return f"{stage}-ok"

    await execute_pipeline_dag(
        db=None,
        pipeline_agent_ids=pipeline_agent_ids,
        user_message="hello",
        stage_timeout_seconds=1,
        stage_runner=stage_runner,
    )

    assert stage_ids["mobility"] == "mobility_agent"
    assert stage_ids["weather"] == "weather_agent"
    assert stage_ids["mobility"] != stage_ids["weather"]


async def test_stage_started_callback_fires_before_stage_result_callback():
    pipeline_agent_ids = ["discover", "mobility", "weather", "budget_fit"]
    observed: list[tuple[str, str]] = []

    async def stage_runner(stage: str, _agent_id: str, _prompt: str) -> str:
        return f"{stage}-ok"

    async def on_stage_started(stage: str, _started_at: str):
        observed.append(("started", stage))

    async def on_stage_result(result):
        observed.append(("result", result.stage))

    await execute_pipeline_dag(
        db=None,
        pipeline_agent_ids=pipeline_agent_ids,
        user_message="hello",
        stage_timeout_seconds=1,
        stage_runner=stage_runner,
        on_stage_started=on_stage_started,
        on_stage_result=on_stage_result,
    )

    for stage in ("discover", "mobility", "weather", "budget_fit"):
        assert observed.index(("started", stage)) < observed.index(("result", stage))


def test_sanitize_stage_error_masks_sensitive_and_timeout_cases():
    assert _sanitize_stage_error(RuntimeError("operation timed out")) == "stage timeout"
    assert _sanitize_stage_error(RuntimeError("Missing API key for upstream")) == "stage failed due to upstream authorization"
    assert _sanitize_stage_error(RuntimeError("unexpected parser failure")) == "stage execution failed"
