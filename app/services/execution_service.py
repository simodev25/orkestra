"""Execution service — run creation, node scheduling, graph execution."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import OrchestrationPlan
from app.models.run import Run, RunNode
from app.models.case import Case
from app.models.enums import RunStatus, RunNodeStatus, RunNodeType, PlanStatus
from app.state_machines.run_sm import RunStateMachine
from app.state_machines.plan_sm import PlanStateMachine
from app.state_machines.case_sm import CaseStateMachine
from app.services.event_service import emit_event

logger = logging.getLogger(__name__)


async def create_run(db: AsyncSession, case_id: str, plan_id: str) -> Run:
    """Create a run from a validated plan and materialize the execution graph."""
    plan = await db.get(OrchestrationPlan, plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")
    if plan.status != "validated":
        raise ValueError(f"Plan must be validated to create a run, got {plan.status}")
    if plan.case_id != case_id:
        raise ValueError(f"Plan {plan_id} does not belong to case {case_id}")

    case = await db.get(Case, case_id)
    if not case:
        raise ValueError(f"Case {case_id} not found")

    # Create run
    run = Run(
        case_id=case_id,
        plan_id=plan_id,
        workflow_id=plan.workflow_id,
        status=RunStatus.CREATED,
        estimated_cost=plan.estimated_cost,
    )
    db.add(run)
    await db.flush()

    # Materialize execution graph from topology
    topology = plan.execution_topology or {"nodes": []}
    nodes_data = topology.get("nodes", [])
    for node_data in nodes_data:
        node = RunNode(
            run_id=run.id,
            node_type=node_data.get("node_type", RunNodeType.SUBAGENT),
            node_ref=node_data["node_ref"],
            status=RunNodeStatus.PENDING,
            depends_on=node_data.get("depends_on"),
            parallel_group=node_data.get("parallel_group"),
            trigger_condition=node_data.get("trigger_condition"),
            order_index=node_data.get("order_index", 0),
        )
        db.add(node)

    # Transition plan to executing
    plan_sm = PlanStateMachine(plan.status)
    plan_sm.transition("executing")
    plan.status = plan_sm.state
    plan.run_id = run.id

    # Transition run to planned
    run_sm = RunStateMachine(run.status)
    run_sm.transition("planned")
    run.status = run_sm.state

    # Update case
    case.current_run_id = run.id

    await db.flush()
    await emit_event(db, "run.created", "system", "execution_service",
                     run_id=run.id, payload={"case_id": case_id, "plan_id": plan_id})

    return run


async def start_run(db: AsyncSession, run_id: str) -> Run:
    """Start a run: transition to running, mark ready nodes, update case."""
    run = await db.get(Run, run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    run_sm = RunStateMachine(run.status)
    if not run_sm.transition("running"):
        raise ValueError(f"Cannot start run in state {run.status}")
    run.status = run_sm.state
    run.started_at = datetime.now(timezone.utc)

    # Transition case to running
    case = await db.get(Case, run.case_id)
    if case and case.status == "planning":
        case_sm = CaseStateMachine(case.status)
        case_sm.transition("running")
        case.status = case_sm.state

    # Mark nodes with no dependencies as ready
    stmt = select(RunNode).where(RunNode.run_id == run_id)
    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    for node in nodes:
        deps = node.depends_on or []
        if not deps:
            node.status = RunNodeStatus.READY

    await db.flush()
    await emit_event(db, "run.started", "system", "execution_service",
                     run_id=run_id, payload={"case_id": run.case_id})
    return run


async def get_ready_nodes(db: AsyncSession, run_id: str) -> list[RunNode]:
    """Get all nodes that are ready to execute."""
    stmt = select(RunNode).where(
        RunNode.run_id == run_id,
        RunNode.status == RunNodeStatus.READY,
    ).order_by(RunNode.order_index)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def complete_node(db: AsyncSession, node_id: str) -> RunNode:
    """Mark a node as completed and check if downstream nodes become ready."""
    node = await db.get(RunNode, node_id)
    if not node:
        raise ValueError(f"Node {node_id} not found")

    node.status = RunNodeStatus.COMPLETED
    node.ended_at = datetime.now(timezone.utc)

    # Check if any pending nodes' dependencies are now all completed
    stmt = select(RunNode).where(
        RunNode.run_id == node.run_id,
        RunNode.status == RunNodeStatus.PENDING,
    )
    result = await db.execute(stmt)
    pending_nodes = list(result.scalars().all())

    # Get all completed node refs
    stmt2 = select(RunNode).where(
        RunNode.run_id == node.run_id,
        RunNode.status == RunNodeStatus.COMPLETED,
    )
    result2 = await db.execute(stmt2)
    completed_refs = {n.node_ref for n in result2.scalars().all()}

    for pending in pending_nodes:
        deps = pending.depends_on or []
        if all(dep in completed_refs for dep in deps):
            pending.status = RunNodeStatus.READY

    await db.flush()
    await emit_event(db, "run.node_completed", "system", "execution_service",
                     run_id=node.run_id, payload={"node_id": node_id, "node_ref": node.node_ref})

    return node


async def fail_node(db: AsyncSession, node_id: str, error: str = "") -> RunNode:
    """Mark a node as failed."""
    node = await db.get(RunNode, node_id)
    if not node:
        raise ValueError(f"Node {node_id} not found")
    node.status = RunNodeStatus.FAILED
    node.ended_at = datetime.now(timezone.utc)
    await db.flush()
    await emit_event(db, "run.node_failed", "system", "execution_service",
                     run_id=node.run_id, payload={"node_id": node_id, "error": error})
    return node


async def check_run_completion(db: AsyncSession, run_id: str) -> Run:
    """Check if all nodes are done and complete/fail the run accordingly."""
    run = await db.get(Run, run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    stmt = select(RunNode).where(RunNode.run_id == run_id)
    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    all_done = all(n.status in ("completed", "skipped", "failed") for n in nodes)
    if not all_done:
        return run

    any_failed = any(n.status == "failed" for n in nodes)
    run_sm = RunStateMachine(run.status)

    if any_failed:
        run_sm.transition("failed")
    else:
        run_sm.transition("completed")

    run.status = run_sm.state
    run.ended_at = datetime.now(timezone.utc)

    # Update case
    case = await db.get(Case, run.case_id)
    if case:
        case_sm = CaseStateMachine(case.status)
        if run.status == "completed":
            case_sm.transition("completed")
        elif run.status == "failed":
            case_sm.transition("blocked")
        case.status = case_sm.state

    await db.flush()
    event_type = "run.completed" if run.status == "completed" else "run.failed"
    await emit_event(db, event_type, "system", "execution_service",
                     run_id=run_id, payload={"final_status": run.status})
    return run


async def cancel_run(db: AsyncSession, run_id: str) -> Run:
    """Cancel a run."""
    run = await db.get(Run, run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    run_sm = RunStateMachine(run.status)
    if not run_sm.transition("cancelled"):
        raise ValueError(f"Cannot cancel run in state {run.status}")
    run.status = run_sm.state
    run.ended_at = datetime.now(timezone.utc)
    await db.flush()
    await emit_event(db, "run.cancelled", "system", "execution_service", run_id=run_id)
    return run


async def get_run(db: AsyncSession, run_id: str) -> Run | None:
    return await db.get(Run, run_id)


async def list_runs(db: AsyncSession, case_id: str | None = None, status: str | None = None,
                    limit: int = 50, offset: int = 0) -> list[Run]:
    stmt = select(Run)
    if case_id:
        stmt = stmt.where(Run.case_id == case_id)
    if status:
        stmt = stmt.where(Run.status == status)
    stmt = stmt.order_by(Run.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_run_nodes(db: AsyncSession, run_id: str) -> list[RunNode]:
    stmt = select(RunNode).where(RunNode.run_id == run_id).order_by(RunNode.order_index)
    result = await db.execute(stmt)
    return list(result.scalars().all())
