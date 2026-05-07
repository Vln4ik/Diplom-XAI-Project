from __future__ import annotations

from statistics import mean


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(float(values[0]), 4)

    sorted_values = sorted(float(value) for value in values)
    if p <= 0:
        return round(sorted_values[0], 4)
    if p >= 1:
        return round(sorted_values[-1], 4)

    position = (len(sorted_values) - 1) * p
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    interpolated = sorted_values[lower_index] + (sorted_values[upper_index] - sorted_values[lower_index]) * fraction
    return round(interpolated, 4)


def summarize_metric(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {
            "count": 0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "p50": 0.0,
            "p95": 0.0,
        }

    normalized = [float(value) for value in values]
    return {
        "count": len(normalized),
        "min": round(min(normalized), 4),
        "max": round(max(normalized), 4),
        "mean": round(mean(normalized), 4),
        "p50": percentile(normalized, 0.50),
        "p95": percentile(normalized, 0.95),
    }


def flatten_timing_metrics(runs: list[dict[str, object]]) -> dict[str, dict[str, float | int]]:
    series: dict[str, list[float]] = {}
    for run in runs:
        timings = run.get("timings_seconds")
        if not isinstance(timings, dict):
            continue
        for key, value in timings.items():
            if isinstance(value, (int, float)):
                series.setdefault(key, []).append(float(value))
    return {key: summarize_metric(values) for key, values in sorted(series.items())}


def throughput_per_minute(completed_runs: int, total_wall_seconds: float) -> float:
    if completed_runs <= 0 or total_wall_seconds <= 0:
        return 0.0
    return round(completed_runs / total_wall_seconds * 60.0, 4)


def success_rate(completed_runs: int, requested_runs: int) -> float:
    if requested_runs <= 0:
        return 0.0
    return round(completed_runs / requested_runs, 4)
