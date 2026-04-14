"""Tests d'intégration async pour execution_service.py.

Utilise SQLite in-memory via les fixtures de conftest.py.
L'event_service est mocké pour éviter les dépendances réseau.
"""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.case import Case
from app.models.plan import OrchestrationPlan
from app.models.run import Run, RunNode
from app.models.enums import RunNodeStatus, RunStatus, PlanStatus, CaseStatus
from app.services import execution_service


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _create_case(db: AsyncSession) -> Case:
    """Crée un Case en état PLANNING (requis par start_run → CaseStateMachine)."""
    case = Case(
        request_id="req_test",
        status=CaseStatus.PLANNING,
    )
    db.add(case)
    await db.flush()
    return case


async def _create_validated_plan(
    db: AsyncSession, case_id: str, topology: dict
) -> OrchestrationPlan:
    plan = OrchestrationPlan(
        case_id=case_id,
        status=PlanStatus.VALIDATED,
        execution_topology=topology,
        estimated_cost=0.0,
    )
    db.add(plan)
    await db.flush()
    return plan


# ── create_run ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCreateRun:
    async def test_creates_run_and_nodes(self, db_session: AsyncSession):
        with patch(
            "app.services.execution_service.emit_event", new_callable=AsyncMock
        ):
            case = await _create_case(db_session)
            topology = {
                "nodes": [
                    {"node_ref": "agent_a", "depends_on": [], "order_index": 0},
                    {
                        "node_ref": "agent_b",
                        "depends_on": ["agent_a"],
                        "order_index": 1,
                    },
                ]
            }
            plan = await _create_validated_plan(db_session, case.id, topology)
            run = await execution_service.create_run(db_session, case.id, plan.id)

            assert run.id is not None
            assert run.case_id == case.id
            assert run.plan_id == plan.id

    async def test_creates_nodes_as_pending(self, db_session: AsyncSession):
        with patch(
            "app.services.execution_service.emit_event", new_callable=AsyncMock
        ):
            case = await _create_case(db_session)
            topology = {
                "nodes": [
                    {"node_ref": "agent_a", "depends_on": [], "order_index": 0}
                ]
            }
            plan = await _create_validated_plan(db_session, case.id, topology)
            run = await execution_service.create_run(db_session, case.id, plan.id)

            stmt = select(RunNode).where(RunNode.run_id == run.id)
            result = await db_session.execute(stmt)
            nodes = result.scalars().all()

            assert len(nodes) == 1
            assert nodes[0].status == RunNodeStatus.PENDING
            assert nodes[0].node_ref == "agent_a"

    async def test_raises_if_plan_not_found(self, db_session: AsyncSession):
        with patch(
            "app.services.execution_service.emit_event", new_callable=AsyncMock
        ):
            case = await _create_case(db_session)
            with pytest.raises(ValueError, match="not found"):
                await execution_service.create_run(
                    db_session, case.id, "nonexistent_plan"
                )

    async def test_raises_if_plan_not_validated(self, db_session: AsyncSession):
        with patch(
            "app.services.execution_service.emit_event", new_callable=AsyncMock
        ):
            case = await _create_case(db_session)
            # Créer un plan en état DRAFT (non validé)
            plan = OrchestrationPlan(
                case_id=case.id,
                status=PlanStatus.DRAFT,
                execution_topology={"nodes": []},
                estimated_cost=0.0,
            )
            db_session.add(plan)
            await db_session.flush()

            with pytest.raises(ValueError, match="validated"):
                await execution_service.create_run(db_session, case.id, plan.id)

    async def test_plan_transitions_to_executing(self, db_session: AsyncSession):
        with patch(
            "app.services.execution_service.emit_event", new_callable=AsyncMock
        ):
            case = await _create_case(db_session)
            topology = {"nodes": []}
            plan = await _create_validated_plan(db_session, case.id, topology)
            await execution_service.create_run(db_session, case.id, plan.id)
            await db_session.refresh(plan)

            assert plan.status == PlanStatus.EXECUTING


# ── start_run ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestStartRun:
    async def test_run_transitions_to_running(self, db_session: AsyncSession):
        with patch(
            "app.services.execution_service.emit_event", new_callable=AsyncMock
        ):
            case = await _create_case(db_session)
            topology = {
                "nodes": [
                    {"node_ref": "a", "depends_on": [], "order_index": 0}
                ]
            }
            plan = await _create_validated_plan(db_session, case.id, topology)
            run = await execution_service.create_run(db_session, case.id, plan.id)

            run = await execution_service.start_run(db_session, run.id)
            assert run.status == RunStatus.RUNNING
            assert run.started_at is not None

    async def test_nodes_without_deps_become_ready(self, db_session: AsyncSession):
        with patch(
            "app.services.execution_service.emit_event", new_callable=AsyncMock
        ):
            case = await _create_case(db_session)
            topology = {
                "nodes": [
                    {"node_ref": "agent_a", "depends_on": [], "order_index": 0},
                    {
                        "node_ref": "agent_b",
                        "depends_on": ["agent_a"],
                        "order_index": 1,
                    },
                ]
            }
            plan = await _create_validated_plan(db_session, case.id, topology)
            run = await execution_service.create_run(db_session, case.id, plan.id)
            await execution_service.start_run(db_session, run.id)

            stmt = (
                select(RunNode)
                .where(RunNode.run_id == run.id)
                .order_by(RunNode.order_index)
            )
            result = await db_session.execute(stmt)
            nodes = result.scalars().all()

            assert nodes[0].status == RunNodeStatus.READY  # agent_a — sans dép.
            assert nodes[1].status == RunNodeStatus.PENDING  # agent_b — dépend de agent_a

    async def test_raises_if_run_not_found(self, db_session: AsyncSession):
        with pytest.raises(ValueError, match="not found"):
            await execution_service.start_run(db_session, "nonexistent_run")


