"""Test Lab Orchestrator — compatibility wrapper.

This module delegates to the execution engine for backward compatibility.
The actual test execution logic lives in execution_engine.py.
"""
from app.services.test_lab.execution_engine import (
    emit_event as emit,
    update_run,
    execute_test_run as run_test,
)

__all__ = ["emit", "update_run", "run_test"]
