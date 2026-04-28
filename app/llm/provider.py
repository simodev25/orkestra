"""LLM provider -- creates AgentScope models for agent execution."""

import logging
from urllib.parse import urlparse

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


# ── Ollama helpers (shared by agent_factory and execution_engine) ─────────────

def is_local_ollama(url: str) -> bool:
    """Return True if the URL points to a local Ollama instance."""
    host = urlparse(url).hostname or ""
    return host in ("localhost", "127.0.0.1", "host.docker.internal", "::1")


def ensure_v1(url: str) -> str:
    """Ensure the URL ends with /v1 for OpenAI-compatible endpoints."""
    url = url.rstrip("/")
    return url if url.endswith("/v1") else f"{url}/v1"


def make_ollama_model(base_url: str, model_name: str, api_key: str | None = None):
    """Create the right AgentScope model depending on local vs remote Ollama.

    - Local  (localhost / host.docker.internal) → OllamaChatModel (native protocol)
    - Remote (https://ollama.com or any other)  → OpenAIChatModel (OpenAI-compatible /v1)
    """
    from agentscope.model import OllamaChatModel, OpenAIChatModel

    if is_local_ollama(base_url):
        logger.info("[LLM] ollama local host=%s model=%s", base_url, model_name)
        return OllamaChatModel(
            model_name=model_name,
            host=base_url.rstrip("/"),
            stream=False,
        )
    logger.info("[LLM] ollama remote base_url=%s model=%s api_key=%s",
                base_url, model_name, "SET" if api_key else "NOT_SET")
    return OpenAIChatModel(
        model_name=model_name,
        api_key=api_key or "ollama",
        client_kwargs={"base_url": ensure_v1(base_url)},
        stream=False,
    )


# ── Public factories ──────────────────────────────────────────────────────────

def get_chat_model(config: dict | None = None):
    """Create and return an AgentScope chat model.

    ``config`` (optional dict from DB) overrides env-var defaults:
      provider, ollama_host, ollama_model, openai_model, openai_base_url
    """
    if not is_agentscope_available():
        logger.warning("AgentScope not available")
        return None

    cfg = config or {}
    settings = get_settings()

    def _cfg(key: str, env_attr: str, default: str) -> str:
        return cfg.get(key) or getattr(settings, env_attr, None) or default

    provider = _cfg("provider", "LLM_PROVIDER", "ollama")

    try:
        if provider == "ollama":
            base_url = _cfg("ollama_host", "OLLAMA_HOST", "http://localhost:11434")
            model_name = _cfg("ollama_model", "OLLAMA_MODEL", "mistral")
            api_key = cfg.get("ollama_api_key") or getattr(settings, "OLLAMA_API_KEY", None)
            return make_ollama_model(base_url, model_name, api_key)
        elif provider in ("openai", "mistral"):
            from agentscope.model import OpenAIChatModel
            openai_key = cfg.get("openai_api_key") or getattr(settings, "OPENAI_API_KEY", "")
            base_url = _cfg("openai_base_url", "OPENAI_BASE_URL", "https://api.openai.com/v1")
            model_name = _cfg("openai_model", "OPENAI_MODEL", "gpt-4o-mini")
            logger.info("[LLM-TRACE] provider=%s base_url=%s model=%s api_key=%s",
                        provider, base_url, model_name, "SET" if openai_key else "NOT SET")
            return OpenAIChatModel(
                model_name=model_name,
                api_key=openai_key,
                base_url=base_url,
            )
        else:
            logger.warning("[LLM-TRACE] Unknown LLM provider: %s", provider)
            return None
    except Exception as e:
        logger.warning("[LLM-TRACE] Failed to create chat model: %s", e)
        return None


def get_formatter():
    """Get the appropriate formatter for the configured LLM provider."""
    if not is_agentscope_available():
        return None

    settings = get_settings()
    provider = getattr(settings, "LLM_PROVIDER", "ollama")

    try:
        if provider == "ollama":
            host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
            if is_local_ollama(host):
                from agentscope.formatter import OllamaChatFormatter
                return OllamaChatFormatter()
        # Remote Ollama (cloud) or OpenAI/Mistral → OpenAI-compatible formatter
        from app.llm.formatter import OpenAIChatFormatterIgnoringThinking
        return OpenAIChatFormatterIgnoringThinking()
    except Exception as e:
        logger.warning(f"Failed to create formatter: {e}")
        return None
