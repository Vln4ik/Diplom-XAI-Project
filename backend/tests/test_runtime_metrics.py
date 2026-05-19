from __future__ import annotations

from collections import defaultdict

from app.services.runtime_metrics import RuntimeMetrics


class FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = defaultdict(dict)
        self.lists: dict[str, list[str]] = defaultdict(list)

    def hget(self, key: str, field: str) -> str | None:
        return self.hashes[key].get(field)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes[key])

    def hmget(self, key: str, fields: list[str]) -> list[str | None]:
        return [self.hashes[key].get(field) for field in fields]

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        stop = None if end == -1 else end + 1
        return self.lists[key][start:stop]

    def pipeline(self) -> "FakeRedis":
        return self

    def execute(self) -> None:
        return None

    def hincrby(self, key: str, field: str, amount: int) -> "FakeRedis":
        self.hashes[key][field] = str(int(self.hashes[key].get(field, "0")) + amount)
        return self

    def hincrbyfloat(self, key: str, field: str, amount: float) -> "FakeRedis":
        self.hashes[key][field] = str(float(self.hashes[key].get(field, "0")) + amount)
        return self

    def hset(self, key: str, field: str, value: str) -> "FakeRedis":
        self.hashes[key][field] = value
        return self

    def lrem(self, key: str, _count: int, value: str) -> "FakeRedis":
        self.lists[key] = [item for item in self.lists[key] if item != value]
        return self

    def lpush(self, key: str, value: str) -> "FakeRedis":
        self.lists[key].insert(0, value)
        return self

    def ltrim(self, key: str, start: int, end: int) -> "FakeRedis":
        stop = None if end == -1 else end + 1
        self.lists[key] = self.lists[key][start:stop]
        return self

    def expire(self, _key: str, _seconds: int) -> "FakeRedis":
        return self


def test_runtime_metrics_tracks_task_lifecycle() -> None:
    metrics = RuntimeMetrics(redis_enabled=False)

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
    metrics = RuntimeMetrics(redis_enabled=False)

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


def test_runtime_metrics_reads_shared_task_lifecycle_from_redis(monkeypatch) -> None:
    redis = FakeRedis()
    publisher_metrics = RuntimeMetrics()
    worker_metrics = RuntimeMetrics()
    api_metrics = RuntimeMetrics()
    monkeypatch.setattr(publisher_metrics, "_get_redis_client", lambda: redis)
    monkeypatch.setattr(worker_metrics, "_get_redis_client", lambda: redis)
    monkeypatch.setattr(api_metrics, "_get_redis_client", lambda: redis)

    publisher_metrics.record_task_queued(task_id="shared-task", task_name="report_analyze")
    worker_metrics.record_task_started(task_id="shared-task", task_name="report_analyze")
    worker_metrics.record_task_finished(
        task_id="shared-task",
        task_name="report_analyze",
        status="FAILURE",
        duration_seconds=2.0,
        error="llm unavailable",
    )

    snapshot = api_metrics.snapshot()

    assert {"task_name": "report_analyze", "status": "queued", "count": 1} in snapshot["task_totals"]
    assert {"task_name": "report_analyze", "status": "started", "count": 1} in snapshot["task_totals"]
    assert {"task_name": "report_analyze", "status": "failed", "count": 1} in snapshot["task_totals"]
    assert snapshot["task_latency"] == [
        {
            "task_name": "report_analyze",
            "status": "failed",
            "count": 1,
            "avg_seconds": 2.0,
            "max_seconds": 2.0,
        }
    ]
    assert snapshot["recent_tasks"][0]["status"] == "failed"
    assert snapshot["recent_tasks"][0]["queued_at"]
    assert snapshot["recent_tasks"][0]["started_at"]
    assert snapshot["recent_tasks"][0]["finished_at"]
    assert snapshot["recent_tasks"][0]["error"] == "llm unavailable"
