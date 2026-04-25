"""Regression tests for BUG-2 word_test_agent write bypass."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.registry import AgentDefinition
from app.services.effect_classifier import EffectClassifier
from app.services.guarded_mcp_executor import guarded_invoke_mcp
from scripts.create_word_test_agent import AGENT


def test_tc_wordtest_001_heuristic_maps_write_doc_to_write() -> None:
    """TC-WORDTEST-001: write_doc must map to the write effect."""
    classifier = EffectClassifier()

    assert classifier._heuristic_classify("write_doc") == ["write"]


@pytest.mark.asyncio
async def test_tc_wordtest_002_executor_denies_write_doc_for_write_forbidden_agent() -> None:
    """TC-WORDTEST-002: guarded executor must deny write_doc when write is forbidden."""
    db = MagicMock()
    agent = MagicMock(spec=AgentDefinition)
    agent.forbidden_effects = ["write"]
    db.get = AsyncMock(return_value=agent)
    db.add = MagicMock()
    db.flush = AsyncMock()

    classifier = EffectClassifier()

    with patch.object(classifier, "_call_llm_sync", side_effect=RuntimeError("llm down")), \
        patch("app.services.guarded_mcp_executor.get_classifier", return_value=classifier), \
        patch("app.services.guarded_mcp_executor.invoke_mcp", new_callable=AsyncMock) as mock_invoke, \
        patch("app.services.guarded_mcp_executor.emit_event", new_callable=AsyncMock):
        result = await guarded_invoke_mcp(
            db=db,
            run_id="run_bug2",
            mcp_id="mcp_word",
            calling_agent_id="word_test_agent",
            tool_action="write_doc",
            tool_kwargs={"doc_id": "abc", "content": "hello"},
        )

    assert result.status == "denied"
    mock_invoke.assert_not_called()


def test_tc_wordtest_003_agent_forbidden_effects_contains_write() -> None:
    """TC-WORDTEST-003: AGENT.forbidden_effects contains write."""
    assert "write" in AGENT["forbidden_effects"]


def test_tc_wordtest_004_prompt_prohibits_write_doc() -> None:
    """TC-WORDTEST-004: prompt does not invite write_doc and explicitly prohibits it."""
    prompt = AGENT["prompt_content"].lower()

    assert "do not call write_doc" in prompt
    assert "this agent is read-only" in prompt


def test_tc_wordtest_005_routing_keywords_excludes_write_doc() -> None:
    """TC-WORDTEST-005: write_doc is absent from routing keywords."""
    routing_keywords = AGENT["selection_hints"]["routing_keywords"]

    assert "write_doc" not in routing_keywords


def test_tc_wordtest_006_purpose_and_description_are_read_only() -> None:
    """TC-WORDTEST-006: purpose/description communicate read-only intent."""
    purpose = AGENT["purpose"].lower()
    description = AGENT["description"].lower()

    assert "lecture seule" in purpose
    assert "write_doc" in purpose
    assert "read-only" in description
    assert "write" not in description
