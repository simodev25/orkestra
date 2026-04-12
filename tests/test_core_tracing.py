"""Tests for app.core.tracing module."""
from unittest.mock import patch, MagicMock
from app.core import tracing as tracing_module


def test_flush_traces_no_provider():
    """flush_traces should not raise when no OTLP provider is active."""
    with patch("opentelemetry.trace.get_tracer_provider") as mock_get:
        mock_provider = MagicMock(spec=[])  # no force_flush attr
        mock_get.return_value = mock_provider
        tracing_module.flush_traces()  # should not raise


def test_flush_traces_with_provider():
    """flush_traces calls force_flush when provider supports it."""
    with patch("opentelemetry.trace.get_tracer_provider") as mock_get:
        mock_provider = MagicMock()
        mock_get.return_value = mock_provider
        tracing_module.flush_traces()
        mock_provider.force_flush.assert_called_once_with(timeout_millis=5000)


def test_setup_tracing_no_endpoint(caplog):
    """setup_tracing is a no-op when endpoint is None or empty."""
    import logging
    with caplog.at_level(logging.WARNING, logger="orkestra.tracing"):
        tracing_module.setup_tracing(endpoint=None)
        tracing_module.setup_tracing(endpoint="")
    # No warning or info logged for missing endpoint
    assert "tracing init failed" not in caplog.text.lower()
    assert "otlp tracing" not in caplog.text.lower()


def test_setup_tracing_with_valid_endpoint():
    """setup_tracing delegates to agentscope.tracing when endpoint is set."""
    original = tracing_module._initialized
    tracing_module._initialized = False
    try:
        with patch("agentscope.tracing.setup_tracing") as mock_setup:
            tracing_module.setup_tracing(endpoint="http://localhost:4317")
            mock_setup.assert_called_once_with(endpoint="http://localhost:4317")
    finally:
        tracing_module._initialized = original
