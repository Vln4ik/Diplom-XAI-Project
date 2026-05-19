from __future__ import annotations

import json
from collections import Counter, OrderedDict, defaultdict
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from typing import Any

from app.core.config import get_settings

try:  # pragma: no cover - exercised when Redis package is available in runtime image
    from redis import Redis
except Exception:  # pragma: no cover - optional runtime dependency guard
    Redis = None


_TASK_EVENTS_KEY = "xai:runtime:task_events"
_TASK_DURATION_SUM_KEY = "xai:runtime:task_duration_sum"
_TASK_DURATION_COUNT_KEY = "xai:runtime:task_duration_count"
_TASK_HISTORY_KEY = "xai:runtime:task_history"
_TASK_ORDER_KEY = "xai:runtime:task_order"
_TASK_REDIS_TTL_SECONDS = 60 * 60 * 24


class RuntimeMetrics:
    def __init__(
        self,
        *,
        max_request_samples: int = 500,
        max_task_history: int = 200,
        redis_enabled: bool = True,
    ) -> None:
        self._max_request_samples = max_request_samples
        self._max_task_history = max_task_history
        self._lock = Lock()
        self._request_counts: dict[tuple[str, str, int], int] = defaultdict(int)
        self._request_durations: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._task_events: dict[tuple[str, str], int] = defaultdict(int)
        self._task_durations: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._task_history: OrderedDict[str, dict[str, object]] = OrderedDict()
        self._redis_client: Any | None = None
        self._redis_enabled = redis_enabled
        self._redis_retry_after = 0.0

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
            task = self._record_task_state(task_id=task_id, task_name=task_name, status="queued", duration_seconds=None)
        self._mirror_task_state_to_redis(task=task, duration_seconds=None)

    def record_task_started(self, *, task_id: str | None, task_name: str | None) -> None:
        if not task_id or not task_name:
            return
        with self._lock:
            task = self._record_task_state(task_id=task_id, task_name=task_name, status="started", duration_seconds=None)
        self._mirror_task_state_to_redis(task=task, duration_seconds=None)

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
            task = self._record_task_state(
                task_id=task_id,
                task_name=task_name,
                status=normalized_status,
                duration_seconds=duration_seconds,
                error=error,
            )
        self._mirror_task_state_to_redis(task=task, duration_seconds=duration_seconds)

    def _record_task_state(
        self,
        *,
        task_id: str,
        task_name: str,
        status: str,
        duration_seconds: float | None,
        error: str | None = None,
    ) -> dict[str, object]:
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
        return dict(task)

    def _get_redis_client(self) -> Any | None:
        if not self._redis_enabled or Redis is None:
            return None
        if monotonic() < self._redis_retry_after:
            return None
        if self._redis_client is not None:
            return self._redis_client
        try:
            self._redis_client = Redis.from_url(
                get_settings().redis_url,
                decode_responses=True,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
            )
            self._redis_client.ping()
            return self._redis_client
        except Exception:
            self._redis_retry_after = monotonic() + 5.0
            self._redis_client = None
            return None

    def _mirror_task_state_to_redis(self, *, task: dict[str, object], duration_seconds: float | None) -> None:
        client = self._get_redis_client()
        if client is None:
            return

        task_id = str(task["task_id"])
        task_name = str(task["task_name"])
        status = str(task["status"])
        metric_key = _encode_metric_key(task_name, status)
        try:
            existing_raw = client.hget(_TASK_HISTORY_KEY, task_id)
            existing = json.loads(existing_raw) if existing_raw else {}
            if not isinstance(existing, dict):
                existing = {}
            merged_task = {**existing, **task}

            pipeline = client.pipeline()
            pipeline.hincrby(_TASK_EVENTS_KEY, metric_key, 1)
            if duration_seconds is not None:
                pipeline.hincrbyfloat(_TASK_DURATION_SUM_KEY, metric_key, float(duration_seconds))
                pipeline.hincrby(_TASK_DURATION_COUNT_KEY, metric_key, 1)
            pipeline.hset(_TASK_HISTORY_KEY, task_id, json.dumps(merged_task, ensure_ascii=False))
            pipeline.lrem(_TASK_ORDER_KEY, 0, task_id)
            pipeline.lpush(_TASK_ORDER_KEY, task_id)
            pipeline.ltrim(_TASK_ORDER_KEY, 0, self._max_task_history - 1)
            for key in (
                _TASK_EVENTS_KEY,
                _TASK_DURATION_SUM_KEY,
                _TASK_DURATION_COUNT_KEY,
                _TASK_HISTORY_KEY,
                _TASK_ORDER_KEY,
            ):
                pipeline.expire(key, _TASK_REDIS_TTL_SECONDS)
            pipeline.execute()
        except Exception:
            self._redis_retry_after = monotonic() + 5.0
            self._redis_client = None

    def _load_redis_task_metrics(
        self,
    ) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], tuple[float, int]], list[dict[str, object]]] | None:
        client = self._get_redis_client()
        if client is None:
            return None
        try:
            event_rows = client.hgetall(_TASK_EVENTS_KEY)
            duration_sums = client.hgetall(_TASK_DURATION_SUM_KEY)
            duration_counts = client.hgetall(_TASK_DURATION_COUNT_KEY)
            task_ids = client.lrange(_TASK_ORDER_KEY, 0, self._max_task_history - 1)
            history_rows = client.hmget(_TASK_HISTORY_KEY, task_ids) if task_ids else []
        except Exception:
            self._redis_retry_after = monotonic() + 5.0
            self._redis_client = None
            return None

        task_events: dict[tuple[str, str], int] = {}
        for encoded_key, value in event_rows.items():
            decoded_key = _decode_metric_key(encoded_key)
            if decoded_key is not None:
                task_events[decoded_key] = int(value)

        task_durations: dict[tuple[str, str], tuple[float, int]] = {}
        for encoded_key, total_value in duration_sums.items():
            decoded_key = _decode_metric_key(encoded_key)
            if decoded_key is None:
                continue
            count_value = duration_counts.get(encoded_key, "0")
            task_durations[decoded_key] = (float(total_value), int(count_value))

        task_history: list[dict[str, object]] = []
        for row in history_rows:
            if not row:
                continue
            try:
                parsed = json.loads(row)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                task_history.append(parsed)
        task_history.reverse()
        return task_events, task_durations, task_history

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counts = dict(self._request_counts)
            durations = {key: list(values) for key, values in self._request_durations.items()}
            task_events = dict(self._task_events)
            task_durations = _duration_lists_to_totals(self._task_durations)
            task_history = list(self._task_history.values())

        redis_task_metrics = self._load_redis_task_metrics()
        if redis_task_metrics is not None:
            task_events, task_durations, task_history = redis_task_metrics

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
        task_views = _build_task_views(task_events=task_events, task_durations=task_durations, task_history=task_history)
        return {
            "request_totals": request_totals,
            "request_latency": latency,
            **task_views,
        }

    def render_prometheus(self) -> str:
        with self._lock:
            counts = dict(self._request_counts)
            durations = {key: list(values) for key, values in self._request_durations.items()}
            task_events = dict(self._task_events)
            task_durations = _duration_lists_to_totals(self._task_durations)
            task_history = list(self._task_history.values())

        redis_task_metrics = self._load_redis_task_metrics()
        if redis_task_metrics is not None:
            task_events, task_durations, task_history = redis_task_metrics

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
        for (task_name, status), (total_seconds, count) in sorted(task_durations.items()):
            average = total_seconds / count if count else 0.0
            lines.append(
                "xai_celery_task_duration_seconds_avg{"
                f'task="{_escape_label(task_name)}",status="{_escape_label(status)}"'
                f"}} {average:.6f}"
            )

        recent_statuses = Counter((task["task_name"], task.get("status", "unknown")) for task in task_history)
        lines.extend(
            [
                "# HELP xai_celery_recent_tasks Count of tasks in recent runtime history by latest status",
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


def _build_task_views(
    *,
    task_events: dict[tuple[str, str], int],
    task_durations: dict[tuple[str, str], tuple[float, int]],
    task_history: list[dict[str, object]],
) -> dict[str, object]:
    task_totals = [
        {
            "task_name": task_name,
            "status": status,
            "count": count,
        }
        for (task_name, status), count in sorted(task_events.items())
    ]

    recent_durations: dict[tuple[str, str], list[float]] = defaultdict(list)
    for task in task_history:
        task_name = task.get("task_name")
        status = task.get("status")
        duration = task.get("duration_seconds")
        if isinstance(task_name, str) and isinstance(status, str) and isinstance(duration, int | float):
            recent_durations[(task_name, status)].append(float(duration))

    task_latency = []
    for (task_name, status), (total_seconds, count) in sorted(task_durations.items()):
        max_seconds = max(recent_durations.get((task_name, status), [0.0]))
        task_latency.append(
            {
                "task_name": task_name,
                "status": status,
                "count": count,
                "avg_seconds": round(total_seconds / count, 4) if count else 0.0,
                "max_seconds": round(max_seconds, 4),
            }
        )

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
        "task_totals": task_totals,
        "task_latency": task_latency,
        "task_recent_status_counts": task_recent_status_counts,
        "recent_tasks": list(reversed(task_history[-50:])),
    }


def _duration_lists_to_totals(
    durations: dict[tuple[str, str], list[float]],
) -> dict[tuple[str, str], tuple[float, int]]:
    return {key: (sum(values), len(values)) for key, values in durations.items()}


def _normalize_task_status(status: str) -> str:
    normalized = status.lower()
    return {
        "success": "succeeded",
        "failure": "failed",
        "retry": "retried",
    }.get(normalized, normalized)


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _encode_metric_key(task_name: str, status: str) -> str:
    return json.dumps([task_name, status], ensure_ascii=False, separators=(",", ":"))


def _decode_metric_key(encoded_key: str) -> tuple[str, str] | None:
    try:
        value = json.loads(encoded_key)
    except json.JSONDecodeError:
        return None
    if (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], str)
    ):
        return value[0], value[1]
    return None


runtime_metrics = RuntimeMetrics()