# ── complete_node ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCompleteNode:
    async def test_node_transitions_to_completed(self, db_session: AsyncSession):
        with patch(
            "app.services.execution_service.emit_event", new_callable=AsyncMock
        ):
            case = await _create_case(db_session)
            topology = {
                "nodes": [
                    {"node_ref": "agent_a", "depends_on": [], "order_index": 0}
                ]
            }
            plan = await _create_validated_plan(db_session, case.id, topology)
            run = await execution_service.create_run(db_session, case.id, plan.id)
            await execution_service.start_run(db_session, run.id)

            stmt = select(RunNode).where(RunNode.run_id == run.id)
            result = await db_session.execute(stmt)
            node = result.scalars().first()

            updated = await execution_service.complete_node(db_session, node.id)
            assert updated.status == RunNodeStatus.COMPLETED
            assert updated.ended_at is not None

    async def test_completing_node_unlocks_downstream(self, db_session: AsyncSession):
        with patch(
            "app.services.execution_service.emit_event", new_callable=AsyncMock
        ):
            case = await _create_case(db_session)
            topology = {
                "nodes": [
                    {"node_ref": "agent_a", "depends_on": [], "order_index": 0},
                    {
                        "node_ref": "agent_b",
                        "depends_on": ["agent_a"],
                        "order_index": 1,
                    },
                ]
            }
            plan = await _create_validated_plan(db_session, case.id, topology)
            run = await execution_service.create_run(db_session, case.id, plan.id)
            await execution_service.start_run(db_session, run.id)

            stmt = (
                select(RunNode)
                .where(RunNode.run_id == run.id)
                .order_by(RunNode.order_index)
            )
            result = await db_session.execute(stmt)
            nodes = result.scalars().all()
            node_a, node_b = nodes[0], nodes[1]

            # Avant completion : node_b est en PENDING
            assert node_b.status == RunNodeStatus.PENDING

            await execution_service.complete_node(db_session, node_a.id)
            await db_session.refresh(node_b)

            # Après completion de node_a : node_b passe à READY
            assert node_b.status == RunNodeStatus.READY

    async def test_raises_if_node_not_found(self, db_session: AsyncSession):
        with pytest.raises(ValueError, match="not found"):
            await execution_service.complete_node(db_session, "nonexistent_node")


# ── check_run_completion ──────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCheckRunCompletion:
    async def test_all_completed_transitions_run_to_completed(
        self, db_session: AsyncSession
    ):
        with patch(
            "app.services.execution_service.emit_event", new_callable=AsyncMock
        ):
            case = await _create_case(db_session)
            topology = {
                "nodes": [
                    {"node_ref": "agent_a", "depends_on": [], "order_index": 0}
                ]
            }
            plan = await _create_validated_plan(db_session, case.id, topology)
            run = await execution_service.create_run(db_session, case.id, plan.id)
            await execution_service.start_run(db_session, run.id)

            stmt = select(RunNode).where(RunNode.run_id == run.id)
            result = await db_session.execute(stmt)
            node = result.scalars().first()

            await execution_service.complete_node(db_session, node.id)
            run = await execution_service.check_run_completion(db_session, run.id)

            assert run.status == RunStatus.COMPLETED
            assert run.ended_at is not None

    async def test_pending_nodes_do_not_complete_run(self, db_session: AsyncSession):
        with patch(
            "app.services.execution_service.emit_event", new_callable=AsyncMock
        ):
            case = await _create_case(db_session)
            topology = {
                "nodes": [
                    {"node_ref": "agent_a", "depends_on": [], "order_index": 0},
                    {
                        "node_ref": "agent_b",
                        "depends_on": ["agent_a"],
                        "order_index": 1,
                    },
                ]
            }
            plan = await _create_validated_plan(db_session, case.id, topology)
            run = await execution_service.create_run(db_session, case.id, plan.id)
            await execution_service.start_run(db_session, run.id)

            stmt = (
                select(RunNode)
                .where(RunNode.run_id == run.id)
                .order_by(RunNode.order_index)
            )
            result = await db_session.execute(stmt)
            node_a = result.scalars().first()

            # Compléter seulement node_a — node_b est encore PENDING
            await execution_service.complete_node(db_session, node_a.id)
            run = await execution_service.check_run_completion(db_session, run.id)

            # node_b still PENDING → run ne doit pas être COMPLETED
            assert run.status != RunStatus.COMPLETED

    async def test_raises_if_run_not_found(self, db_session: AsyncSession):
        with pytest.raises(ValueError, match="not found"):
            await execution_service.check_run_completion(db_session, "nonexistent")
