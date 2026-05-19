from __future__ import annotations

from app.services.runtime_metrics import RuntimeMetrics


def test_runtime_metrics_tracks_task_lifecycle() -> None:
    metrics = RuntimeMetrics()

    metrics.record_task_queued(task_id="task-1", task_name="document_process")
    metrics.record_task_started(task_id="task-1", task_name="document_process")
    metrics.record_task_finished(
        task_id="task-1",
        task_name="document_process",
        status="SUCCESS",
        duration_seconds=1.25,
    )

    snapshot = metrics.snapshot()

    assert {"task_name": "document_process", "status": "queued", "count": 1} in snapshot["task_totals"]
    assert {"task_name": "document_process", "status": "started", "count": 1} in snapshot["task_totals"]
    assert {"task_name": "document_process", "status": "succeeded", "count": 1} in snapshot["task_totals"]
    assert snapshot["task_latency"] == [
        {
            "task_name": "document_process",
            "status": "succeeded",
            "count": 1,
            "avg_seconds": 1.25,
            "max_seconds": 1.25,
        }
    ]
    assert snapshot["recent_tasks"][0]["status"] == "succeeded"
    assert snapshot["recent_tasks"][0]["duration_seconds"] == 1.25

    prometheus = metrics.render_prometheus()
    assert 'xai_celery_task_events_total{task="document_process",status="succeeded"} 1' in prometheus
    assert 'xai_celery_recent_tasks{task="document_process",status="succeeded"} 1' in prometheus


def test_runtime_metrics_keeps_failed_task_error() -> None:
    metrics = RuntimeMetrics()

    metrics.record_task_finished(
        task_id="task-2",
        task_name="report_analyze",
        status="FAILURE",
        duration_seconds=0.5,
        error="model timeout",
    )

    recent = metrics.snapshot()["recent_tasks"][0]

    assert recent["task_name"] == "report_analyze"
    assert recent["status"] == "failed"
    assert recent["error"] == "model timeout"
