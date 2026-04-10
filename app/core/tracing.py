"""Centralised OTLP tracing setup for Orkestra.

Call ``setup_tracing(endpoint)`` once at startup.
Call ``flush_traces()`` before process exit or after a test run.
"""

import logging

logger = logging.getLogger("orkestra.tracing")


def setup_tracing(endpoint: str | None) -> None:
    """Initialise AgentScope OTLP tracing.

    Safe to call multiple times — silently no-ops if endpoint is falsy or if
    agentscope.tracing is unavailable.
    """
    if not endpoint:
        return
    try:
        from agentscope.tracing import setup_tracing as _setup
        _setup(endpoint=endpoint)
        logger.info(f"AgentScope OTLP tracing → {endpoint}")
    except Exception as exc:
        logger.warning(f"Tracing init failed: {exc}")


def flush_traces() -> None:
    """Force-flush pending OTLP spans. Safe to call even without a provider."""
    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush(timeout_millis=5000)
    except Exception:
        pass
