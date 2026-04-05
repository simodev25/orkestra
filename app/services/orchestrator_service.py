"""Orchestrator service — plan generation, agent/MCP selection."""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import OrchestrationPlan
from app.models.case import Case
from app.models.registry import AgentDefinition, MCPDefinition
from app.models.enums import PlanStatus, CaseStatus
from app.state_machines.case_sm import CaseStateMachine
from app.state_machines.plan_sm import PlanStateMachine
from app.services.event_service import emit_event

logger = logging.getLogger(__name__)


async def _discover_agents(db: AsyncSession, use_case: str | None = None) -> list[AgentDefinition]:
    """Discover active agents, optionally filtered by use case hints."""
    stmt = select(AgentDefinition).where(AgentDefinition.status == "active")
    result = await db.execute(stmt)
    agents = list(result.scalars().all())

    if not use_case:
        return agents

    # Score agents by use_case match in selection_hints
    scored = []
    for agent in agents:
        score = 0
        hints = agent.selection_hints or {}
        hint_use_cases = hints.get("use_cases", [])
        if use_case in hint_use_cases:
            score += 10
        # Also include agents without specific use_case hints (generic agents)
        if not hint_use_cases:
            score += 1
        if score > 0:
            scored.append((score, agent))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [agent for _, agent in scored] if scored else agents


async def _discover_mcps(db: AsyncSession, agent_ids: list[str]) -> list[MCPDefinition]:
    """Discover active MCPs that are allowed for the selected agents."""
    stmt = select(MCPDefinition).where(MCPDefinition.status.in_(["active", "degraded"]))
    result = await db.execute(stmt)
    all_mcps = list(result.scalars().all())

    # Filter MCPs that are allowed by at least one selected agent
    relevant = []
    for mcp in all_mcps:
        allowed = mcp.allowed_agents or []
        if not allowed or any(aid in allowed for aid in agent_ids):
            relevant.append(mcp)
    return relevant


def _build_topology(agents: list[AgentDefinition]) -> dict:
    """Build a simple sequential execution topology from selected agents."""
    nodes = []
    for i, agent in enumerate(agents):
        node = {
            "node_ref": agent.id,
            "node_type": "subagent",
            "order_index": i,
            "depends_on": [agents[i - 1].id] if i > 0 else [],
            "parallel_group": None,
        }
        nodes.append(node)
    return {"nodes": nodes, "execution_mode": "sequential"}


def _estimate_cost(agents: list[AgentDefinition], mcps: list[MCPDefinition]) -> float:
    """Rough cost estimate based on agent and MCP cost profiles."""
    cost_map = {"low": 0.5, "medium": 1.0, "high": 2.0, "variable": 1.5}
    total = sum(cost_map.get(a.cost_profile, 1.0) for a in agents)
    total += sum(cost_map.get(m.cost_profile, 0.5) for m in mcps)
    return round(total, 2)


async def generate_plan(db: AsyncSession, case_id: str) -> OrchestrationPlan:
    """Generate an orchestration plan for a case."""
    case = await db.get(Case, case_id)
    if not case:
        raise ValueError(f"Case {case_id} not found")

    if case.status != "ready_for_planning":
        raise ValueError(f"Case must be in ready_for_planning state, got {case.status}")

    # Transition case to planning
    case_sm = CaseStateMachine(case.status)
    if not case_sm.transition("planning"):
        raise ValueError(f"Cannot transition case to planning from {case.status}")
    case.status = case_sm.state

    # Discover agents and MCPs
    agents = await _discover_agents(db, use_case=case.case_type)
    agent_ids = [a.id for a in agents]
    mcps = await _discover_mcps(db, agent_ids)

    # Build topology and estimate cost
    topology = _build_topology(agents)
    estimated_cost = _estimate_cost(agents, mcps)

    # Create plan
    plan = OrchestrationPlan(
        case_id=case_id,
        objective_summary=f"Process case {case_id} ({case.case_type or 'general'})",
        selected_agents=[{"agent_id": a.id, "name": a.name, "family": a.family_id} for a in agents],
        selected_mcps=[{"mcp_id": m.id, "name": m.name, "effect_type": m.effect_type} for m in mcps],
        execution_topology=topology,
        estimated_cost=estimated_cost,
        estimated_parallelism=1,  # sequential for now
        status=PlanStatus.DRAFT,
    )
    db.add(plan)
    await db.flush()

    # Auto-validate (simplified — no control engine yet)
    plan_sm = PlanStateMachine(plan.status)
    plan_sm.transition("validated")
    plan.status = plan_sm.state

    await emit_event(db, "plan.created", "orchestrator", "orchestrator_service",
                     payload={"plan_id": plan.id, "case_id": case_id, "agents": agent_ids})
    await emit_event(db, "plan.validated", "orchestrator", "orchestrator_service",
                     payload={"plan_id": plan.id})

    return plan


async def get_plan(db: AsyncSession, plan_id: str) -> OrchestrationPlan | None:
    return await db.get(OrchestrationPlan, plan_id)


async def get_plan_for_case(db: AsyncSession, case_id: str) -> OrchestrationPlan | None:
    stmt = select(OrchestrationPlan).where(
        OrchestrationPlan.case_id == case_id
    ).order_by(OrchestrationPlan.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().first()
