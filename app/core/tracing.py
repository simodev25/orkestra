"""Centralised OTLP tracing setup for Orkestra.

Call ``setup_tracing(endpoint)`` once at startup.
Call ``flush_traces()`` before process exit or after a test run.
"""

import logging

logger = logging.getLogger("orkestra.tracing")

_initialized = False


def setup_tracing(endpoint: str | None) -> None:
    """Initialise AgentScope OTLP tracing.

    Safe to call multiple times — silently no-ops if endpoint is falsy or already
    initialized.
    """
    global _initialized
    if _initialized or not endpoint:
        return
    _initialized = True
    try:
        from agentscope.tracing import setup_tracing as _setup
        _setup(endpoint=endpoint)
        logger.info("AgentScope OTLP tracing → %s", endpoint)
    except Exception as exc:
        logger.warning("Tracing init failed: %s", exc)


def flush_traces() -> None:
    """Force-flush pending OTLP spans. Safe to call even without a provider."""
    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush(timeout_millis=5000)
    except Exception:
        pass
