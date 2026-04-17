"""Unit tests for orchestrator_builder_service (LLM-independent parts)."""
import json
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock

from app.services.orchestrator_builder_service import (
    _build_agents_block,
    _build_system_prompt,
    _parse_llm_json,
    _slugify_name,
)


# ── Valid draft JSON for mocking LLM responses ────────────────────────────────

VALID_DRAFT_JSON = {
    "agent_id": "test_orchestrator",
    "name": "Test Orchestrator",
    "family_id": "orchestration",
    "purpose": "Coordinate agents",
    "description": "Manages a sequential pipeline",
    "skill_ids": ["sequential_routing", "context_propagation"],
    "selection_hints": {
        "routing_keywords": ["orchestrate"],
        "workflow_ids": [],
        "use_case_hint": "Pipeline coordination",
        "requires_grounded_evidence": False,
    },
    "allowed_mcps": [],
    "forbidden_effects": [],
    "criticality": "medium",
    "cost_profile": "medium",
    "limitations": ["Depends on sub-agent reliability"],
    "prompt_content": "You are an orchestrator. Route tasks in sequence.",
    "skills_content": "sequential_routing: Routes tasks sequentially\ncontext_propagation: Passes context forward",
    "version": "1.0.0",
    "status": "draft",
}


def test_slugify_name():
    assert _slugify_name("Hotel Pipeline Orchestrator") == "hotel_pipeline_orchestrator"
    assert _slugify_name("  My Agent!! ") == "my_agent"
    assert len(_slugify_name("a" * 200)) <= 90  # DB column is String(100)


def test_parse_llm_json_clean():
    raw = '{"agent_id":"x","name":"X","family_id":"orchestration","purpose":"p","description":"d","skill_ids":["s"],"selection_hints":{"routing_keywords":["a"],"workflow_ids":[],"use_case_hint":"u","requires_grounded_evidence":false},"allowed_mcps":[],"forbidden_effects":[],"criticality":"medium","cost_profile":"medium","limitations":["l1"],"prompt_content":"pc","skills_content":"sc","version":"1.0.0","status":"draft"}'
    result = _parse_llm_json(raw)
    assert result["agent_id"] == "x"
    assert result["limitations"] == ["l1"]


def test_parse_llm_json_with_fences():
    raw = '```json\n{"agent_id":"x","name":"X","family_id":"orchestration","purpose":"p","description":"d","skill_ids":["s"],"selection_hints":{"routing_keywords":["a"],"workflow_ids":[],"use_case_hint":"u","requires_grounded_evidence":false},"allowed_mcps":[],"forbidden_effects":[],"criticality":"medium","cost_profile":"medium","limitations":["l1"],"prompt_content":"pc","skills_content":"sc","version":"1.0.0","status":"draft"}\n```'
    result = _parse_llm_json(raw)
    assert result["name"] == "X"


def test_parse_llm_json_invalid_raises():
    with pytest.raises(ValueError, match="LLM returned invalid JSON"):
        _parse_llm_json("not json at all")


def test_build_agents_block_ordered():
    agents = [
        {"id": "weather_agent", "name": "Weather Agent", "purpose": "Check weather", "description": "Searches forecasts", "limitations": ["7-day limit"]},
        {"id": "budget_agent", "name": "Budget Agent", "purpose": "Score budget", "description": "Evaluates fit", "limitations": []},
    ]
    block = _build_agents_block(agents)
    assert "1. weather_agent" in block
    assert "2. budget_agent" in block
    assert "Check weather" in block


# ── Group 1: Additional _slugify_name edge cases ──────────────────────────────

def test_slugify_name_already_snake_case():
    assert _slugify_name("my_agent") == "my_agent"


def test_slugify_name_numbers_preserved():
    assert _slugify_name("agent2024") == "agent2024"


def test_slugify_name_empty_string():
    assert _slugify_name("") == "orchestrator"


# ── Group 2: Additional _build_agents_block edge cases ───────────────────────

def test_build_agents_block_limitations_truncated():
    agents = [
        {
            "id": "multi_agent",
            "name": "Multi Agent",
            "purpose": "Does many things",
            "description": "A very capable agent",
            "limitations": [
                "limit_one",
                "limit_two",
                "limit_three",
                "limit_four",
                "limit_five",
            ],
        }
    ]
    block = _build_agents_block(agents)
    # Only 3 limitations should appear joined by semicolons
    assert "limit_four" not in block
    assert "limit_five" not in block
    # At most 2 semicolons (3 items → 2 separators)
    assert block.count(";") <= 2


