"""Celery application (T-07 parallel pipeline).

Workers are started with ``celery -A app.workers.celery_app worker``; the API
enqueues ``analysis.run`` which fans out per-file ``analysis.parse_file`` tasks
(a ``group``, so they run concurrently on the prefork pool) and aggregates the
results deterministically. ``CELERY_TASK_ALWAYS_EAGER=1`` runs everything inline
(used by the test suite; no broker needed).
"""

import os

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "codeoracle",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_always_eager=os.environ.get("CELERY_TASK_ALWAYS_EAGER", "0") == "1",
    task_eager_propagates=False,
    result_expires=3600,
    worker_prefetch_multiplier=4,
)