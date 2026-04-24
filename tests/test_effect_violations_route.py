"""Tests for GET /api/agents/{agent_id}/effect-violations"""

import pytest
from datetime import datetime, timezone

from app.models.invocation import MCPInvocation


async def _make_violation(
    db_session,
    calling_agent_id: str,
    run_id: str = "run_1",
    mcp_id: str = "write_mcp",
    effect_type: str = "write",
    status: str = "denied",
):
    inv = MCPInvocation(
        run_id=run_id,
        calling_agent_id=calling_agent_id,
        mcp_id=mcp_id,
        effect_type=effect_type,
        status=status,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(inv)
    await db_session.flush()
    return inv


class TestEffectViolationsRoute:
    @pytest.mark.asyncio
    async def test_violations_returns_only_agent_violations(self, client, db_session):
        """Only violations for this agent_id are returned, not others."""
        await _make_violation(db_session, calling_agent_id="agent_1", effect_type="write")
        await _make_violation(db_session, calling_agent_id="agent_1", effect_type="delete")
        await _make_violation(db_session, calling_agent_id="agent_2", effect_type="write")
        await db_session.commit()

        resp = await client.get("/api/agents/agent_1/effect-violations")
        assert resp.status_code == 200
        data = resp.json()
        # Verify only agent_1's violations returned (not agent_2's)
        assert len(data["violations"]) == 2
        # Verify structure is correct
        for v in data["violations"]:
            assert "effects" in v
            assert "blocked_at" in v

    @pytest.mark.asyncio
    async def test_violations_summary_counts(self, client, db_session):
        """Summary counts violations per effect type correctly."""
        await _make_violation(db_session, calling_agent_id="agent_1", effect_type="write")
        await _make_violation(db_session, calling_agent_id="agent_1", effect_type="write")
        await _make_violation(db_session, calling_agent_id="agent_1", effect_type="delete")
        await db_session.commit()

        resp = await client.get("/api/agents/agent_1/effect-violations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["write"] == 2
        assert data["summary"]["delete"] == 1

    @pytest.mark.asyncio
    async def test_violations_empty(self, client, db_session):
        """Returns {'violations': [], 'summary': {}} if no violations."""
        resp = await client.get("/api/agents/agent_no_violations/effect-violations")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"violations": [], "summary": {}}
