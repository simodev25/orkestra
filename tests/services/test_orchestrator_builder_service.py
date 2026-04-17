"""Unit tests for orchestrator_builder_service (LLM-independent parts)."""
import pytest
from app.services.orchestrator_builder_service import (
    _build_agents_block,
    _parse_llm_json,
    _slugify_name,
)


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
