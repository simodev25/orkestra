"""Tests for MCP validation engine."""

import pytest
from app.models.registry import MCPDefinition
from app.models.enums import MCPStatus
from app.services.mcp_validation_engine import validate_mcp, validate_lifecycle_gate


async def _create_mcp(db_session, **overrides):
    defaults = {
        "id": "test_mcp",
        "name": "Test MCP",
        "purpose": "Test MCP for validation tests",
        "effect_type": "read",
        "criticality": "medium",
        "timeout_seconds": 30,
        "retry_policy": "standard",
        "cost_profile": "low",
        "approval_required": False,
        "audit_required": True,
        "status": MCPStatus.DRAFT,
        "version": "1.0.0",
        "owner": "test_team",
        "allowed_agents": ["agent_a"],
        "input_contract_ref": "contracts/input.json",
        "output_contract_ref": "contracts/output.json",
    }
    defaults.update(overrides)
    mcp = MCPDefinition(**defaults)
    db_session.add(mcp)
    await db_session.flush()
    return mcp


class TestValidationRules:
    async def test_valid_mcp_passes(self, db_session):
        await _create_mcp(db_session)
        await db_session.commit()
        report = await validate_mcp(db_session, "test_mcp", include_integration=False)
        assert report.valid is True
        assert report.errors == 0
        assert report.score >= 90

    async def test_missing_purpose_fails(self, db_session):
        await _create_mcp(db_session, id="bad_purpose", purpose="abc")
        await db_session.commit()
        report = await validate_mcp(db_session, "bad_purpose", include_integration=False)
        assert any(f.rule_id == "STRUCT_001" for f in report.findings)

    async def test_write_without_approval_fails(self, db_session):
        await _create_mcp(db_session, id="write_no_approval",
                          effect_type="write", approval_required=False)
        await db_session.commit()
        report = await validate_mcp(db_session, "write_no_approval", include_integration=False)
        gov_errors = [f for f in report.findings if f.rule_id == "GOV_001"]
        assert len(gov_errors) == 1
        assert gov_errors[0].severity == "error"

    async def test_act_without_high_criticality_warns(self, db_session):
        await _create_mcp(db_session, id="act_low_crit",
                          effect_type="act", criticality="low",
                          approval_required=True, audit_required=True)
        await db_session.commit()
        report = await validate_mcp(db_session, "act_low_crit", include_integration=False)
        assert any(f.rule_id == "GOV_003" for f in report.findings)

    async def test_high_criticality_without_audit_fails(self, db_session):
        await _create_mcp(db_session, id="high_no_audit",
                          criticality="high", audit_required=False)
        await db_session.commit()
        report = await validate_mcp(db_session, "high_no_audit", include_integration=False)
        assert any(f.rule_id == "GOV_002" for f in report.findings)

    async def test_no_allowed_agents_warns(self, db_session):
        await _create_mcp(db_session, id="no_agents", allowed_agents=[])
        await db_session.commit()
        report = await validate_mcp(db_session, "no_agents", include_integration=False)
        assert any(f.rule_id == "GOV_004" for f in report.findings)

    async def test_excessive_timeout_warns(self, db_session):
        await _create_mcp(db_session, id="slow_mcp", timeout_seconds=200)
        await db_session.commit()
        report = await validate_mcp(db_session, "slow_mcp", include_integration=False)
        assert any(f.rule_id == "RT_002" for f in report.findings)

    async def test_no_contracts_warns(self, db_session):
        await _create_mcp(db_session, id="no_contracts",
                          input_contract_ref=None, output_contract_ref=None)
        await db_session.commit()
        report = await validate_mcp(db_session, "no_contracts", include_integration=False)
        contract_findings = [f for f in report.findings if f.category == "contract"]
        assert len(contract_findings) == 2

    async def test_score_degrades_with_issues(self, db_session):
        await _create_mcp(db_session, id="many_issues",
                          purpose="abc", owner=None, description=None,
                          effect_type="write", approval_required=False,
                          allowed_agents=[], input_contract_ref=None,
                          output_contract_ref=None)
        await db_session.commit()
        report = await validate_mcp(db_session, "many_issues", include_integration=False)
        assert report.valid is False
        assert report.score < 50


class TestLifecycleGates:
    async def test_valid_mcp_can_go_active(self, db_session):
        await _create_mcp(db_session)
        await db_session.commit()
        report = await validate_lifecycle_gate(db_session, "test_mcp", "active")
        assert report.valid is True

    async def test_bad_mcp_blocked_from_active(self, db_session):
        await _create_mcp(db_session, id="bad_active",
                          effect_type="write", approval_required=False)
        await db_session.commit()
        report = await validate_lifecycle_gate(db_session, "bad_active", "active")
        assert report.valid is False
        assert report.errors > 0

    async def test_no_gate_for_draft(self, db_session):
        await _create_mcp(db_session, id="draft_mcp")
        await db_session.commit()
        report = await validate_lifecycle_gate(db_session, "draft_mcp", "draft")
        assert report.valid is True


class TestValidationAPI:
    async def test_validate_endpoint(self, client):
        await client.post("/api/mcps", json={
            "id": "api_val_mcp", "name": "API Val", "purpose": "API validation test MCP",
            "effect_type": "read", "allowed_agents": ["agent_a"],
        })
        resp = await client.post("/api/mcps/api_val_mcp/validate",
                                  json={"include_integration": False})
        assert resp.status_code == 200
        data = resp.json()
        assert "valid" in data
        assert "score" in data
        assert "findings" in data

    async def test_validate_gate_endpoint(self, client):
        await client.post("/api/mcps", json={
            "id": "gate_mcp", "name": "Gate", "purpose": "Gate test MCP",
            "effect_type": "read",
        })
        resp = await client.post("/api/mcps/gate_mcp/validate-gate/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "valid" in data

    async def test_validate_nonexistent_returns_404(self, client):
        resp = await client.post("/api/mcps/nonexistent/validate")
        assert resp.status_code == 404
