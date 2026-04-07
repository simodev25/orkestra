# app/services/test_lab/scenario_service.py
"""Scenario CRUD operations."""

from __future__ import annotations

import logging

from sqlalchemy import select, func
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
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[TestScenario], int]:
    base_q = select(TestScenario)
    if agent_id:
        base_q = base_q.where(TestScenario.agent_id == agent_id)
    if enabled is not None:
        base_q = base_q.where(TestScenario.enabled == enabled)
    count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = count_result.scalar() or 0
    paged_q = base_q.order_by(TestScenario.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(paged_q)
    return list(result.scalars().all()), total


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
