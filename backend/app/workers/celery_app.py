from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("xai_report_builder", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_always_eager = settings.celery_task_always_eager
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.imports = ("app.workers.tasks",)
