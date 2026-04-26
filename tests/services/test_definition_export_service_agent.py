import pytest


@pytest.mark.asyncio
async def test_export_agent_returns_canonical_payload(db_session):
    from app.models.family import FamilyDefinition
    from app.models.registry import AgentDefinition
    from app.services.definition_export_service import export_definition

    db_session.add(FamilyDefinition(id="analysis", label="Analysis", status="active"))
    db_session.add(
        AgentDefinition(
            id="budget_fit_agent",
            name="Budget Fit Agent",
            family_id="analysis",
            purpose="Scoring budget fit",
            description="Deterministic scoring",
            selection_hints={"workflow_ids": ["hotel_pipeline"]},
            allowed_mcps=[],
            forbidden_effects=["write"],
            allow_code_execution=False,
            criticality="medium",
            cost_profile="low",
            llm_provider="ollama",
            llm_model="mistral",
            limitations=["No external calls"],
            prompt_content="Prompt",
            skills_content=None,
            version="1.0.0",
            status="draft",
        )
    )
    await db_session.commit()

    exported = await export_definition(db_session, kind="agent", definition_id="budget_fit_agent")

    assert exported["kind"] == "agent"
    assert exported["schema_version"] == "v1"
    assert exported["id"] == "budget_fit_agent"
    assert exported["name"] == "Budget Fit Agent"
    assert exported["version"] == "1.0.0"
