"""Tests for EffectClassifier — LLM-based MCP tool effect classification."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.effect_classifier import EffectClassifier


@pytest.fixture
def classifier():
    """Fresh classifier (empty cache) per test."""
    return EffectClassifier()


class TestHeuristicFallback:
    def test_write_prefix(self, classifier):
        assert classifier._heuristic_classify("write_file") == ["write"]

    def test_create_prefix(self, classifier):
        assert classifier._heuristic_classify("create_record") == ["write"]

    def test_delete_prefix(self, classifier):
        assert classifier._heuristic_classify("delete_item") == ["write"]

    def test_search_prefix(self, classifier):
        assert classifier._heuristic_classify("search_web") == ["search"]

    def test_read_prefix(self, classifier):
        assert classifier._heuristic_classify("read_document") == ["read"]

    def test_get_prefix(self, classifier):
        assert classifier._heuristic_classify("get_weather") == ["read"]

    def test_send_prefix(self, classifier):
        assert classifier._heuristic_classify("send_email") == ["act"]

    def test_unknown_tool(self, classifier):
        assert classifier._heuristic_classify("do_something_weird") == ["compute"]


class TestClassifyWithLLM:
    @pytest.mark.asyncio
    async def test_classify_single_effect(self, classifier):
        with patch.object(classifier, "_call_llm_sync", new=MagicMock(return_value="write")):
            result = await classifier.classify("save_document", {})
        assert result == ["write"]

    @pytest.mark.asyncio
    async def test_classify_compound_effects(self, classifier):
        with patch.object(classifier, "_call_llm_sync", new=MagicMock(return_value="write,act")):
            result = await classifier.classify("publish_and_notify", {})
        assert "write" in result
        assert "act" in result

    @pytest.mark.asyncio
    async def test_classify_uses_cache_on_second_call(self, classifier):
        mock_llm = MagicMock(return_value="read")
        with patch.object(classifier, "_call_llm_sync", new=mock_llm):
            await classifier.classify("get_data", {})
            await classifier.classify("get_data", {"key": "val"})
        assert mock_llm.call_count == 1  # second call hits cache

    @pytest.mark.asyncio
    async def test_classify_invalid_llm_response_uses_heuristic(self, classifier):
        with patch.object(classifier, "_call_llm_sync", new=MagicMock(return_value="destroy")):
            result = await classifier.classify("delete_all", {})
        assert result == ["write"]  # heuristic for delete_*

    @pytest.mark.asyncio
    async def test_classify_partial_invalid_response_filters_invalid(self, classifier):
        with patch.object(classifier, "_call_llm_sync", new=MagicMock(return_value="write,destroy")):
            result = await classifier.classify("write_and_destroy", {})
        assert result == ["write"]  # "destroy" filtered, "write" kept

    @pytest.mark.asyncio
    async def test_classify_llm_failure_uses_heuristic(self, classifier):
        with patch.object(classifier, "_call_llm_sync", new=MagicMock(side_effect=Exception("timeout"))):
            result = await classifier.classify("send_notification", {})
        assert result == ["act"]  # heuristic for send_*

    @pytest.mark.asyncio
    async def test_cache_populated_after_classify(self, classifier):
        with patch.object(classifier, "_call_llm_sync", new=MagicMock(return_value="search")):
            await classifier.classify("query_index", {})
        assert "query_index" in classifier._cache
        assert classifier._cache["query_index"] == ["search"]

    @pytest.mark.asyncio
    async def test_concurrent_classify_llm_failure_both_get_heuristic(self, classifier):
        """Both concurrent callers must get heuristic, not CancelledError."""
        with patch.object(classifier, "_call_llm_sync", new=MagicMock(side_effect=Exception("LLM down"))):
            results = await asyncio.gather(
                classifier.classify("send_alert", {}),
                classifier.classify("send_alert", {}),
                return_exceptions=True,
            )
        # Both should get heuristic result ["act"], not CancelledError
        assert results[0] == ["act"]
        assert results[1] == ["act"]
