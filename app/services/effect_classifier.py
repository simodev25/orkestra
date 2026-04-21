"""Effect Classifier — classifies MCP tool calls into effect types via LLM + heuristic fallback."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

EFFECT_TYPES = frozenset({"read", "search", "compute", "generate", "validate", "write", "act"})

_CLASSIFIER_SYSTEM = """Classify the MCP tool call into one or more of:
  read, search, compute, generate, validate, write, act

Definitions:
- read    : fetches/retrieves data, no mutation
- search  : queries/lookups, no mutation
- compute : pure calculation, no I/O side effects
- generate: produces new content (text, image, code)
- validate: checks/verifies, no mutation
- write   : creates, updates, or deletes data
- act     : triggers external action (email, API call, deploy, publish)

Reply with a comma-separated list of applicable effects (lowercase, no spaces after comma).
Examples: "write" or "write,act" or "read,compute"
No explanation — only the list."""


class EffectClassifier:
    """LLM-based tool effect classifier with process-level cache and heuristic fallback."""

    def __init__(self) -> None:
        self._cache: dict[str, list[str]] = {}

    async def classify(self, tool_name: str, args: dict[str, Any]) -> list[str]:
        """Return the list of effects for this tool call.

        Uses process-level cache keyed on tool_name (effects are stable per tool).
        Falls back to heuristic if LLM is unavailable or returns invalid output.
        """
        if tool_name in self._cache:
            return self._cache[tool_name]

        try:
            raw = await asyncio.wait_for(self._call_llm(tool_name, args), timeout=2.0)
            effects = [e.strip() for e in raw.split(",") if e.strip() in EFFECT_TYPES]
            if not effects:
                effects = self._heuristic_classify(tool_name)
        except Exception as exc:
            logger.warning("[EffectClassifier] LLM call failed for '%s': %s — using heuristic", tool_name, exc)
            effects = self._heuristic_classify(tool_name)

        self._cache[tool_name] = effects
        return effects

    async def _call_llm(self, tool_name: str, args: dict[str, Any]) -> str:
        """Call LLM to classify the tool effect. Returns raw string response."""
        from app.llm.provider import get_chat_model
        from agentscope.message import Msg

        model = get_chat_model()
        if model is None:
            raise RuntimeError("LLM model unavailable")

        args_summary = str(args)[:200] if args else ""
        user_content = f"tool={tool_name} args={args_summary}"

        response = model(
            [
                Msg(name="system", role="system", content=_CLASSIFIER_SYSTEM),
                Msg(name="user", role="user", content=user_content),
            ]
        )
        if hasattr(response, "text"):
            return response.text.strip().lower()
        return str(response).strip().lower()

    def _heuristic_classify(self, tool_name: str) -> list[str]:
        """Pattern-based fallback classifier."""
        name = tool_name.lower()
        if any(p in name for p in ("write", "create", "delete", "update", "save", "remove", "insert")):
            return ["write"]
        if any(p in name for p in ("search", "query", "find", "lookup", "filter")):
            return ["search"]
        if any(p in name for p in ("get", "fetch", "read", "list", "retrieve", "load")):
            return ["read"]
        if any(p in name for p in ("send", "post", "publish", "deploy", "email", "notify", "trigger")):
            return ["act"]
        if any(p in name for p in ("generate", "draft", "synthesize")):
            return ["generate"]
        if any(p in name for p in ("validate", "check", "verify", "lint")):
            return ["validate"]
        return ["compute"]


# Singleton — shared across all requests in this process
_classifier = EffectClassifier()


def get_classifier() -> EffectClassifier:
    """Return the process-level singleton EffectClassifier."""
    return _classifier
