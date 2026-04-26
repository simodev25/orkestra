"""Formatters LLM projet (wrappers AgentScope)."""

from __future__ import annotations

from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg


def _strip_thinking_blocks(msg: Msg) -> Msg:
    """Return a copy of ``msg`` without unsupported ``thinking`` blocks.

    Certains modèles (ex: deepseek via Ollama cloud) renvoient des blocs
    ``{"type": "thinking"}`` qui ne sont pas supportés par
    ``OpenAIChatFormatter``. Sans filtrage, AgentScope loggue un warning à
    chaque passage dans le formatter.
    """
    content = getattr(msg, "content", None)
    if not isinstance(content, list):
        return msg

    filtered = [
        block
        for block in content
        if not (isinstance(block, dict) and block.get("type") == "thinking")
    ]
    if len(filtered) == len(content):
        return msg

    if not filtered:
        # Évite d'émettre un message assistant avec une liste vide
        filtered = ""

    return Msg(
        name=msg.name,
        role=msg.role,
        content=filtered,
        metadata=getattr(msg, "metadata", None),
        timestamp=getattr(msg, "timestamp", None),
        invocation_id=getattr(msg, "invocation_id", None),
    )


class OpenAIChatFormatterIgnoringThinking(OpenAIChatFormatter):
    """OpenAIChatFormatter qui retire les blocs ``thinking`` en amont."""

    async def _format(self, msgs: list[Msg]) -> list[dict]:
        sanitized = [_strip_thinking_blocks(m) for m in msgs]
        return await super()._format(sanitized)
