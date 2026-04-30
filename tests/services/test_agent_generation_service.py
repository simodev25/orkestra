"""Service tests for LLM-backed agent generation with fallback."""

from __future__ import annotations

import json

import pytest

from app.schemas.agent import AgentGenerationRequest, McpCatalogSummary
from app.services import agent_generation_service
from app.services.agent_generation_service import AgentGenerationContext


def _mk_request() -> AgentGenerationRequest:
    return AgentGenerationRequest(
        intent="Generate an agent that analyzes public procurement compliance risks",
        use_case="procurement_compliance",
        preferred_family="analyst",
        preferred_skill_ids=["document_analysis"],
        constraints="No direct write actions",
    )


def _mk_catalog(size: int = 3) -> list[McpCatalogSummary]:
    return [
        McpCatalogSummary(
            id=f"mcp_{i}",
            name=f"MCP {i}",
            purpose=f"Purpose {i}",
            effect_type="read",
            criticality="medium",
            approval_required=False,
            obot_state="active",
            orkestra_state="enabled",
        )
        for i in range(size)
    ]


def _mk_context() -> AgentGenerationContext:
    return AgentGenerationContext(
        families=[
            {"id": "analyst", "label": "Analyst", "status": "active"},
            {"id": "reviewer", "label": "Reviewer", "status": "active"},
        ],
        skills=[
            {"skill_id": "document_analysis", "status": "active", "allowed_families": ["analyst"]},
            {"skill_id": "source_comparison", "status": "active", "allowed_families": ["analyst", "reviewer"]},
        ],
        similar_agents=[
            {"id": f"similar_{i}", "name": f"Similar {i}", "family_id": "analyst", "purpose": "Analyze evidence"}
            for i in range(7)
        ],
    )


def _valid_llm_draft_dict() -> dict:
    return {
        "agent_id": "llm_generated_agent",
        "name": "LLM Generated Agent",
        "family_id": "analyst",
        "purpose": "Analyze procurement risks",
        "description": "Analyzes procurement and compliance evidence.",
        "skill_ids": ["document_analysis", "source_comparison"],
        "selection_hints": {"routing_keywords": ["procurement", "risk"], "workflow_ids": [], "requires_grounded_evidence": True},
        "allowed_mcps": ["mcp_0", "mcp_1"],
        "forbidden_effects": ["act"],
        "input_contract_ref": "contracts/llm_generated_agent.input.v1",
        "output_contract_ref": "contracts/llm_generated_agent.output.v1",
        "criticality": "medium",
        "cost_profile": "medium",
        "limitations": ["Do not execute unauthorized actions."],
        "prompt_content": "Evidence-first behavior.",
        "skills_content": "document_analysis: analyze docs",
        "owner": "agent-registry",
        "version": "1.0.0",
        "status": "draft",
        "suggested_missing_mcps": [],
        "mcp_rationale": {"mcp_0": "Matches read needs", "mcp_1": "Supports legal lookup"},
        "pipeline_agent_ids": [],
        "routing_mode": "sequential",
    }


def test_build_generation_prompt_includes_context_and_caps_similar_agents():
    req = _mk_request()
    catalog = _mk_catalog(60)
    ctx = _mk_context()

    prompt = agent_generation_service.build_generation_prompt(req, catalog, ctx)

    assert "mcp_catalog_omitted_count" in prompt
    assert "similar_agents" in prompt
    # Ensure cap is represented by omitting extra MCPs when > 50
    assert "mcp_59" not in prompt


@pytest.mark.asyncio
async def test_generate_agent_draft_with_fallback_llm_success(monkeypatch, tmp_path, db_session):
    req = _mk_request()
    catalog = _mk_catalog()
    ctx = _mk_context()
    expected = _valid_llm_draft_dict()

    monkeypatch.setattr(agent_generation_service, "_TRACE_DIR", tmp_path)

    async def _fake_call_llm(prompt: str, db):
        return json.dumps(expected)

    monkeypatch.setattr(agent_generation_service, "_call_llm", _fake_call_llm)

    draft, source = await agent_generation_service.generate_agent_draft_with_fallback(
        db_session, req, catalog, ctx
    )

    assert source == "llm"
    assert draft.agent_id == "llm_generated_agent"
    assert draft.family_id == "analyst"
    traces = list(tmp_path.glob("*.json"))
    assert traces


@pytest.mark.asyncio
async def test_generate_agent_draft_with_fallback_on_llm_error(monkeypatch, tmp_path, db_session):
    req = _mk_request()
    catalog = _mk_catalog()
    ctx = _mk_context()

    monkeypatch.setattr(agent_generation_service, "_TRACE_DIR", tmp_path)

    async def _boom(prompt: str, db):
        raise TimeoutError("timed out")

    monkeypatch.setattr(agent_generation_service, "_call_llm", _boom)

    draft, source = await agent_generation_service.generate_agent_draft_with_fallback(
        db_session, req, catalog, ctx
    )

    assert source == "heuristic_template"
    assert draft.status == "draft"
    traces = list(tmp_path.glob("*.json"))
    assert traces
    payload = json.loads(traces[0].read_text())
    assert payload["fallback_reason"]


@pytest.mark.asyncio
async def test_generate_agent_draft_with_fallback_on_invalid_json(monkeypatch, tmp_path, db_session):
    req = _mk_request()
    catalog = _mk_catalog()
    ctx = _mk_context()

    monkeypatch.setattr(agent_generation_service, "_TRACE_DIR", tmp_path)

    async def _invalid(prompt: str, db):
        return "not-json"

    monkeypatch.setattr(agent_generation_service, "_call_llm", _invalid)

    draft, source = await agent_generation_service.generate_agent_draft_with_fallback(
        db_session, req, catalog, ctx
    )

    assert source == "heuristic_template"
    assert draft.allowed_mcps is not None


@pytest.mark.asyncio
async def test_generate_agent_draft_normalizes_unknown_family_and_skills(monkeypatch, tmp_path, db_session):
    req = _mk_request()
    catalog = _mk_catalog()
    ctx = _mk_context()
    raw = _valid_llm_draft_dict()
    raw["family_id"] = "unknown_family"
    raw["skill_ids"] = ["unknown_skill", "source_comparison"]
    raw["allowed_mcps"] = ["mcp_0", "unknown_mcp"]

    monkeypatch.setattr(agent_generation_service, "_TRACE_DIR", tmp_path)

    async def _fake(prompt: str, db):
        return json.dumps(raw)

    monkeypatch.setattr(agent_generation_service, "_call_llm", _fake)

    draft, source = await agent_generation_service.generate_agent_draft_with_fallback(
        db_session, req, catalog, ctx
    )

    assert source == "llm"
    assert draft.family_id in {"analyst", "reviewer"}
    assert "unknown_skill" not in draft.skill_ids
    assert "unknown_mcp" not in draft.allowed_mcps
