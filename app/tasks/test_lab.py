"""Celery task for Agentic Test Lab — thin wrapper around orchestrator."""

import asyncio
import logging
from datetime import datetime, timezone

from app.celery_app import celery
from app.services.test_lab.orchestrator import emit, update_run

logger = logging.getLogger("orkestra.tasks.test_lab")


@celery.task(bind=True, name="test_lab.run_test")
def run_test_task(self, run_id: str, scenario_id: str):
    """Execute a test run via Celery. Delegates to orchestrator.run_test()."""
    logger.info(f"Celery task started: run={run_id} scenario={scenario_id}")

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run(run_id, scenario_id))
    except Exception as e:
        logger.error(f"Celery task failed: {e}")
        emit(run_id, "run_failed", "orchestrator", f"Error: {e}")
        update_run(run_id, status="failed", error_message=str(e)[:1000],
                   ended_at=datetime.now(timezone.utc).isoformat())
    finally:
        loop.close()


async def _run(run_id: str, scenario_id: str):
    from app.services.test_lab.orchestrator import run_test
    await run_test(run_id, scenario_id)
