"""Regression tests for BUG-3 forbidden-effects enforcement."""

import logging
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.agent_factory import _enforce_forbidden_effects_on_mcp_tools


@pytest.mark.asyncio
async def test_forbidden_tool_excluded_without_run_id() -> None:
    """BUG-3: forbidden tools are excluded even without test_run_id."""
    agent_def = SimpleNamespace(id="agent_bug3", forbidden_effects=["write"])
    tools = [SimpleNamespace(name="write_doc"), SimpleNamespace(name="list_docs")]

    classifier = MagicMock()
    classifier.classify = AsyncMock(
        side_effect=lambda tool_name, _: ["write"] if tool_name == "write_doc" else ["read"]
    )

    with patch("app.services.effect_classifier.get_classifier", return_value=classifier):
        filtered = await _enforce_forbidden_effects_on_mcp_tools(
            agent_def=agent_def,
            mcp_id="mcp_docs",
            mcp_tools=tools,
            test_run_id=None,
            db=None,
        )

    assert [t.name for t in filtered] == ["list_docs"]


@pytest.mark.asyncio
async def test_no_forbidden_effects_all_tools_registered() -> None:
    """Without forbidden_effects, enforcement must keep all tools unchanged."""
    agent_def = SimpleNamespace(id="agent_bug3", forbidden_effects=None)
    tools = [SimpleNamespace(name="write_doc"), SimpleNamespace(name="list_docs")]

    with patch("app.services.effect_classifier.get_classifier") as mock_gc:
        filtered = await _enforce_forbidden_effects_on_mcp_tools(
            agent_def=agent_def,
            mcp_id="mcp_docs",
            mcp_tools=tools,
            test_run_id=None,
            db=None,
        )

    assert [t.name for t in filtered] == ["write_doc", "list_docs"]
    mock_gc.assert_not_called()


def test_guarded_mcp_executor_deleted() -> None:
    """BUG-3: dead guarded executor module must be removed."""
    repo_root = Path(__file__).resolve().parents[1]
    assert os.path.exists(repo_root / "app/services/guarded_mcp_executor.py") is False


@pytest.mark.asyncio
async def test_warning_logged_without_run_id(caplog: pytest.LogCaptureFixture) -> None:
    """Blocking outside Test Lab should emit WARNING logs (no DB writes)."""
    agent_def = SimpleNamespace(id="agent_bug3", forbidden_effects=["write"])
    tools = [SimpleNamespace(name="write_doc")]

    classifier = MagicMock()
    classifier.classify = AsyncMock(return_value=["write"])

    with patch("app.services.effect_classifier.get_classifier", return_value=classifier):
        with caplog.at_level(logging.WARNING, logger="app.services.agent_factory"):
            filtered = await _enforce_forbidden_effects_on_mcp_tools(
                agent_def=agent_def,
                mcp_id="mcp_docs",
                mcp_tools=tools,
                test_run_id=None,
                db=None,
            )

    assert filtered == []
    assert any(
        "[EffectEnforcement]" in rec.message
        and "tool=write_doc" in rec.message
        and "no run_id" in rec.message
        for rec in caplog.records
    )


@pytest.mark.asyncio
async def test_with_run_id_persists_denied_invocation_and_emits_event() -> None:
    """When run context exists, denied tools keep previous Test Lab audit behavior."""
    agent_def = SimpleNamespace(id="agent_bug3", forbidden_effects=["write"])
    tools = [SimpleNamespace(name="write_doc")]
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    classifier = MagicMock()
    classifier.classify = AsyncMock(return_value=["write"])

    with patch("app.services.effect_classifier.get_classifier", return_value=classifier), patch(
        "app.services.event_service.emit_event", new_callable=AsyncMock
    ) as mock_emit:
        filtered = await _enforce_forbidden_effects_on_mcp_tools(
            agent_def=agent_def,
            mcp_id="mcp_docs",
            mcp_tools=tools,
            test_run_id="run_bug3",
            db=db,
        )

    assert filtered == []
    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    mock_emit.assert_awaited_once()
    assert mock_emit.await_args.kwargs["payload"]["reason"] == "forbidden_effect"
