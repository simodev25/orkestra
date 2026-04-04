"""LLM provider -- creates AgentScope models for agent execution."""

import logging
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_agentscope_available = None


def is_agentscope_available() -> bool:
    global _agentscope_available
    if _agentscope_available is None:
        try:
            import agentscope
            _agentscope_available = True
        except ImportError:
            _agentscope_available = False
    return _agentscope_available


def get_chat_model():
    """Create and return an AgentScope chat model based on config."""
    if not is_agentscope_available():
        logger.warning("AgentScope not available")
        return None

    settings = get_settings()
    provider = getattr(settings, "LLM_PROVIDER", "ollama")

    try:
        if provider == "ollama":
            from agentscope.model import OllamaChatModel
            return OllamaChatModel(
                model_name=getattr(settings, "OLLAMA_MODEL", "mistral"),
                host=getattr(settings, "OLLAMA_HOST", "http://localhost:11434"),
                stream=False,
            )
        elif provider in ("openai", "mistral"):
            from agentscope.model import OpenAIChatModel
            return OpenAIChatModel(
                model_name=getattr(settings, "OPENAI_MODEL", "mistral-small-latest"),
                api_key=getattr(settings, "OPENAI_API_KEY", ""),
                base_url=getattr(settings, "OPENAI_BASE_URL", "https://api.mistral.ai/v1"),
            )
        else:
            logger.warning(f"Unknown LLM provider: {provider}")
            return None
    except Exception as e:
        logger.warning(f"Failed to create chat model: {e}")
        return None


def get_formatter():
    """Get the appropriate formatter for the configured LLM provider."""
    if not is_agentscope_available():
        return None

    settings = get_settings()
    provider = getattr(settings, "LLM_PROVIDER", "ollama")

    try:
        if provider == "ollama":
            from agentscope.formatter import OllamaChatFormatter
            return OllamaChatFormatter()
        elif provider in ("openai", "mistral"):
            from agentscope.formatter import OpenAIChatFormatter
            return OpenAIChatFormatter()
        else:
            return None
    except Exception as e:
        logger.warning(f"Failed to create formatter: {e}")
        return None
