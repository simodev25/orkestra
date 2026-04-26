import pytest
from pydantic import ValidationError

from app.schemas.definitions import validate_definition_payload


def test_validate_agent_definition_payload_v1():
    payload = {
        "kind": "agent",
        "schema_version": "v1",
        "id": "weather_agent",
        "name": "Weather Agent",
        "family_id": "analysis",
        "purpose": "Fournir des informations météo contextualisées.",
        "description": "Analyse météo.",
        "skill_ids": ["source_comparison"],
        "selection_hints": {"routing_keywords": ["weather"]},
        "allowed_mcps": ["weather_mcp"],
        "forbidden_effects": ["write"],
        "allow_code_execution": False,
        "criticality": "low",
        "cost_profile": "low",
        "llm_provider": "ollama",
        "llm_model": "mistral",
        "limitations": ["No real-time guarantee"],
        "prompt_content": "Prompt",
        "skills_content": None,
        "version": "1.0.0",
        "status": "draft",
    }

    definition = validate_definition_payload(payload)
    assert definition.kind == "agent"
    assert definition.id == "weather_agent"


def test_validate_orchestrator_definition_payload_v1():
    payload = {
        "kind": "orchestrator",
        "schema_version": "v1",
        "id": "hotel_pipeline_orchestrator",
        "name": "Hotel Pipeline Orchestrator",
        "family_id": "orchestration",
        "purpose": "Orchestrer les agents du pipeline hôtelier.",
        "description": "Pipeline séquentiel.",
        "skill_ids": ["sequential_routing"],
        "selection_hints": {"workflow_ids": ["hotel_pipeline"]},
        "allowed_mcps": [],
        "forbidden_effects": [],
        "allow_code_execution": False,
        "criticality": "medium",
        "cost_profile": "medium",
        "llm_provider": "ollama",
        "llm_model": "mistral",
        "limitations": [],
        "prompt_content": "Prompt",
        "skills_content": None,
        "version": "1.0.0",
        "status": "draft",
        "pipeline_definition": {
            "routing_mode": "sequential",
            "stages": [
                {"stage_id": "stay", "agent_id": "stay_discovery_agent", "required": True}
            ],
            "error_policy": "continue_on_partial_failure",
        },
    }

    definition = validate_definition_payload(payload)
    assert definition.kind == "orchestrator"
    assert definition.pipeline_definition.stages[0].agent_id == "stay_discovery_agent"


def test_validate_scenario_definition_payload_v1():
    payload = {
        "kind": "scenario",
        "schema_version": "v1",
        "definition_key": "weather_context_lisbon_may_2026",
        "name": "Weather Lisbon May 2026",
        "description": "Scenario météo",
        "agent_id": "weather_agent",
        "input_prompt": "Quel temps à Lisbonne en mai 2026 ?",
        "expected_tools": ["weather_mcp"],
        "assertions": [{"type": "output_contains", "target": "forecast", "critical": True}],
        "timeout_seconds": 120,
        "max_iterations": 10,
        "tags": ["weather", "lisbon"],
        "enabled": True,
    }

    definition = validate_definition_payload(payload)
    assert definition.kind == "scenario"
    assert definition.definition_key == "weather_context_lisbon_may_2026"


def test_reject_invalid_schema_version():
    payload = {
        "kind": "agent",
        "schema_version": "v2",
        "id": "weather_agent",
        "name": "Weather Agent",
        "family_id": "analysis",
        "purpose": "Fournir des informations météo contextualisées.",
        "criticality": "low",
        "cost_profile": "low",
        "version": "1.0.0",
        "status": "draft",
    }

    with pytest.raises(ValidationError):
        validate_definition_payload(payload)


def test_reject_orchestrator_without_pipeline_definition():
    payload = {
        "kind": "orchestrator",
        "schema_version": "v1",
        "id": "hotel_pipeline_orchestrator",
        "name": "Hotel Pipeline Orchestrator",
        "family_id": "orchestration",
        "purpose": "Orchestrer les agents du pipeline hôtelier.",
        "criticality": "medium",
        "cost_profile": "medium",
        "version": "1.0.0",
        "status": "draft",
    }

    with pytest.raises(ValidationError):
        validate_definition_payload(payload)
