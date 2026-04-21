"""Tests for guarded_invoke_mcp — AOP wrapper with forbidden-effects enforcement."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.models.invocation import MCPInvocation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(forbidden_effects):
    """Return a mock AgentDefinition with given forbidden_effects."""
    agent = MagicMock()
    agent.forbidden_effects = forbidden_effects
    return agent


def _make_denied_inv():
    """Return a mock MCPInvocation with status='denied'."""
    inv = MagicMock(spec=MCPInvocation)
    inv.status = "denied"
    return inv


def _make_db(agent=None):
    """Return a fully-mocked AsyncSession."""
    db = MagicMock()
    db.get = AsyncMock(return_value=agent)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGuardedInvokeMCP:

    @pytest.mark.asyncio
    async def test_blocks_forbidden_single_effect(self):
        """forbidden=['write'], classifier → ['write'] → returns MCPInvocation(status='denied')."""
        from app.services.guarded_mcp_executor import guarded_invoke_mcp

        agent = _make_agent(["write"])
        db = _make_db(agent)

        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=["write"])

        with patch("app.services.guarded_mcp_executor.get_classifier", return_value=mock_classifier), \
             patch("app.services.guarded_mcp_executor.emit_event", new_callable=AsyncMock), \
             patch("app.services.guarded_mcp_executor.invoke_mcp", new_callable=AsyncMock) as mock_invoke:

            result = await guarded_invoke_mcp(
                db=db,
                run_id="run_1",
                mcp_id="mcp_a",
                calling_agent_id="agent_x",
                tool_action="write_file",
                tool_kwargs={"path": "/tmp/x"},
            )

        assert result.status == "denied"
        mock_invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocks_forbidden_compound_effect(self):
        """forbidden=['act'], classifier → ['write','act'] → denied (any match)."""
        from app.services.guarded_mcp_executor import guarded_invoke_mcp

        agent = _make_agent(["act"])
        db = _make_db(agent)

        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=["write", "act"])

        with patch("app.services.guarded_mcp_executor.get_classifier", return_value=mock_classifier), \
             patch("app.services.guarded_mcp_executor.emit_event", new_callable=AsyncMock), \
             patch("app.services.guarded_mcp_executor.invoke_mcp", new_callable=AsyncMock) as mock_invoke:

            result = await guarded_invoke_mcp(
                db=db,
                run_id="run_1",
                mcp_id="mcp_a",
                calling_agent_id="agent_x",
                tool_action="publish_and_write",
                tool_kwargs={},
            )

        assert result.status == "denied"
        mock_invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_allows_permitted_effect(self):
        """forbidden=['write'], classifier → ['read'] → calls invoke_mcp (not denied)."""
        from app.services.guarded_mcp_executor import guarded_invoke_mcp

        agent = _make_agent(["write"])
        db = _make_db(agent)

        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=["read"])

        mock_result = MagicMock()
        mock_result.status = "completed"

        with patch("app.services.guarded_mcp_executor.get_classifier", return_value=mock_classifier), \
             patch("app.services.guarded_mcp_executor.emit_event", new_callable=AsyncMock), \
             patch("app.services.guarded_mcp_executor.invoke_mcp", new_callable=AsyncMock, return_value=mock_result) as mock_invoke:

            result = await guarded_invoke_mcp(
                db=db,
                run_id="run_1",
                mcp_id="mcp_a",
                calling_agent_id="agent_x",
                tool_action="read_document",
                tool_kwargs={},
            )

        mock_invoke.assert_called_once()
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_run_override_unblocks_effect(self):
        """forbidden=['write'], run_overrides=['write'] → calls invoke_mcp (not denied)."""
        from app.services.guarded_mcp_executor import guarded_invoke_mcp

        agent = _make_agent(["write"])
        db = _make_db(agent)

        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=["write"])

        mock_result = MagicMock()
        mock_result.status = "completed"

        with patch("app.services.guarded_mcp_executor.get_classifier", return_value=mock_classifier), \
             patch("app.services.guarded_mcp_executor.emit_event", new_callable=AsyncMock), \
             patch("app.services.guarded_mcp_executor.invoke_mcp", new_callable=AsyncMock, return_value=mock_result) as mock_invoke:

            result = await guarded_invoke_mcp(
                db=db,
                run_id="run_1",
                mcp_id="mcp_a",
                calling_agent_id="agent_x",
                tool_action="write_file",
                tool_kwargs={},
                run_effect_overrides=["write"],
            )

        mock_invoke.assert_called_once()
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_run_override_partial(self):
        """forbidden=['write','act'], run_overrides=['write'], classifier → ['act'] → denied."""
        from app.services.guarded_mcp_executor import guarded_invoke_mcp

        agent = _make_agent(["write", "act"])
        db = _make_db(agent)

        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=["act"])

        with patch("app.services.guarded_mcp_executor.get_classifier", return_value=mock_classifier), \
             patch("app.services.guarded_mcp_executor.emit_event", new_callable=AsyncMock), \
             patch("app.services.guarded_mcp_executor.invoke_mcp", new_callable=AsyncMock) as mock_invoke:

            result = await guarded_invoke_mcp(
                db=db,
                run_id="run_1",
                mcp_id="mcp_a",
                calling_agent_id="agent_x",
                tool_action="send_email",
                tool_kwargs={},
                run_effect_overrides=["write"],
            )

        assert result.status == "denied"
        mock_invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_forbidden_effects_configured(self):
        """forbidden=[] or None → no classifier call, delegates directly."""
        from app.services.guarded_mcp_executor import guarded_invoke_mcp

        for forbidden in [[], None]:
            agent = _make_agent(forbidden)
            db = _make_db(agent)

            mock_classifier = MagicMock()
            mock_classifier.classify = AsyncMock(return_value=["write"])

            mock_result = MagicMock()
            mock_result.status = "completed"

            with patch("app.services.guarded_mcp_executor.get_classifier", return_value=mock_classifier), \
                 patch("app.services.guarded_mcp_executor.emit_event", new_callable=AsyncMock), \
                 patch("app.services.guarded_mcp_executor.invoke_mcp", new_callable=AsyncMock, return_value=mock_result) as mock_invoke:

                result = await guarded_invoke_mcp(
                    db=db,
                    run_id="run_1",
                    mcp_id="mcp_a",
                    calling_agent_id="agent_x",
                    tool_action="write_file",
                    tool_kwargs={},
                )

            mock_classifier.classify.assert_not_called()
            mock_invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_event_on_block(self):
        """When denied → emit_event called with reason='forbidden_effect' and correct effects."""
        from app.services.guarded_mcp_executor import guarded_invoke_mcp

        agent = _make_agent(["write"])
        db = _make_db(agent)

        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=["write"])

        with patch("app.services.guarded_mcp_executor.get_classifier", return_value=mock_classifier), \
             patch("app.services.guarded_mcp_executor.emit_event", new_callable=AsyncMock) as mock_emit, \
             patch("app.services.guarded_mcp_executor.invoke_mcp", new_callable=AsyncMock):

            await guarded_invoke_mcp(
                db=db,
                run_id="run_42",
                mcp_id="mcp_b",
                calling_agent_id="agent_y",
                tool_action="write_file",
                tool_kwargs={},
            )

        mock_emit.assert_called_once()
        assert mock_emit.call_args.args[1] == "mcp.denied"  # event_type
        call_kwargs = mock_emit.call_args.kwargs
        assert call_kwargs["payload"]["reason"] == "forbidden_effect"
        assert call_kwargs["payload"]["effects"] == ["write"]

    @pytest.mark.asyncio
    async def test_calling_agent_id_stored(self):
        """Denied MCPInvocation.calling_agent_id == calling_agent_id."""
        from app.services.guarded_mcp_executor import guarded_invoke_mcp

        agent = _make_agent(["write"])
        db = _make_db(agent)

        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=["write"])

        added_objects = []

        def capture_add(obj):
            added_objects.append(obj)

        db.add = MagicMock(side_effect=capture_add)

        with patch("app.services.guarded_mcp_executor.get_classifier", return_value=mock_classifier), \
             patch("app.services.guarded_mcp_executor.emit_event", new_callable=AsyncMock), \
             patch("app.services.guarded_mcp_executor.invoke_mcp", new_callable=AsyncMock):

            await guarded_invoke_mcp(
                db=db,
                run_id="run_1",
                mcp_id="mcp_a",
                calling_agent_id="agent_special",
                tool_action="write_doc",
                tool_kwargs={},
            )

        assert len(added_objects) == 1
        inv = added_objects[0]
        assert isinstance(inv, MCPInvocation)
        assert inv.calling_agent_id == "agent_special"

    @pytest.mark.asyncio
    async def test_no_tool_action_skips_classifier(self):
        """tool_action=None → no classifier call, delegates directly."""
        from app.services.guarded_mcp_executor import guarded_invoke_mcp

        agent = _make_agent(["write"])
        db = _make_db(agent)

        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=["write"])

        mock_result = MagicMock()
        mock_result.status = "completed"

        with patch("app.services.guarded_mcp_executor.get_classifier", return_value=mock_classifier), \
             patch("app.services.guarded_mcp_executor.emit_event", new_callable=AsyncMock), \
             patch("app.services.guarded_mcp_executor.invoke_mcp", new_callable=AsyncMock, return_value=mock_result) as mock_invoke:

            result = await guarded_invoke_mcp(
                db=db,
                run_id="run_1",
                mcp_id="mcp_a",
                calling_agent_id="agent_x",
                tool_action=None,
                tool_kwargs={},
            )

        mock_classifier.classify.assert_not_called()
        mock_invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_blocked_effect_type_csv(self):
        """Denied with effects=['write','act'] → MCPInvocation.effect_type == 'write,act'."""
        from app.services.guarded_mcp_executor import guarded_invoke_mcp

        agent = _make_agent(["write", "act"])
        db = _make_db(agent)

        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=["write", "act"])

        added_objects = []

        def capture_add(obj):
            added_objects.append(obj)

        db.add = MagicMock(side_effect=capture_add)

        with patch("app.services.guarded_mcp_executor.get_classifier", return_value=mock_classifier), \
             patch("app.services.guarded_mcp_executor.emit_event", new_callable=AsyncMock), \
             patch("app.services.guarded_mcp_executor.invoke_mcp", new_callable=AsyncMock):

            await guarded_invoke_mcp(
                db=db,
                run_id="run_1",
                mcp_id="mcp_a",
                calling_agent_id="agent_x",
                tool_action="publish_and_write",
                tool_kwargs={},
            )

        assert len(added_objects) == 1
        inv = added_objects[0]
        assert isinstance(inv, MCPInvocation)
        assert set(inv.effect_type.split(",")) == {"write", "act"}
