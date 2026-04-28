"""Unit tests for in-memory run store + TTL eviction."""

import asyncio
import time

from app.services.pipeline_runner import PipelineRunStore, RunStatus


async def test_completed_run_is_evicted_after_ttl():
    store = PipelineRunStore(ttl_seconds=1, max_runs=10)
    rec = await store.create(agent_id="a1", message="hello")

    await store.update(
        rec.run_id,
        lambda r: (
            setattr(r, "status", RunStatus.COMPLETED),
            setattr(r, "expires_at", time.time() + 0.02),
        ),
    )

    await asyncio.sleep(0.03)
    evicted = await store.evict_expired()
    assert evicted == 1
    assert await store.get(rec.run_id) is None


async def test_non_terminal_run_is_not_evicted_without_expiry():
    store = PipelineRunStore(ttl_seconds=1, max_runs=10)
    rec = await store.create(agent_id="a1", message="hello")
    evicted = await store.evict_expired()
    assert evicted == 0
    assert await store.get(rec.run_id) is not None
