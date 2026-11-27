"""Celery application configured for Redis broker/backend with eager local fallback."""

from __future__ import annotations

from celery import Celery

from backend.app.core.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "aspirant_ecosystem",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["backend.app.workers.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_always_eager=settings.celery_task_always_eager,
        task_eager_propagates=True,
        broker_connection_retry_on_startup=False,
    )
    return app


celery_app = create_celery_app()
