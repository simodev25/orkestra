from app.services.definition_canonicalization import canonicalize_definition


def test_canonicalize_agent_excludes_runtime_fields():
    payload = {
        "kind": "agent",
        "schema_version": "v1",
        "id": "weather_agent",
        "name": "Weather Agent",
        "family_id": "analysis",
        "purpose": "Fournir un contexte météo.",
        "description": "desc",
        "skill_ids": ["skill_a", "skill_b"],
        "selection_hints": {"routing_keywords": ["meteo"]},
        "allowed_mcps": ["mcp_weather"],
        "forbidden_effects": ["write"],
        "allow_code_execution": False,
        "criticality": "low",
        "cost_profile": "low",
        "llm_provider": "ollama",
        "llm_model": "mistral",
        "limitations": ["sources externes"],
        "prompt_content": "prompt",
        "skills_content": None,
        "version": "1.0.0",
        "status": "draft",
        "usage_count": 42,
        "last_test_status": "passed",
        "last_validated_at": "2026-04-26T10:00:00Z",
        "created_at": "2026-04-26T10:00:00Z",
        "updated_at": "2026-04-26T10:00:00Z",
    }

    canonical = canonicalize_definition(payload)

    assert "usage_count" not in canonical
    assert "last_test_status" not in canonical
    assert "last_validated_at" not in canonical
    assert "created_at" not in canonical
    assert "updated_at" not in canonical
    assert canonical["version"] == "1.0.0"


def test_canonicalize_scenario_stable_ordered_output():
    payload = {
        "schema_version": "v1",
        "kind": "scenario",
        "definition_key": "weather_context_lisbon_may_2026",
        "name": "Weather Lisbon",
        "description": "desc",
        "agent_id": "weather_agent",
        "input_prompt": "Quel temps fera-t-il ?",
        "expected_tools": ["weather_tool"],
        "assertions": [{"type": "output_contains", "target": "forecast", "critical": True}],
        "timeout_seconds": 120,
        "max_iterations": 10,
        "tags": ["weather", "lisbon"],
        "enabled": True,
    }

    canonical = canonicalize_definition(payload)

    assert list(canonical.keys()) == sorted(canonical.keys())
    assert canonical["definition_key"] == "weather_context_lisbon_may_2026"
