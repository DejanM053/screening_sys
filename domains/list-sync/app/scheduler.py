"""Celery app + beat schedule for sanctions list sync (Section CC-07)."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery("list_sync", broker=settings.celery_broker_url, backend=settings.celery_broker_url)

celery_app.conf.task_default_queue = "sanctions_sync"
celery_app.conf.timezone = "UTC"

celery_app.conf.beat_schedule = {
    "sync-ofac": {
        "task": "app.tasks.sync_ofac",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "sync-ofsi": {
        "task": "app.tasks.sync_ofsi",
        "schedule": crontab(minute=0, hour=8),
    },
    "sync-eu": {
        "task": "app.tasks.sync_eu",
        "schedule": crontab(minute=0, hour=9),
    },
    "sync-un": {
        "task": "app.tasks.sync_un",
        "schedule": crontab(minute=0, hour=10),
    },
    "sync-pep": {
        "task": "app.tasks.sync_pep",
        "schedule": crontab(minute=0, hour=6),
    },
}

celery_app.autodiscover_tasks(["app"])
