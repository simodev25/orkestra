"""Service/API tests for /api/agents/{id}/runs endpoints."""

from app.services.pipeline_runner import RunStatus, pipeline_runner


async def _seed_family_and_agent(client, agent_id: str = "hotel_orchestrateur"):
    await client.post(
        "/api/families",
        json={"id": "orchestration", "label": "Orchestration", "description": "Test orchestration family"},
    )
    resp = await client.post(
        "/api/agents",
        json={
            "id": agent_id,
            "name": "Hotel Orchestrateur",
            "family_id": "orchestration",
            "purpose": "Asynchronous hotel pipeline orchestration test purpose",
            "pipeline_agent_ids": ["discover", "mobility", "weather", "budget_fit"],
        },
    )
    assert resp.status_code == 201


async def _seed_second_agent(client, agent_id: str = "hotel_orchestrateur_bis"):
    resp = await client.post(
        "/api/agents",
        json={
            "id": agent_id,
            "name": "Hotel Orchestrateur Bis",
            "family_id": "orchestration",
            "purpose": "Second async orchestration test agent",
            "pipeline_agent_ids": ["discover", "mobility", "weather", "budget_fit"],
        },
    )
    assert resp.status_code == 201


async def test_post_runs_returns_202_and_urls(client, monkeypatch):
    await _seed_family_and_agent(client)

    async def fake_start_run(**kwargs):
        return None

    monkeypatch.setattr(pipeline_runner, "start_run", fake_start_run)

    resp = await client.post(
        "/api/agents/hotel_orchestrateur/runs",
        json={"message": "hello", "timeout_seconds": 30, "max_iterations": 2},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "run_id" in data
    assert data["status_url"].startswith("/api/agents/hotel_orchestrateur/runs/")
    assert data["events_url"].endswith("/events")


async def test_get_run_status_returns_completed_result(client, monkeypatch):
    await _seed_family_and_agent(client)

    async def fake_start_run(*, run_id: str, **kwargs):
        await pipeline_runner.store.update(
            run_id,
            lambda rec: (
                setattr(rec, "status", RunStatus.COMPLETED),
                setattr(rec, "result", "final-result"),
            ),
        )

    monkeypatch.setattr(pipeline_runner, "start_run", fake_start_run)

    create = await client.post("/api/agents/hotel_orchestrateur/runs", json={"message": "hello"})
    run_id = create.json()["run_id"]

    status = await client.get(f"/api/agents/hotel_orchestrateur/runs/{run_id}")
    assert status.status_code == 200
    payload = status.json()
    assert payload["run_id"] == run_id
    assert payload["status"] == "completed"
    assert payload["result"] == "final-result"


async def test_sse_events_streams_stage_and_terminal_events(client, monkeypatch):
    await _seed_family_and_agent(client)

    async def fake_start_run(*, run_id: str, **kwargs):
        await pipeline_runner.emit_event(run_id, "stage_started", {"stage": "discover", "ts": "2026-04-27T10:00:00Z"})
        await pipeline_runner.emit_event(run_id, "stage_completed", {"stage": "discover", "output": "ok", "ts": "2026-04-27T10:00:01Z"})
        await pipeline_runner.emit_event(run_id, "run_complete", {"status": "completed", "run_id": run_id, "ts": "2026-04-27T10:00:02Z"})
        await pipeline_runner.emit_event(run_id, "stream_end", {"run_id": run_id, "ts": "2026-04-27T10:00:03Z"})

    monkeypatch.setattr(pipeline_runner, "start_run", fake_start_run)

    create = await client.post("/api/agents/hotel_orchestrateur/runs", json={"message": "hello"})
    run_id = create.json()["run_id"]

    async with client.stream("GET", f"/api/agents/hotel_orchestrateur/runs/{run_id}/events") as resp:
        assert resp.status_code == 200
        chunks: list[str] = []
        async for chunk in resp.aiter_text():
            chunks.append(chunk)
            if "event: stream_end" in chunk:
                break

    payload = "".join(chunks)
    assert "event: stage_started" in payload
    assert "event: stage_completed" in payload
    assert "event: run_complete" in payload


async def test_runs_endpoints_do_not_invoke_probe_fn(client, monkeypatch):
    await _seed_family_and_agent(client)

    from app.services import agent_factory

    async def boom_probe(*args, **kwargs):
        raise AssertionError("probe_fn should not be called")

    monkeypatch.setattr(agent_factory, "probe_fn", boom_probe, raising=False)

    async def fake_start_run(*, run_id: str, **kwargs):
        await pipeline_runner.emit_event(run_id, "run_complete", {"status": "completed", "run_id": run_id, "ts": "2026-04-27T10:00:02Z"})
        await pipeline_runner.emit_event(run_id, "stream_end", {"run_id": run_id, "ts": "2026-04-27T10:00:03Z"})

    monkeypatch.setattr(pipeline_runner, "start_run", fake_start_run)

    create = await client.post("/api/agents/hotel_orchestrateur/runs", json={"message": "hello"})
    run_id = create.json()["run_id"]

    status = await client.get(f"/api/agents/hotel_orchestrateur/runs/{run_id}")
    assert status.status_code == 200

    async with client.stream("GET", f"/api/agents/hotel_orchestrateur/runs/{run_id}/events") as resp:
        assert resp.status_code == 200
        async for chunk in resp.aiter_text():
            if "event: stream_end" in chunk:
                break


async def test_get_run_status_unknown_run_id_returns_404(client):
    await _seed_family_and_agent(client)

    status = await client.get("/api/agents/hotel_orchestrateur/runs/unknown-run-id")
    assert status.status_code == 404
    assert status.json()["detail"] == "Run not found"


async def test_get_run_events_unknown_run_id_returns_404(client):
    await _seed_family_and_agent(client)

    status = await client.get("/api/agents/hotel_orchestrateur/runs/unknown-run-id/events")
    assert status.status_code == 404
    assert status.json()["detail"] == "Run not found"


async def test_get_run_status_agent_id_mismatch_returns_404(client, monkeypatch):
    await _seed_family_and_agent(client)
    await _seed_second_agent(client)

    async def fake_start_run(**kwargs):
        return None

    monkeypatch.setattr(pipeline_runner, "start_run", fake_start_run)

    create = await client.post("/api/agents/hotel_orchestrateur/runs", json={"message": "hello"})
    run_id = create.json()["run_id"]

    wrong_agent_status = await client.get(f"/api/agents/hotel_orchestrateur_bis/runs/{run_id}")
    assert wrong_agent_status.status_code == 404
    assert wrong_agent_status.json()["detail"] == "Run not found"


async def test_get_run_events_agent_id_mismatch_returns_404(client, monkeypatch):
    await _seed_family_and_agent(client)
    await _seed_second_agent(client)

    async def fake_start_run(**kwargs):
        return None

    monkeypatch.setattr(pipeline_runner, "start_run", fake_start_run)

    create = await client.post("/api/agents/hotel_orchestrateur/runs", json={"message": "hello"})
    run_id = create.json()["run_id"]

    wrong_agent_status = await client.get(f"/api/agents/hotel_orchestrateur_bis/runs/{run_id}/events")
    assert wrong_agent_status.status_code == 404
    assert wrong_agent_status.json()["detail"] == "Run not found"


async def test_chat_endpoint_backward_compatible_shape(client, monkeypatch):
    await _seed_family_and_agent(client)

    from app.api.routes import agents as agents_route

    class _FakeResult:
        status = "completed"
        final_output = "raw"
        tool_calls = [{"tool_name": "t", "tool_output": "o"}]
        duration_ms = 42
        error = None

    async def fake_run_target_agent(**kwargs):
        return _FakeResult()

    monkeypatch.setattr(agents_route, "run_target_agent", fake_run_target_agent)
    monkeypatch.setattr(agents_route, "_synthesize", lambda raw_output, user_message, tool_calls: "synth")

    resp = await client.post(
        "/api/agents/hotel_orchestrateur/chat",
        json={"message": "Bonjour", "timeout_seconds": 5, "max_iterations": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"response", "raw_output", "tool_calls", "duration_ms", "status"}