def test_build_agents_block_empty_list():
    block = _build_agents_block([])
    assert block == ""


# ── Group 3: Additional _parse_llm_json edge cases ───────────────────────────

def test_parse_llm_json_embedded_in_text():
    inner = (
        '{"agent_id":"x","name":"X","family_id":"orchestration","purpose":"p",'
        '"description":"d","skill_ids":["s"],'
        '"selection_hints":{"routing_keywords":["a"],"workflow_ids":[],'
        '"use_case_hint":"u","requires_grounded_evidence":false},'
        '"allowed_mcps":[],"forbidden_effects":[],'
        '"criticality":"medium","cost_profile":"medium","limitations":["l1"],'
        '"prompt_content":"pc","skills_content":"sc","version":"1.0.0","status":"draft"}'
    )
    raw = f"Here is your JSON: {inner} That's all."
    result = _parse_llm_json(raw)
    assert result["agent_id"] == "x"
    assert result["name"] == "X"


# ── Group 4: _build_system_prompt tests (pure, no DB) ────────────────────────

def _make_agents_block() -> str:
    return _build_agents_block([
        {"id": "agent_a", "name": "Agent A", "purpose": "Do A", "description": "Does A things", "limitations": []},
    ])


def test_build_system_prompt_contains_name():
    block = _make_agents_block()
    result = _build_system_prompt(
        agent_block=block,
        orchestrator_name="Hotel Pipeline Orchestrator",
        routing_strategy="sequential",
        user_instructions=None,
        use_case_description=None,
        is_auto_mode=False,
    )
    assert "Hotel Pipeline Orchestrator" in result
    assert "hotel_pipeline_orchestrator" in result


def test_build_system_prompt_with_user_instructions():
    block = _make_agents_block()
    result = _build_system_prompt(
        agent_block=block,
        orchestrator_name="My Orchestrator",
        routing_strategy="sequential",
        user_instructions="Prioritize speed over accuracy.",
        use_case_description=None,
        is_auto_mode=False,
    )
    assert "ADDITIONAL INSTRUCTIONS FROM USER" in result
    assert "Prioritize speed over accuracy." in result


def test_build_system_prompt_without_user_instructions():
    block = _make_agents_block()
    result = _build_system_prompt(
        agent_block=block,
        orchestrator_name="My Orchestrator",
        routing_strategy="sequential",
        user_instructions=None,
        use_case_description=None,
        is_auto_mode=False,
    )
    assert "ADDITIONAL INSTRUCTIONS FROM USER" not in result


def test_build_system_prompt_auto_mode():
    block = _make_agents_block()
    result = _build_system_prompt(
        agent_block=block,
        orchestrator_name="Auto Orchestrator",
        routing_strategy="sequential",
        user_instructions=None,
        use_case_description="Find the best hotel deals.",
        is_auto_mode=True,
    )
    assert "USER'S PIPELINE DESCRIPTION" in result
    assert "Find the best hotel deals." in result


def test_build_system_prompt_manual_mode_no_use_case_section():
    block = _make_agents_block()
    result = _build_system_prompt(
        agent_block=block,
        orchestrator_name="Manual Orchestrator",
        routing_strategy="sequential",
        user_instructions=None,
        use_case_description="Should not appear",
        is_auto_mode=False,
    )
    assert "USER'S PIPELINE DESCRIPTION" not in result


# ── Group 5: generate_orchestrator integration tests ─────────────────────────

async def _seed_family_and_agents(db_session):
    """Seed orchestration family + 2 test agents in DB for integration tests."""
    from app.models.registry import AgentDefinition
    from app.models.family import FamilyDefinition

    family = FamilyDefinition(id="analysis", label="Analysis", status="active")
    db_session.add(family)

    agent1 = AgentDefinition(
        id="agent_alpha", name="Agent Alpha", family_id="analysis",
        purpose="Does alpha things", description="Alpha description",
        status="designed", version="1.0.0",
    )
    agent2 = AgentDefinition(
        id="agent_beta", name="Agent Beta", family_id="analysis",
        purpose="Does beta things", description="Beta description",
        status="designed", version="1.0.0",
    )
    db_session.add(agent1)
    db_session.add(agent2)
    await db_session.commit()


