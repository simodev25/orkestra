"""Celery app configuration for Orkestra."""

from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "orkestra",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.test_lab"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Long timeout for agent execution
    task_soft_time_limit=300,
    task_time_limit=600,
)
