# app/services/test_lab/scenario_service.py
"""Scenario CRUD operations."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_lab import TestScenario
from app.schemas.test_lab import ScenarioCreate, ScenarioUpdate

logger = logging.getLogger("orkestra.test_lab.scenario")


async def create_scenario(db: AsyncSession, data: ScenarioCreate) -> TestScenario:
    scenario = TestScenario(
        name=data.name,
        description=data.description,
        agent_id=data.agent_id,
        input_prompt=data.input_prompt,
        input_payload=data.input_payload,
        allowed_tools=data.allowed_tools,
        expected_tools=data.expected_tools,
        timeout_seconds=data.timeout_seconds,
        max_iterations=data.max_iterations,
        retry_count=data.retry_count,
        assertions=[a.model_dump() for a in data.assertions],
        tags=data.tags,
        enabled=data.enabled,
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return scenario


async def get_scenario(db: AsyncSession, scenario_id: str) -> TestScenario | None:
    return await db.get(TestScenario, scenario_id)


async def list_scenarios(
    db: AsyncSession,
    agent_id: str | None = None,
    enabled: bool | None = None,
    limit: int = 50,
) -> list[TestScenario]:
    q = select(TestScenario)
    if agent_id:
        q = q.where(TestScenario.agent_id == agent_id)
    if enabled is not None:
        q = q.where(TestScenario.enabled == enabled)
    q = q.order_by(TestScenario.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def update_scenario(db: AsyncSession, scenario_id: str, data: ScenarioUpdate) -> TestScenario:
    scenario = await db.get(TestScenario, scenario_id)
    if not scenario:
        raise ValueError(f"Scenario {scenario_id} not found")
    update_data = data.model_dump(exclude_unset=True)
    if "assertions" in update_data and update_data["assertions"] is not None:
        update_data["assertions"] = [a if isinstance(a, dict) else a.model_dump() for a in update_data["assertions"]]
    for key, value in update_data.items():
        setattr(scenario, key, value)
    await db.commit()
    await db.refresh(scenario)
    return scenario


async def delete_scenario(db: AsyncSession, scenario_id: str) -> None:
    scenario = await db.get(TestScenario, scenario_id)
    if not scenario:
        raise ValueError(f"Scenario {scenario_id} not found")
    await db.delete(scenario)
    await db.commit()
