# tests/test_service_agent_registry.py
"""Tests unitaires pour agent_registry_service.

Utilise la DB in-memory via db_session.
Chaque test est isolé : setup_db (autouse) recrée le schéma.
"""
import pytest

from app.schemas.agent import AgentCreate, AgentUpdate
from app.schemas.family import FamilyCreate
from app.services import agent_registry_service, family_service
from app.models.enums import AgentStatus, Criticality, CostProfile


async def _create_family(db_session, family_id: str = "test_family") -> None:
    data = FamilyCreate(id=family_id, label="Test Family")
    await family_service.create_family(db_session, data)
    await db_session.commit()


def _agent_payload(**overrides) -> AgentCreate:
    return AgentCreate(
        id=overrides.get("id", "agent_test"),
        name=overrides.get("name", "Test Agent"),
        family_id=overrides.get("family_id", "test_family"),
        purpose=overrides.get("purpose", "Test purpose for agent"),
        **{k: v for k, v in overrides.items() if k not in ("id", "name", "family_id", "purpose")},
    )


# ── create_agent ───────────────────────────────────────────────────────────────

async def test_create_agent_returns_agent(db_session):
    await _create_family(db_session)
    agent = await agent_registry_service.create_agent(db_session, _agent_payload())
    assert agent.id == "agent_test"
    assert agent.name == "Test Agent"
    assert agent.family_id == "test_family"
    assert agent.status == AgentStatus.DRAFT


async def test_create_agent_defaults_criticality_medium(db_session):
    await _create_family(db_session)
    agent = await agent_registry_service.create_agent(db_session, _agent_payload())
    assert agent.criticality == Criticality.MEDIUM


async def test_create_agent_duplicate_id_raises(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()
    with pytest.raises(Exception):
        await agent_registry_service.create_agent(db_session, _agent_payload())


async def test_create_agent_unknown_family_raises(db_session):
    with pytest.raises(ValueError, match="family"):
        await agent_registry_service.create_agent(
            db_session, _agent_payload(family_id="nonexistent_family")
        )


# ── get_agent ─────────────────────────────────────────────────────────────────

async def test_get_agent_returns_agent(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()

    agent = await agent_registry_service.get_agent(db_session, "agent_test")
    assert agent is not None
    assert agent.id == "agent_test"


async def test_get_agent_nonexistent_returns_none(db_session):
    agent = await agent_registry_service.get_agent(db_session, "nonexistent")
    assert agent is None


# ── list_agents ────────────────────────────────────────────────────────────────

async def test_list_agents_returns_all(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a1", name="Agent 1"))
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a2", name="Agent 2"))
    await db_session.commit()

    agents, total = await agent_registry_service.list_agents(db_session)
    assert total >= 2
    ids = [a.id for a in agents]
    assert "a1" in ids
    assert "a2" in ids


async def test_list_agents_filter_by_family(db_session):
    await _create_family(db_session, "fam_a")
    await _create_family(db_session, "fam_b")
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a1", family_id="fam_a"))
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a2", family_id="fam_b"))
    await db_session.commit()

    agents, total = await agent_registry_service.list_agents(db_session, family="fam_a")
    assert total == 1
    assert agents[0].id == "a1"


async def test_list_agents_filter_by_status(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a_draft", status=AgentStatus.DRAFT))
    await db_session.commit()

    agents, total = await agent_registry_service.list_agents(db_session, status="draft")
    assert total >= 1
    assert all(a.status == AgentStatus.DRAFT for a in agents)


async def test_list_agents_empty(db_session):
    agents, total = await agent_registry_service.list_agents(db_session)
    assert total == 0
    assert agents == []


# ── update_agent ───────────────────────────────────────────────────────────────

async def test_update_agent_name(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()

    updated = await agent_registry_service.update_agent(
        db_session, "agent_test", AgentUpdate(name="Updated Name")
    )
    assert updated.name == "Updated Name"


async def test_update_agent_nonexistent_raises(db_session):
    with pytest.raises(ValueError):
        await agent_registry_service.update_agent(
            db_session, "nonexistent", AgentUpdate(name="x")
        )


# ── update_agent_status ────────────────────────────────────────────────────────

async def test_update_agent_status_draft_to_designed(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()

    updated = await agent_registry_service.update_agent_status(
        db_session, "agent_test", "designed", "ready for design"
    )
    assert updated.status == AgentStatus.DESIGNED


# ── delete_agent ───────────────────────────────────────────────────────────────

async def test_delete_agent_removes_it(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()

    await agent_registry_service.delete_agent(db_session, "agent_test")
    await db_session.commit()

    agent = await agent_registry_service.get_agent(db_session, "agent_test")
    assert agent is None


# ── enrich_agent ───────────────────────────────────────────────────────────────

async def test_enrich_agent_includes_family(db_session):
    await _create_family(db_session)
    agent = await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()

    enriched = await agent_registry_service.enrich_agent(db_session, agent)
    assert isinstance(enriched, dict)
    assert enriched["id"] == "agent_test"


# ── get_registry_stats ─────────────────────────────────────────────────────────

async def test_get_registry_stats_zero_initially(db_session):
    stats = await agent_registry_service.get_registry_stats(db_session)
    assert stats.total_agents == 0


async def test_get_registry_stats_counts_agents(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a1"))
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a2"))
    await db_session.commit()

    stats = await agent_registry_service.get_registry_stats(db_session)
    assert stats.total_agents == 2
