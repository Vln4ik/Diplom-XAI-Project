from __future__ import annotations

from threading import Lock
from time import perf_counter

from celery import Celery
from celery.signals import after_task_publish, task_postrun, task_prerun

from app.core.config import get_settings
from app.services.runtime_metrics import runtime_metrics

settings = get_settings()

celery_app = Celery("xai_report_builder", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_always_eager = settings.celery_task_always_eager
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.imports = ("app.workers.tasks",)
celery_app.conf.task_track_started = True
celery_app.conf.task_send_sent_event = True
celery_app.conf.worker_send_task_events = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.result_expires = 60 * 60 * 24

_task_started_at: dict[str, float] = {}
_task_started_lock = Lock()


def _task_name_from_signal(*, task: object | None = None, sender: object | None = None, headers: object | None = None) -> str | None:
    task_name = getattr(task, "name", None)
    if task_name:
        return str(task_name)
    if sender:
        return str(sender)
    if isinstance(headers, dict):
        header_task = headers.get("task")
        if header_task:
            return str(header_task)
    return None


@after_task_publish.connect
def observe_task_queued(sender: object | None = None, headers: object | None = None, **_: object) -> None:
    task_id = headers.get("id") if isinstance(headers, dict) else None
    runtime_metrics.record_task_queued(
        task_id=str(task_id) if task_id else None,
        task_name=_task_name_from_signal(sender=sender, headers=headers),
    )


@task_prerun.connect
def observe_task_started(task_id: str | None = None, task: object | None = None, **_: object) -> None:
    if task_id:
        with _task_started_lock:
            _task_started_at[task_id] = perf_counter()
    runtime_metrics.record_task_started(task_id=task_id, task_name=_task_name_from_signal(task=task))


@task_postrun.connect
def observe_task_finished(
    task_id: str | None = None,
    task: object | None = None,
    state: str | None = None,
    retval: object | None = None,
    **_: object,
) -> None:
    duration_seconds = None
    if task_id:
        with _task_started_lock:
            started_at = _task_started_at.pop(task_id, None)
        if started_at is not None:
            duration_seconds = perf_counter() - started_at

    status = state or "unknown"
    error = str(retval) if status.lower() in {"failure", "retry", "revoked"} and retval is not None else None
    runtime_metrics.record_task_finished(
        task_id=task_id,
        task_name=_task_name_from_signal(task=task),
        status=status,
        duration_seconds=duration_seconds,
        error=error,
    )
