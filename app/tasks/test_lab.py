"""Celery tasks for Test Lab execution."""
import asyncio
import logging

from app.celery_app import celery
from app.services.test_lab.execution_engine import emit_event, execute_test_run, update_run

logger = logging.getLogger(__name__)


@celery.task(name="test_lab.run_test", bind=True, max_retries=0)
def run_test_task(self, run_id: str, scenario_id: str):
    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(execute_test_run(run_id, scenario_id))
        finally:
            loop.close()
    except Exception as exc:
        logger.exception(f"Test run {run_id} failed")
        try:
            emit_event(run_id, "run_failed", "error", f"Task failed: {exc}")
            update_run(run_id, status="failed", error_message=str(exc))
        except Exception:
            pass
        raise
