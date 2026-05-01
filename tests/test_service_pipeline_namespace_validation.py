"""Service tests for orchestrator pipeline same-namespace validation."""

import pytest

from app.models.namespace import Namespace
from app.schemas.agent import AgentCreate, AgentUpdate
from app.schemas.family import FamilyCreate
from app.services import agent_registry_service, family_service
from app.core.namespaces import DEFAULT_NAMESPACE_ID


async def _create_family(db_session) -> None:
    await family_service.create_family(db_session, FamilyCreate(id="analysis", label="Analysis"))
    await db_session.commit()


async def _create_namespace(db_session, ns_id: str, slug: str, name: str) -> None:
    db_session.add(Namespace(id=ns_id, slug=slug, name=name, description=f"{name} namespace"))
    await db_session.commit()


def _agent_payload(agent_id: str, namespace_id: str) -> AgentCreate:
    return AgentCreate(
        id=agent_id,
        name=f"Agent {agent_id}",
        family_id="analysis",
        purpose="Pipeline namespace validation agent",
        namespace_id=namespace_id,
    )


async def test_pipeline_agent_ids_reject_cross_namespace_on_create(db_session):
    await _create_family(db_session)
    await _create_namespace(db_session, "00000000-0000-0000-0000-000000000001", "team-alpha", "Team Alpha")
    await _create_namespace(db_session, "00000000-0000-0000-0000-000000000002", "team-beta", "Team Beta")

    await agent_registry_service.create_agent(
        db_session,
        _agent_payload("agent_alpha", "00000000-0000-0000-0000-000000000001"),
    )
    await agent_registry_service.create_agent(
        db_session,
        _agent_payload("agent_beta", "00000000-0000-0000-0000-000000000002"),
    )
    await db_session.commit()

    with pytest.raises(ValueError, match="All pipeline agents must belong to the same namespace"):
        await agent_registry_service.create_agent(
            db_session,
            AgentCreate(
                id="orch_cross_ns",
                name="Orchestrator Cross NS",
                family_id="analysis",
                purpose="Orchestrator with mixed namespace pipeline",
                namespace_id="00000000-0000-0000-0000-000000000001",
                pipeline_agent_ids=["agent_alpha", "agent_beta"],
            ),
        )


async def test_pipeline_agent_ids_accept_same_namespace_on_create(db_session):
    await _create_family(db_session)
    await _create_namespace(db_session, "00000000-0000-0000-0000-000000000001", "team-alpha", "Team Alpha")

    await agent_registry_service.create_agent(
        db_session,
        _agent_payload("agent_alpha_1", "00000000-0000-0000-0000-000000000001"),
    )
    await agent_registry_service.create_agent(
        db_session,
        _agent_payload("agent_alpha_2", "00000000-0000-0000-0000-000000000001"),
    )
    await db_session.commit()

    orchestrator = await agent_registry_service.create_agent(
        db_session,
        AgentCreate(
            id="orch_same_ns",
            name="Orchestrator Same NS",
            family_id="analysis",
            purpose="Orchestrator with same namespace pipeline",
            namespace_id="00000000-0000-0000-0000-000000000001",
            pipeline_agent_ids=["agent_alpha_1", "agent_alpha_2"],
        ),
    )
    assert orchestrator.id == "orch_same_ns"


async def test_pipeline_agent_ids_reject_cross_namespace_on_update(db_session):
    await _create_family(db_session)
    await _create_namespace(db_session, "00000000-0000-0000-0000-000000000001", "team-alpha", "Team Alpha")
    await _create_namespace(db_session, "00000000-0000-0000-0000-000000000002", "team-beta", "Team Beta")

    await agent_registry_service.create_agent(
        db_session,
        _agent_payload("agent_alpha_update", "00000000-0000-0000-0000-000000000001"),
    )
    await agent_registry_service.create_agent(
        db_session,
        _agent_payload("agent_beta_update", "00000000-0000-0000-0000-000000000002"),
    )
    orchestrator = await agent_registry_service.create_agent(
        db_session,
        AgentCreate(
            id="orch_update_ns",
            name="Orchestrator Update NS",
            family_id="analysis",
            purpose="Orchestrator update namespace pipeline",
            namespace_id="00000000-0000-0000-0000-000000000001",
        ),
    )
    await db_session.commit()

    with pytest.raises(ValueError, match="All pipeline agents must belong to the same namespace"):
        await agent_registry_service.update_agent(
            db_session,
            orchestrator.id,
            AgentUpdate(pipeline_agent_ids=["agent_alpha_update", "agent_beta_update"]),
        )


async def test_agent_create_defaults_namespace_to_default_uuid(db_session):
    await _create_family(db_session)
    agent = await agent_registry_service.create_agent(
        db_session,
        AgentCreate(
            id="default_ns_agent",
            name="Default Namespace Agent",
            family_id="analysis",
            purpose="Default namespace fallback on creation",
        ),
    )
    assert agent.namespace_id == str(DEFAULT_NAMESPACE_ID)
