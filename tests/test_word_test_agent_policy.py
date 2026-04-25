"""Regression tests for BUG-2 word_test_agent write bypass."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.registry import AgentDefinition
from app.services.effect_classifier import EffectClassifier
from app.services.agent_factory import _enforce_forbidden_effects_on_mcp_tools
from scripts.create_word_test_agent import AGENT


def test_tc_wordtest_001_heuristic_maps_write_doc_to_write() -> None:
    """TC-WORDTEST-001: write_doc must map to the write effect."""
    classifier = EffectClassifier()

    assert classifier._heuristic_classify("write_doc") == ["write"]


@pytest.mark.asyncio
async def test_tc_wordtest_002_executor_denies_write_doc_for_write_forbidden_agent() -> None:
    """TC-WORDTEST-002: write_doc must be excluded when write is forbidden."""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    agent = MagicMock(spec=AgentDefinition)
    agent.id = "word_test_agent"
    agent.forbidden_effects = ["write"]

    tools = [
        SimpleNamespace(name="write_doc"),
        SimpleNamespace(name="list_docs"),
    ]

    classifier = EffectClassifier()

    with patch.object(classifier, "_call_llm_sync", side_effect=RuntimeError("llm down")), \
        patch("app.services.effect_classifier.get_classifier", return_value=classifier):
        result = await _enforce_forbidden_effects_on_mcp_tools(
            agent_def=agent,
            mcp_id="mcp_word",
            mcp_tools=tools,
            test_run_id=None,
            db=db,
        )

    assert [t.name for t in result] == ["list_docs"]


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
