"""Tests for the Test Lab execution engine."""


def test_execution_engine_importable():
    from app.services.test_lab.execution_engine import execute_test_run

    assert callable(execute_test_run)


def test_execution_engine_from_request_importable():
    from app.services.test_lab.execution_engine import execute_test_from_request

    assert callable(execute_test_from_request)


def test_emit_event_importable():
    from app.services.test_lab.execution_engine import emit_event, update_run

    assert callable(emit_event)
    assert callable(update_run)


def test_phase_constants():
    from app.services.test_lab.execution_engine import PHASES

    assert "preparation" in PHASES
    assert "runtime" in PHASES
    assert "assertions" in PHASES
    assert "diagnostics" in PHASES
    assert "verdict" in PHASES


def test_orchestrator_backward_compat():
    from app.services.test_lab.orchestrator import emit, run_test, update_run

    assert callable(emit)
    assert callable(update_run)
    assert callable(run_test)
