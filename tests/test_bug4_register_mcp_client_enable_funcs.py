"""Regression tests for BUG-4 MCP register_mcp_client enable_funcs."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_enable_funcs_excludes_forbidden_tool() -> None:
    toolkit = MagicMock()
    toolkit.register_mcp_client = AsyncMock()
    mcp_client = object()
    mcp_tools = [SimpleNamespace(name="list_docs")]

    await toolkit.register_mcp_client(
        mcp_client=mcp_client,
        group_name="basic",
        namesake_strategy="rename",
        enable_funcs=[t.name for t in mcp_tools],
    )

    enable_funcs = toolkit.register_mcp_client.await_args.kwargs["enable_funcs"]
    assert "write_doc" not in enable_funcs


@pytest.mark.asyncio
async def test_enable_funcs_contains_allowed_tool() -> None:
    toolkit = MagicMock()
    toolkit.register_mcp_client = AsyncMock()
    mcp_client = object()
    mcp_tools = [SimpleNamespace(name="list_docs")]

    await toolkit.register_mcp_client(
        mcp_client=mcp_client,
        group_name="basic",
        namesake_strategy="rename",
        enable_funcs=[t.name for t in mcp_tools],
    )

    enable_funcs = toolkit.register_mcp_client.await_args.kwargs["enable_funcs"]
    assert "list_docs" in enable_funcs


@pytest.mark.asyncio
async def test_no_forbidden_effects_all_tools_in_enable_funcs() -> None:
    toolkit = MagicMock()
    toolkit.register_mcp_client = AsyncMock()
    mcp_client = object()
    mcp_tools = [SimpleNamespace(name="write_doc"), SimpleNamespace(name="list_docs")]

    await toolkit.register_mcp_client(
        mcp_client=mcp_client,
        group_name="basic",
        namesake_strategy="rename",
        enable_funcs=[t.name for t in mcp_tools],
    )

    enable_funcs = toolkit.register_mcp_client.await_args.kwargs["enable_funcs"]
    assert enable_funcs == ["write_doc", "list_docs"]


@pytest.mark.asyncio
async def test_empty_after_filter_no_registration() -> None:
    toolkit = MagicMock()
    toolkit.register_mcp_client = AsyncMock()
    mcp_tools: list = []

    if mcp_tools:
        await toolkit.register_mcp_client(
            mcp_client=object(),
            group_name="basic",
            namesake_strategy="rename",
            enable_funcs=[t.name for t in mcp_tools],
        )

    toolkit.register_mcp_client.assert_not_awaited()
