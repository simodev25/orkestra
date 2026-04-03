"""Control service — governance engine, policy evaluation, safe-blocks."""

import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.control import ControlDecision
from app.models.settings import PolicyProfile, BudgetProfile
from app.models.run import Run
from app.models.registry import AgentDefinition, MCPDefinition
from app.models.enums import ControlDecisionScope, ControlDecisionType
from app.services.event_service import emit_event

logger = logging.getLogger(__name__)


async def _get_default_policy(db: AsyncSession) -> PolicyProfile | None:
    stmt = select(PolicyProfile).where(PolicyProfile.is_default == True)
    result = await db.execute(stmt)
    return result.scalars().first()


async def _get_default_budget(db: AsyncSession) -> BudgetProfile | None:
    stmt = select(BudgetProfile).where(BudgetProfile.is_default == True)
    result = await db.execute(stmt)
    return result.scalars().first()


async def evaluate_plan(
    db: AsyncSession,
    run_id: str,
    plan_agents: list[dict],
    plan_mcps: list[dict],
    estimated_cost: float,
    criticality: str = "medium",
) -> list[ControlDecision]:
    """Evaluate a plan against policies. Returns list of control decisions."""
    decisions = []

    # Check budget
    budget = await _get_default_budget(db)
    if budget and budget.hard_limit and estimated_cost > budget.hard_limit:
        d = ControlDecision(
            run_id=run_id,
            decision_scope=ControlDecisionScope.PLAN,
            decision_type=ControlDecisionType.DENY,
            policy_rule_id="budget_hard_limit",
            reason=f"Estimated cost {estimated_cost} exceeds hard limit {budget.hard_limit}",
            severity="high",
            target_ref=run_id,
        )
        db.add(d)
        decisions.append(d)
    elif budget and budget.soft_limit and estimated_cost > budget.soft_limit:
        d = ControlDecision(
            run_id=run_id,
            decision_scope=ControlDecisionScope.PLAN,
            decision_type=ControlDecisionType.HOLD,
            policy_rule_id="budget_soft_limit",
            reason=f"Estimated cost {estimated_cost} exceeds soft limit {budget.soft_limit}",
            severity="medium",
            target_ref=run_id,
        )
        db.add(d)
        decisions.append(d)

    # Check high-criticality requires review
    policy = await _get_default_policy(db)
    if policy:
        rules = policy.rules or {}
        if rules.get("high_criticality_requires_review") and criticality == "high":
            d = ControlDecision(
                run_id=run_id,
                decision_scope=ControlDecisionScope.PLAN,
                decision_type=ControlDecisionType.REVIEW_REQUIRED,
                policy_rule_id="high_criticality_review",
                reason="High criticality cases require human review",
                severity="high",
                target_ref=run_id,
            )
            db.add(d)
            decisions.append(d)

    # If no issues found, allow
    if not decisions:
        d = ControlDecision(
            run_id=run_id,
            decision_scope=ControlDecisionScope.PLAN,
            decision_type=ControlDecisionType.ALLOW,
            reason="Plan approved — no policy violations",
            severity="low",
            target_ref=run_id,
        )
        db.add(d)
        decisions.append(d)

    await db.flush()
    for d in decisions:
        await emit_event(
            db,
            f"control.{d.decision_type}",
            "control",
            "control_service",
            run_id=run_id,
            payload={"decision_id": d.id, "scope": d.decision_scope},
        )
    return decisions


async def check_agent_authorization(
    db: AsyncSession,
    run_id: str,
    agent_id: str,
) -> ControlDecision:
    """Check if an agent is authorized for execution."""
    agent = await db.get(AgentDefinition, agent_id)

    if not agent:
        d = ControlDecision(
            run_id=run_id,
            decision_scope=ControlDecisionScope.AGENT,
            decision_type=ControlDecisionType.DENY,
            policy_rule_id="agent_not_found",
            reason=f"Agent {agent_id} not found in registry",
            severity="high",
            target_ref=agent_id,
        )
        db.add(d)
        await db.flush()
        return d

    if agent.status != "active":
        d = ControlDecision(
            run_id=run_id,
            decision_scope=ControlDecisionScope.AGENT,
            decision_type=ControlDecisionType.DENY,
            policy_rule_id="agent_not_active",
            reason=f"Agent {agent_id} is {agent.status}, not active",
            severity="high",
            target_ref=agent_id,
        )
        db.add(d)
        await db.flush()
        return d

    d = ControlDecision(
        run_id=run_id,
        decision_scope=ControlDecisionScope.AGENT,
        decision_type=ControlDecisionType.ALLOW,
        reason=f"Agent {agent_id} authorized",
        severity="low",
        target_ref=agent_id,
    )
    db.add(d)
    await db.flush()
    return d


async def check_mcp_authorization(
    db: AsyncSession,
    run_id: str,
    mcp_id: str,
    calling_agent_id: str,
) -> ControlDecision:
    """Check if an MCP call is authorized."""
    mcp = await db.get(MCPDefinition, mcp_id)

    if not mcp or mcp.status not in ("active", "degraded"):
        d = ControlDecision(
            run_id=run_id,
            decision_scope=ControlDecisionScope.MCP,
            decision_type=ControlDecisionType.DENY,
            policy_rule_id="mcp_unavailable",
            reason=f"MCP {mcp_id} not available",
            severity="high",
            target_ref=mcp_id,
        )
        db.add(d)
        await db.flush()
        return d

    # Check allowlist
    agent = await db.get(AgentDefinition, calling_agent_id)
    if agent:
        allowed = agent.allowed_mcps or []
        if allowed and mcp_id not in allowed:
            d = ControlDecision(
                run_id=run_id,
                decision_scope=ControlDecisionScope.MCP,
                decision_type=ControlDecisionType.DENY,
                policy_rule_id="mcp_not_in_allowlist",
                reason=f"MCP {mcp_id} not in agent {calling_agent_id} allowlist",
                severity="high",
                target_ref=mcp_id,
            )
            db.add(d)
            await db.flush()
            return d

    # Check if sensitive effect type requires review
    if mcp.effect_type in ("write", "act") and mcp.approval_required:
        d = ControlDecision(
            run_id=run_id,
            decision_scope=ControlDecisionScope.MCP,
            decision_type=ControlDecisionType.REVIEW_REQUIRED,
            policy_rule_id="sensitive_effect_review",
            reason=f"MCP {mcp_id} has {mcp.effect_type} effect and requires approval",
            severity="medium",
            target_ref=mcp_id,
        )
        db.add(d)
        await db.flush()
        return d

    d = ControlDecision(
        run_id=run_id,
        decision_scope=ControlDecisionScope.MCP,
        decision_type=ControlDecisionType.ALLOW,
        reason=f"MCP {mcp_id} authorized for agent {calling_agent_id}",
        severity="low",
        target_ref=mcp_id,
    )
    db.add(d)
    await db.flush()
    return d


async def get_decisions_for_run(db: AsyncSession, run_id: str) -> list[ControlDecision]:
    stmt = (
        select(ControlDecision)
        .where(ControlDecision.run_id == run_id)
        .order_by(ControlDecision.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_decisions(
    db: AsyncSession,
    decision_scope: str | None = None,
    decision_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ControlDecision]:
    stmt = select(ControlDecision)
    if decision_scope:
        stmt = stmt.where(ControlDecision.decision_scope == decision_scope)
    if decision_type:
        stmt = stmt.where(ControlDecision.decision_type == decision_type)
    stmt = stmt.order_by(ControlDecision.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())
