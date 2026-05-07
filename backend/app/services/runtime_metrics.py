from __future__ import annotations

from collections import defaultdict
from threading import Lock


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._request_counts: dict[tuple[str, str, int], int] = defaultdict(int)
        self._request_durations: dict[tuple[str, str], list[float]] = defaultdict(list)

    def record_request(self, *, method: str, path: str, status_code: int, duration_seconds: float) -> None:
        key = (method, path, status_code)
        duration_key = (method, path)
        with self._lock:
            self._request_counts[key] += 1
            durations = self._request_durations[duration_key]
            durations.append(duration_seconds)
            if len(durations) > 500:
                del durations[: len(durations) - 500]

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counts = dict(self._request_counts)
            durations = {key: list(values) for key, values in self._request_durations.items()}

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
        return {
            "request_totals": request_totals,
            "request_latency": latency,
        }

    def render_prometheus(self) -> str:
        with self._lock:
            counts = dict(self._request_counts)
            durations = {key: list(values) for key, values in self._request_durations.items()}

        lines = [
            "# HELP xai_http_requests_total Count of HTTP requests handled by the API",
            "# TYPE xai_http_requests_total counter",
        ]
        for (method, path, status_code), count in sorted(counts.items()):
            lines.append(
                f'xai_http_requests_total{{method="{method}",path="{path}",status="{status_code}"}} {count}'
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
                f'xai_http_request_duration_seconds_avg{{method="{method}",path="{path}"}} {average:.6f}'
            )
        return "\n".join(lines) + "\n"


runtime_metrics = RuntimeMetrics()
