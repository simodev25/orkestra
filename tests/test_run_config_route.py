"""Tests for PATCH /api/runs/{run_id}/config"""

import pytest
from app.models.run import Run


async def _create_run(db_session, config=None):
    run = Run(case_id="case_1", plan_id="plan_1", status="created", config=config)
    db_session.add(run)
    await db_session.commit()
    return run


class TestPatchRunConfig:
    async def test_patch_run_config_sets_effect_overrides(self, client, db_session):
        """PATCH {"effect_overrides": ["write"]} → 200, config updated."""
        run = await _create_run(db_session)

        response = await client.patch(
            f"/api/runs/{run.id}/config",
            json={"effect_overrides": ["write"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run.id
        assert data["config"]["effect_overrides"] == ["write"]

    async def test_patch_run_config_not_found(self, client):
        """PATCH on unknown run_id → 404."""
        response = await client.patch(
            "/api/runs/nonexistent-run-id/config",
            json={"effect_overrides": ["write"]},
        )

        assert response.status_code == 404
        assert "nonexistent-run-id" in response.json()["detail"]

    async def test_patch_run_config_merges_existing_keys(self, client, db_session):
        """Run already has config={"other_key": "val"} → after PATCH, other_key still present."""
        run = await _create_run(db_session, config={"other_key": "val"})

        response = await client.patch(
            f"/api/runs/{run.id}/config",
            json={"effect_overrides": ["act"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["config"]["effect_overrides"] == ["act"]
        assert data["config"]["other_key"] == "val"
