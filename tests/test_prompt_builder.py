"""Tests for the multi-layer prompt builder."""

import pytest


async def _seed_family_and_skill(client, family_id="analysis"):
    """Create a family with system rules and a skill."""
    await client.post("/api/families", json={
        "id": family_id,
        "label": "Analysis",
        "description": "Analysis family",
        "default_system_rules": ["You are an analysis agent.", "Be precise."],
        "default_forbidden_effects": ["publish", "approve"],
        "default_output_expectations": ["Produce structured findings."],
        "version": "1.0.0",
        "status": "active",
        "owner": "test",
    })
    await client.post("/api/skills", json={
        "skill_id": "web_research",
        "label": "Web Research",
        "category": "execution",
        "description": "Search the web",
        "behavior_templates": ["Search broadly first.", "Prioritize official sources."],
        "output_guidelines": ["Cite sources.", "Distinguish facts from interpretation."],
        "allowed_families": [family_id],
        "version": "1.0.0",
        "status": "active",
    })


async def test_prompt_builder_family_rules(client, db_session):
    """Family rules should appear in the prompt."""
    await _seed_family_and_skill(client)

    # Create agent with the family
    await client.post("/api/agents", json={
        "id": "test_builder_agent",
        "name": "Test Builder Agent",
        "family_id": "analysis",
        "purpose": "Test prompt building",
        "skill_ids": ["web_research"],
    })

    # Build prompt directly via service
    from app.models.registry import AgentDefinition
    from app.services.prompt_builder import build_agent_prompt

    agent = await db_session.get(AgentDefinition, "test_builder_agent")
    prompt = await build_agent_prompt(db_session, agent)

    assert "FAMILY RULES" in prompt
    assert "You are an analysis agent." in prompt
    assert "Be precise." in prompt


async def test_prompt_builder_skill_rules(client, db_session):
    """Skill behavior templates should appear in the prompt."""
    await _seed_family_and_skill(client)
    await client.post("/api/agents", json={
        "id": "skill_prompt_agent",
        "name": "Skill Prompt Agent",
        "family_id": "analysis",
        "purpose": "Test skill prompt building",
        "skill_ids": ["web_research"],
    })

    from app.models.registry import AgentDefinition
    from app.services.prompt_builder import build_agent_prompt

    agent = await db_session.get(AgentDefinition, "skill_prompt_agent")
    prompt = await build_agent_prompt(db_session, agent)

    assert "SKILL RULES" in prompt
    assert "Web Research" in prompt
    assert "Search broadly first." in prompt
    assert "Cite sources." in prompt


async def test_prompt_builder_output_expectations(client, db_session):
    """Family output expectations should appear after agent mission."""
    await _seed_family_and_skill(client)
    await client.post("/api/agents", json={
        "id": "output_agent",
        "name": "Output Agent",
        "family_id": "analysis",
        "purpose": "Test output expectations",
    })

    from app.models.registry import AgentDefinition
    from app.services.prompt_builder import build_agent_prompt

    agent = await db_session.get(AgentDefinition, "output_agent")
    prompt = await build_agent_prompt(db_session, agent)

    assert "OUTPUT EXPECTATIONS" in prompt
    assert "Produce structured findings." in prompt


async def test_prompt_builder_layer_order(client, db_session):
    """Layers should appear in the correct order."""
    await _seed_family_and_skill(client)
    await client.post("/api/agents", json={
        "id": "order_agent",
        "name": "Order Agent",
        "family_id": "analysis",
        "purpose": "Test layer ordering",
        "skill_ids": ["web_research"],
    })

    from app.models.registry import AgentDefinition
    from app.services.prompt_builder import build_agent_prompt

    agent = await db_session.get(AgentDefinition, "order_agent")
    prompt = await build_agent_prompt(db_session, agent)

    # Check ordering: FAMILY RULES before SKILL RULES before AGENT MISSION before OUTPUT EXPECTATIONS
    family_pos = prompt.index("FAMILY RULES")
    skill_pos = prompt.index("SKILL RULES")
    mission_pos = prompt.index("AGENT MISSION")
    output_pos = prompt.index("OUTPUT EXPECTATIONS")

    assert family_pos < skill_pos < mission_pos < output_pos


async def test_prompt_builder_soul_optional(client, db_session):
    """Soul layer should be skipped if not set."""
    await _seed_family_and_skill(client)
    await client.post("/api/agents", json={
        "id": "no_soul_agent",
        "name": "No Soul Agent",
        "family_id": "analysis",
        "purpose": "Test soul absence",
    })

    from app.models.registry import AgentDefinition
    from app.services.prompt_builder import build_agent_prompt

    agent = await db_session.get(AgentDefinition, "no_soul_agent")
    prompt = await build_agent_prompt(db_session, agent)

    assert "SOUL" not in prompt


async def test_prompt_builder_forbidden_effects_merged(client, db_session):
    """Forbidden effects from family + agent should be merged."""
    await _seed_family_and_skill(client)
    await client.post("/api/agents", json={
        "id": "effects_agent",
        "name": "Effects Agent",
        "family_id": "analysis",
        "purpose": "Test forbidden effects merge",
        "forbidden_effects": ["write", "act"],
    })

    from app.models.registry import AgentDefinition
    from app.services.prompt_builder import build_agent_prompt

    agent = await db_session.get(AgentDefinition, "effects_agent")
    prompt = await build_agent_prompt(db_session, agent)

    assert "RUNTIME CONTEXT" in prompt
    # Family has ["publish", "approve"], agent has ["write", "act"]
    assert "publish" in prompt
    assert "approve" in prompt
    assert "write" in prompt
    assert "act" in prompt
