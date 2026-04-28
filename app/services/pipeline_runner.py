"""Async pipeline runner with in-memory state, TTL, and SSE events.

v1 limitation: run records are stored in memory and are lost on process restart.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.services.pipeline_executor import StageExecutionResult, execute_pipeline_dag

logger = logging.getLogger("orkestra.pipeline_runner")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StageRecord:
    stage_name: str
    status: str = "pending"
    output: str | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int = 0


@dataclass
class RunRecord:
    run_id: str
    agent_id: str
    message: str
    status: RunStatus = RunStatus.PENDING
    stages: dict[str, StageRecord] = field(default_factory=dict)
    result: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    started_at: str | None = None
    completed_at: str | None = None
    expires_at: float | None = None


class PipelineRunStore:
    """In-memory run store with TTL eviction and bounded size guardrail."""

    def __init__(self, ttl_seconds: int = 3600, max_runs: int = 1000):
        self.ttl_seconds = ttl_seconds
        self.max_runs = max_runs
        self._runs: dict[str, RunRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, agent_id: str, message: str) -> RunRecord:
        async with self._lock:
            await self.evict_expired_locked()
            if len(self._runs) >= self.max_runs:
                await self._evict_oldest_terminal_locked(max(1, self.max_runs // 10))

            run_id = str(uuid4())
            record = RunRecord(run_id=run_id, agent_id=agent_id, message=message)
            self._runs[run_id] = record
            return record

    async def get(self, run_id: str) -> RunRecord | None:
        async with self._lock:
            return self._runs.get(run_id)

    async def update(self, run_id: str, updater) -> RunRecord | None:
        async with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return None
            updater(record)
            record.updated_at = _utc_now_iso()
            return record

    async def evict_expired(self) -> int:
        async with self._lock:
            return await self.evict_expired_locked()

    async def evict_expired_locked(self) -> int:
        now = time.time()
        to_delete: list[str] = []
        for run_id, record in self._runs.items():
            if record.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
                if record.expires_at is not None and record.expires_at <= now:
                    to_delete.append(run_id)
        for run_id in to_delete:
            self._runs.pop(run_id, None)
        return len(to_delete)

    async def active_run_ids(self) -> set[str]:
        async with self._lock:
            return set(self._runs.keys())

    async def _evict_oldest_terminal_locked(self, count: int) -> None:
        terminal = [
            rec
            for rec in self._runs.values()
            if rec.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
        ]
        terminal.sort(key=lambda rec: rec.completed_at or rec.updated_at or rec.created_at)
        for rec in terminal[:count]:
            self._runs.pop(rec.run_id, None)


class PipelineRunner:
    """Coordinates async run execution and SSE event subscriptions."""

    def __init__(self, ttl_seconds: int = 3600, cleanup_interval_seconds: int = 60):
        self.store = PipelineRunStore(ttl_seconds=ttl_seconds)
        self.ttl_seconds = ttl_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._run_tasks: dict[str, asyncio.Task] = {}
        self._event_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    async def create_run(self, agent_id: str, message: str) -> RunRecord:
        record = await self.store.create(agent_id=agent_id, message=message)
        async with self._lock:
            self._event_queues[record.run_id] = asyncio.Queue(maxsize=500)
        await self.emit_event(record.run_id, "run_created", {"run_id": record.run_id, "status": record.status.value})
        return record

    async def get_run(self, run_id: str) -> RunRecord | None:
        return await self.store.get(run_id)

    async def start_run(
        self,
        *,
        run_id: str,
        pipeline_agent_ids: list[str],
        session_factory: async_sessionmaker,
        stage_timeout_seconds: int = 90,
        max_iterations: int = 5,
        stage_runner=None,
    ) -> None:
        await self._ensure_cleanup_task()

        placeholder = asyncio.get_running_loop().create_future()
        async with self._lock:
            # Sentinel registration prevents races with cleanup/cancel observers.
            self._run_tasks[run_id] = placeholder

        async def _execute() -> None:
            initial = await self.get_run(run_id)
            user_message = initial.message if initial is not None else ""

            async def _on_stage_started(stage: str, started_at: str) -> None:
                def _mark_started(rec: RunRecord) -> None:
                    stage_record = rec.stages.get(stage)
                    if stage_record is None:
                        stage_record = StageRecord(stage_name=stage)
                        rec.stages[stage] = stage_record
                    stage_record.status = "running"
                    stage_record.started_at = started_at

                await self.store.update(run_id, _mark_started)
                await self.emit_event(run_id, "stage_started", {"stage": stage, "ts": started_at})

            await self.store.update(
                run_id,
                lambda rec: (
                    setattr(rec, "status", RunStatus.RUNNING),
                    setattr(rec, "started_at", _utc_now_iso()),
                ),
            )
            await self.emit_event(run_id, "run_started", {"run_id": run_id})

            t0 = time.time()
            try:
                async def _on_stage_result(stage_res: StageExecutionResult) -> None:
                    await self.apply_stage_result(run_id, stage_res)

                async with session_factory() as db:
                    _, final_result = await execute_pipeline_dag(
                        db=db,
                        pipeline_agent_ids=pipeline_agent_ids,
                        user_message=user_message,
                        stage_timeout_seconds=stage_timeout_seconds,
                        max_iterations=max_iterations,
                        stage_runner=stage_runner,
                        on_stage_started=_on_stage_started,
                        on_stage_result=_on_stage_result,
                    )

                await self.store.update(
                    run_id,
                    lambda rec: (
                        setattr(rec, "status", RunStatus.COMPLETED),
                        setattr(rec, "result", final_result),
                        setattr(rec, "completed_at", _utc_now_iso()),
                        setattr(rec, "expires_at", time.time() + self.ttl_seconds),
                    ),
                )
                duration_ms = int((time.time() - t0) * 1000)
                logger.info("Pipeline run completed", extra={"run_id": run_id, "status": "completed", "duration_ms": duration_ms})
                await self.emit_event(run_id, "run_complete", {"status": "completed", "run_id": run_id})
            except Exception as exc:
                duration_ms = int((time.time() - t0) * 1000)
                logger.exception("Pipeline run failed: %s", exc)
                await self.store.update(
                    run_id,
                    lambda rec: (
                        setattr(rec, "status", RunStatus.FAILED),
                        setattr(rec, "error", "pipeline execution failed"),
                        setattr(rec, "completed_at", _utc_now_iso()),
                        setattr(rec, "expires_at", time.time() + self.ttl_seconds),
                    ),
                )
                logger.info("Pipeline run failed", extra={"run_id": run_id, "status": "failed", "duration_ms": duration_ms})
                await self.emit_event(run_id, "run_complete", {"status": "failed", "run_id": run_id, "error": "pipeline execution failed"})
            finally:
                async with self._lock:
                    self._run_tasks.pop(run_id, None)
                    queue = self._event_queues.get(run_id)
                    if queue is not None:
                        await self._safe_queue_put(
                            queue,
                            {
                                "event": "stream_end",
                                "data": {"run_id": run_id, "ts": _utc_now_iso()},
                            },
                        )

        try:
            task = asyncio.create_task(_execute())
        except Exception:
            async with self._lock:
                if self._run_tasks.get(run_id) is placeholder:
                    self._run_tasks.pop(run_id, None)
            raise

        async with self._lock:
            self._run_tasks[run_id] = task

    async def apply_stage_result(self, run_id: str, stage_res: StageExecutionResult) -> None:
        def _update(rec: RunRecord) -> None:
            stage_record = rec.stages.get(stage_res.stage)
            if stage_record is None:
                stage_record = StageRecord(stage_name=stage_res.stage)
                rec.stages[stage_res.stage] = stage_record
            stage_record.status = stage_res.status
            stage_record.output = stage_res.output
            stage_record.error = stage_res.error
            stage_record.duration_ms = stage_res.duration_ms
            stage_record.started_at = stage_res.started_at
            stage_record.completed_at = stage_res.completed_at

        await self.store.update(run_id, _update)
        if stage_res.status == "completed":
            await self.emit_event(
                run_id,
                "stage_completed",
                {
                    "stage": stage_res.stage,
                    "output": stage_res.output,
                    "ts": stage_res.completed_at or _utc_now_iso(),
                },
            )
        else:
            await self.emit_event(
                run_id,
                "stage_failed",
                {
                    "stage": stage_res.stage,
                    "error": stage_res.error or "stage execution failed",
                    "ts": stage_res.completed_at or _utc_now_iso(),
                },
            )

    async def emit_event(self, run_id: str, event: str, data: dict[str, Any]) -> None:
        payload = {
            "event": event,
            "data": data,
        }
        async with self._lock:
            queue = self._event_queues.get(run_id)
        if queue is not None:
            await self._safe_queue_put(queue, payload)

    async def _safe_queue_put(self, queue: asyncio.Queue[dict[str, Any]], payload: dict[str, Any]) -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            # Drop oldest event and enqueue latest to avoid blocking run lifecycle.
            try:
                _ = queue.get_nowait()
            except Exception:
                pass
            try:
                queue.put_nowait(payload)
            except Exception:
                pass

    async def stream_events(self, run_id: str, heartbeat_seconds: int = 15):
        """Yield SSE-formatted bytes for the given run queue.

        This stream is best-effort live feed. State of truth remains GET status endpoint.
        """

        async with self._lock:
            queue = self._event_queues.get(run_id)

        if queue is None:
            yield self.serialize_sse("run_complete", {"status": "failed", "error": "run not found", "ts": _utc_now_iso()})
            return

        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except asyncio.TimeoutError:
                yield self.serialize_sse("heartbeat", {"run_id": run_id, "ts": _utc_now_iso()})
                continue
            event_name = evt.get("event", "message")
            data = evt.get("data", {})
            yield self.serialize_sse(event_name, data)
            if event_name == "stream_end":
                break

    def serialize_sse(self, event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def _ensure_cleanup_task(self) -> None:
        async with self._lock:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                evicted = await self.store.evict_expired()
                if evicted:
                    logger.info("Evicted expired pipeline runs", extra={"evicted": evicted})

                # Remove queues for runs no longer in store.
                active_ids = await self.store.active_run_ids()
                async with self._lock:
                    stale_run_ids = [rid for rid in self._event_queues.keys() if rid not in active_ids]
                    for rid in stale_run_ids:
                        self._event_queues.pop(rid, None)
                await asyncio.sleep(self.cleanup_interval_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Pipeline runner cleanup loop error: %s", exc)
                await asyncio.sleep(self.cleanup_interval_seconds)


pipeline_runner = PipelineRunner()
