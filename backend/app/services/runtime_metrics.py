from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from datetime import UTC, datetime
from threading import Lock


class RuntimeMetrics:
    def __init__(self, *, max_request_samples: int = 500, max_task_history: int = 200) -> None:
        self._max_request_samples = max_request_samples
        self._max_task_history = max_task_history
        self._lock = Lock()
        self._request_counts: dict[tuple[str, str, int], int] = defaultdict(int)
        self._request_durations: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._task_events: dict[tuple[str, str], int] = defaultdict(int)
        self._task_durations: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._task_history: OrderedDict[str, dict[str, object]] = OrderedDict()

    def record_request(self, *, method: str, path: str, status_code: int, duration_seconds: float) -> None:
        key = (method, path, status_code)
        duration_key = (method, path)
        with self._lock:
            self._request_counts[key] += 1
            durations = self._request_durations[duration_key]
            durations.append(duration_seconds)
            if len(durations) > self._max_request_samples:
                del durations[: len(durations) - self._max_request_samples]

    def record_task_queued(self, *, task_id: str | None, task_name: str | None) -> None:
        if not task_id or not task_name:
            return
        with self._lock:
            self._record_task_state(task_id=task_id, task_name=task_name, status="queued", duration_seconds=None)

    def record_task_started(self, *, task_id: str | None, task_name: str | None) -> None:
        if not task_id or not task_name:
            return
        with self._lock:
            self._record_task_state(task_id=task_id, task_name=task_name, status="started", duration_seconds=None)

    def record_task_finished(
        self,
        *,
        task_id: str | None,
        task_name: str | None,
        status: str,
        duration_seconds: float | None = None,
        error: str | None = None,
    ) -> None:
        if not task_id or not task_name:
            return
        normalized_status = _normalize_task_status(status)
        with self._lock:
            self._record_task_state(
                task_id=task_id,
                task_name=task_name,
                status=normalized_status,
                duration_seconds=duration_seconds,
                error=error,
            )

    def _record_task_state(
        self,
        *,
        task_id: str,
        task_name: str,
        status: str,
        duration_seconds: float | None,
        error: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        self._task_events[(task_name, status)] += 1
        if duration_seconds is not None:
            durations = self._task_durations[(task_name, status)]
            durations.append(duration_seconds)
            if len(durations) > self._max_request_samples:
                del durations[: len(durations) - self._max_request_samples]

        task = self._task_history.get(task_id, {"task_id": task_id, "task_name": task_name, "created_at": now})
        task["task_name"] = task_name
        task["status"] = status
        task["updated_at"] = now
        if status == "queued":
            task["queued_at"] = now
        if status == "started":
            task["started_at"] = now
        if status in {"succeeded", "failed", "retried", "revoked"}:
            task["finished_at"] = now
        if duration_seconds is not None:
            task["duration_seconds"] = round(duration_seconds, 4)
        if error:
            task["error"] = error[:700]
        elif status == "succeeded":
            task.pop("error", None)

        self._task_history[task_id] = task
        self._task_history.move_to_end(task_id)
        while len(self._task_history) > self._max_task_history:
            self._task_history.popitem(last=False)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counts = dict(self._request_counts)
            durations = {key: list(values) for key, values in self._request_durations.items()}
            task_events = dict(self._task_events)
            task_durations = {key: list(values) for key, values in self._task_durations.items()}
            task_history = list(self._task_history.values())

        request_totals = [
            {
                "method": method,
                "path": path,
                "status_code": status_code,
                "count": count,
            }
            for (method, path, status_code), count in sorted(counts.items())
        ]
        latency = [
            {
                "method": method,
                "path": path,
                "count": len(values),
                "avg_seconds": round(sum(values) / len(values), 4) if values else 0.0,
                "max_seconds": round(max(values), 4) if values else 0.0,
            }
            for (method, path), values in sorted(durations.items())
        ]
        task_totals = [
            {
                "task_name": task_name,
                "status": status,
                "count": count,
            }
            for (task_name, status), count in sorted(task_events.items())
        ]
        task_latency = [
            {
                "task_name": task_name,
                "status": status,
                "count": len(values),
                "avg_seconds": round(sum(values) / len(values), 4) if values else 0.0,
                "max_seconds": round(max(values), 4) if values else 0.0,
            }
            for (task_name, status), values in sorted(task_durations.items())
        ]
        recent_statuses = Counter((task["task_name"], task.get("status", "unknown")) for task in task_history)
        task_recent_status_counts = [
            {
                "task_name": task_name,
                "status": str(status),
                "count": count,
            }
            for (task_name, status), count in sorted(recent_statuses.items())
        ]
        return {
            "request_totals": request_totals,
            "request_latency": latency,
            "task_totals": task_totals,
            "task_latency": task_latency,
            "task_recent_status_counts": task_recent_status_counts,
            "recent_tasks": list(reversed(task_history[-50:])),
        }

    def render_prometheus(self) -> str:
        with self._lock:
            counts = dict(self._request_counts)
            durations = {key: list(values) for key, values in self._request_durations.items()}
            task_events = dict(self._task_events)
            task_durations = {key: list(values) for key, values in self._task_durations.items()}
            task_history = list(self._task_history.values())

        lines = [
            "# HELP xai_http_requests_total Count of HTTP requests handled by the API",
            "# TYPE xai_http_requests_total counter",
        ]
        for (method, path, status_code), count in sorted(counts.items()):
            lines.append(
                'xai_http_requests_total{'
                f'method="{_escape_label(method)}",path="{_escape_label(path)}",status="{status_code}"'
                f"}} {count}"
            )
        lines.extend(
            [
                "# HELP xai_http_request_duration_seconds_avg Average request duration in seconds",
                "# TYPE xai_http_request_duration_seconds_avg gauge",
            ]
        )
        for (method, path), values in sorted(durations.items()):
            average = sum(values) / len(values) if values else 0.0
            lines.append(
                "xai_http_request_duration_seconds_avg{"
                f'method="{_escape_label(method)}",path="{_escape_label(path)}"'
                f"}} {average:.6f}"
            )
        lines.extend(
            [
                "# HELP xai_celery_task_events_total Count of observed Celery task lifecycle events",
                "# TYPE xai_celery_task_events_total counter",
            ]
        )
        for (task_name, status), count in sorted(task_events.items()):
            lines.append(
                "xai_celery_task_events_total{"
                f'task="{_escape_label(task_name)}",status="{_escape_label(status)}"'
                f"}} {count}"
            )
        lines.extend(
            [
                "# HELP xai_celery_task_duration_seconds_avg Average observed Celery task duration in seconds",
                "# TYPE xai_celery_task_duration_seconds_avg gauge",
            ]
        )
        for (task_name, status), values in sorted(task_durations.items()):
            average = sum(values) / len(values) if values else 0.0
            lines.append(
                "xai_celery_task_duration_seconds_avg{"
                f'task="{_escape_label(task_name)}",status="{_escape_label(status)}"'
                f"}} {average:.6f}"
            )

        recent_statuses = Counter((task["task_name"], task.get("status", "unknown")) for task in task_history)
        lines.extend(
            [
                "# HELP xai_celery_recent_tasks Count of tasks in recent in-memory history by latest status",
                "# TYPE xai_celery_recent_tasks gauge",
            ]
        )
        for (task_name, status), count in sorted(recent_statuses.items()):
            lines.append(
                "xai_celery_recent_tasks{"
                f'task="{_escape_label(str(task_name))}",status="{_escape_label(str(status))}"'
                f"}} {count}"
            )
        return "\n".join(lines) + "\n"


def _normalize_task_status(status: str) -> str:
    normalized = status.lower()
    return {
        "success": "succeeded",
        "failure": "failed",
        "retry": "retried",
    }.get(normalized, normalized)


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


runtime_metrics = RuntimeMetrics()
