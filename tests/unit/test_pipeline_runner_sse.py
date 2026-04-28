"""Unit tests for pipeline runner SSE serialization and event ordering."""

import json

from app.services.pipeline_runner import PipelineRunner
from app.services.pipeline_executor import StageExecutionResult


async def test_sse_stream_emits_stage_events_and_terminal_event():
    runner = PipelineRunner(ttl_seconds=10, cleanup_interval_seconds=60)
    rec = await runner.create_run(agent_id="a1", message="hello")

    await runner.emit_event(rec.run_id, "stage_started", {"stage": "discover", "ts": "2026-04-27T10:00:00Z"})
    await runner.apply_stage_result(
        rec.run_id,
        StageExecutionResult(
            stage="discover",
            status="completed",
            output="ok",
            started_at="2026-04-27T10:00:00Z",
            completed_at="2026-04-27T10:00:01Z",
            duration_ms=1000,
        ),
    )
    await runner.emit_event(rec.run_id, "run_complete", {"status": "completed", "run_id": rec.run_id})
    await runner.emit_event(rec.run_id, "stream_end", {"run_id": rec.run_id, "ts": "2026-04-27T10:00:02Z"})

    chunks = []
    async for chunk in runner.stream_events(rec.run_id):
        chunks.append(chunk)
        if "event: stream_end" in chunk:
            break

    text = "".join(chunks)
    assert "event: stage_started" in text
    assert "event: stage_completed" in text
    assert text.index("event: stage_started") < text.index("event: stage_completed")
    assert "event: run_complete" in text
    assert "event: stream_end" in text


def test_sse_serializer_format_and_json_payload():
    runner = PipelineRunner()
    payload = {"stage": "weather", "status": "failed", "error": "stage timeout"}
    sse = runner.serialize_sse("stage_failed", payload)
    assert sse.startswith("event: stage_failed\n")
    assert "data: " in sse
    body = sse.split("data: ", 1)[1].strip()
    parsed = json.loads(body)
    assert parsed["stage"] == "weather"
