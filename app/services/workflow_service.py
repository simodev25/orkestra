"""Workflow service -- CRUD, validation, versioning for workflow definitions."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import WorkflowDefinition
from app.services.event_service import emit_event

logger = logging.getLogger(__name__)


def validate_graph(graph: dict) -> list[str]:
    """Validate workflow graph structure. Returns list of errors."""
    errors = []
    nodes = graph.get("nodes", [])
    if not nodes:
        return errors  # Empty graph is valid (orchestrator decides)

    node_refs = {n.get("node_ref") for n in nodes}
    for node in nodes:
        ref = node.get("node_ref")
        if not ref:
            errors.append("Node missing node_ref")
            continue
        deps = node.get("depends_on", [])
        for dep in deps:
            if dep not in node_refs:
                errors.append(f"Node {ref} depends on unknown node {dep}")

    # Check for cycles (simple DFS)
    adj = {n.get("node_ref"): n.get("depends_on", []) for n in nodes}
    visited = set()
    rec_stack = set()

    def has_cycle(node_ref):
        visited.add(node_ref)
        rec_stack.add(node_ref)
        for dep in adj.get(node_ref, []):
            if dep not in visited:
                if has_cycle(dep):
                    return True
            elif dep in rec_stack:
                return True
        rec_stack.discard(node_ref)
        return False

    for ref in node_refs:
        if ref not in visited:
            if has_cycle(ref):
                errors.append("Cycle detected in workflow graph")
                break

    return errors


async def create_workflow(
    db: AsyncSession, name: str, use_case: str | None = None,
    execution_mode: str = "sequential", graph_definition: dict | None = None,
    policy_profile_id: str | None = None, budget_profile_id: str | None = None,
) -> WorkflowDefinition:
    if graph_definition:
        errors = validate_graph(graph_definition)
        if errors:
            raise ValueError(f"Graph validation errors: {'; '.join(errors)}")

    wf = WorkflowDefinition(
        name=name, use_case=use_case, execution_mode=execution_mode,
        graph_definition=graph_definition, policy_profile_id=policy_profile_id,
        budget_profile_id=budget_profile_id, status="draft",
    )
    db.add(wf)
    await db.flush()
    await emit_event(db, "workflow.created", "system", "workflow_service",
                     payload={"workflow_id": wf.id})
    return wf


async def publish_workflow(db: AsyncSession, workflow_id: str) -> WorkflowDefinition:
    wf = await db.get(WorkflowDefinition, workflow_id)
    if not wf:
        raise ValueError(f"Workflow {workflow_id} not found")
    if wf.status == "published":
        raise ValueError("Workflow already published")

    if wf.graph_definition:
        errors = validate_graph(wf.graph_definition)
        if errors:
            raise ValueError(f"Cannot publish: {'; '.join(errors)}")

    wf.status = "published"
    wf.published_at = datetime.now(timezone.utc)
    await db.flush()
    await emit_event(db, "workflow.published", "system", "workflow_service",
                     payload={"workflow_id": wf.id})
    return wf


async def update_workflow(
    db: AsyncSession, workflow_id: str, **kwargs
) -> WorkflowDefinition:
    wf = await db.get(WorkflowDefinition, workflow_id)
    if not wf:
        raise ValueError(f"Workflow {workflow_id} not found")

    if "graph_definition" in kwargs and kwargs["graph_definition"]:
        errors = validate_graph(kwargs["graph_definition"])
        if errors:
            raise ValueError(f"Graph validation errors: {'; '.join(errors)}")

    for key, value in kwargs.items():
        if value is not None and hasattr(wf, key):
            setattr(wf, key, value)

    await db.flush()
    return wf


async def validate_workflow(db: AsyncSession, workflow_id: str) -> dict:
    wf = await db.get(WorkflowDefinition, workflow_id)
    if not wf:
        raise ValueError(f"Workflow {workflow_id} not found")

    errors = validate_graph(wf.graph_definition or {})
    return {"workflow_id": workflow_id, "valid": len(errors) == 0, "errors": errors}


async def list_workflows(
    db: AsyncSession, use_case: str | None = None, status: str | None = None,
    limit: int = 50, offset: int = 0,
) -> list[WorkflowDefinition]:
    stmt = select(WorkflowDefinition)
    if use_case:
        stmt = stmt.where(WorkflowDefinition.use_case == use_case)
    if status:
        stmt = stmt.where(WorkflowDefinition.status == status)
    stmt = stmt.order_by(WorkflowDefinition.name).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_workflow(db: AsyncSession, workflow_id: str) -> WorkflowDefinition | None:
    return await db.get(WorkflowDefinition, workflow_id)