async def test_generate_orchestrator_manual_mode_calls_llm(db_session):
    from app.schemas.agent import OrchestratorGenerationRequest
    from app.services.orchestrator_builder_service import generate_orchestrator

    await _seed_family_and_agents(db_session)

    req = OrchestratorGenerationRequest(
        name="Test Orchestrator",
        agent_ids=["agent_alpha", "agent_beta"],
    )

    with patch(
        "app.services.orchestrator_builder_service._call_llm",
        new_callable=AsyncMock,
        return_value=json.dumps(VALID_DRAFT_JSON),
    ) as mock_llm:
        draft, selected_ids = await generate_orchestrator(db_session, req)

    assert selected_ids == ["agent_alpha", "agent_beta"]
    assert draft.name == "Test Orchestrator"
    assert mock_llm.call_count == 1


async def test_generate_orchestrator_auto_mode_selects_all_agents(db_session):
    from app.schemas.agent import OrchestratorGenerationRequest
    from app.services.orchestrator_builder_service import generate_orchestrator

    await _seed_family_and_agents(db_session)

    req = OrchestratorGenerationRequest(
        name="Auto Orchestrator",
        agent_ids=[],
        use_case_description="Find hotels",
    )

    with patch(
        "app.services.orchestrator_builder_service._call_llm",
        new_callable=AsyncMock,
        return_value=json.dumps(VALID_DRAFT_JSON),
    ):
        draft, selected_ids = await generate_orchestrator(db_session, req)

    assert len(selected_ids) == 2
    assert draft.family_id == "orchestration"


async def test_generate_orchestrator_missing_agent_raises(db_session):
    from app.schemas.agent import OrchestratorGenerationRequest
    from app.services.orchestrator_builder_service import generate_orchestrator

    await _seed_family_and_agents(db_session)

    req = OrchestratorGenerationRequest(
        name="Broken Orchestrator",
        agent_ids=["agent_alpha", "nonexistent_agent"],
    )

    with pytest.raises(ValueError, match="not found"):
        await generate_orchestrator(db_session, req)


async def test_generate_orchestrator_llm_failure_raises(db_session):
    from app.schemas.agent import OrchestratorGenerationRequest
    from app.services.orchestrator_builder_service import generate_orchestrator

    await _seed_family_and_agents(db_session)

    req = OrchestratorGenerationRequest(
        name="Failing Orchestrator",
        agent_ids=["agent_alpha", "agent_beta"],
    )

    with patch(
        "app.services.orchestrator_builder_service._call_llm",
        new_callable=AsyncMock,
        side_effect=RuntimeError("connection refused"),
    ):
        with pytest.raises(RuntimeError):
            await generate_orchestrator(db_session, req)


async def test_generate_orchestrator_fills_empty_limitations(db_session):
    from app.schemas.agent import OrchestratorGenerationRequest
    from app.services.orchestrator_builder_service import generate_orchestrator

    await _seed_family_and_agents(db_session)

    draft_no_limitations = {**VALID_DRAFT_JSON, "limitations": []}

    req = OrchestratorGenerationRequest(
        name="Test Orchestrator",
        agent_ids=["agent_alpha", "agent_beta"],
    )

    with patch(
        "app.services.orchestrator_builder_service._call_llm",
        new_callable=AsyncMock,
        return_value=json.dumps(draft_no_limitations),
    ):
        draft, _ = await generate_orchestrator(db_session, req)

    assert len(draft.limitations) > 0


async def test_generate_orchestrator_fills_empty_skills_content(db_session):
    from app.schemas.agent import OrchestratorGenerationRequest
    from app.services.orchestrator_builder_service import generate_orchestrator

    await _seed_family_and_agents(db_session)

    draft_no_skills = {**VALID_DRAFT_JSON, "skills_content": ""}

    req = OrchestratorGenerationRequest(
        name="Test Orchestrator",
        agent_ids=["agent_alpha", "agent_beta"],
    )

    with patch(
        "app.services.orchestrator_builder_service._call_llm",
        new_callable=AsyncMock,
        return_value=json.dumps(draft_no_skills),
    ):
        draft, _ = await generate_orchestrator(db_session, req)

    assert draft.skills_content != ""
