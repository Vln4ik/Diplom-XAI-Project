from __future__ import annotations

from app.services.performance import (
    flatten_timing_metrics,
    parse_memory_to_mib,
    parse_percentage,
    percentile,
    success_rate,
    summarize_metric,
    summarize_resource_samples,
    throughput_per_minute,
)


def test_percentile_interpolates_between_values():
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 3.85


def test_summarize_metric_returns_expected_shape():
    summary = summarize_metric([1.0, 2.0, 3.0])

    assert summary == {
        "count": 3,
        "min": 1.0,
        "max": 3.0,
        "mean": 2.0,
        "p50": 2.0,
        "p95": 2.9,
    }


def test_flatten_timing_metrics_collects_across_runs():
    summary = flatten_timing_metrics(
        [
            {"timings_seconds": {"upload_total": 1.2, "analyze": 4.1}},
            {"timings_seconds": {"upload_total": 1.8, "analyze": 5.1}},
        ]
    )

    assert summary["upload_total"]["count"] == 2
    assert summary["upload_total"]["mean"] == 1.5
    assert summary["analyze"]["p50"] == 4.6


def test_throughput_per_minute_handles_simple_case():
    assert throughput_per_minute(4, 30.0) == 8.0


def test_success_rate_handles_zero_and_fraction():
    assert success_rate(0, 0) == 0.0
    assert success_rate(3, 4) == 0.75


def test_parse_percentage_and_memory_helpers():
    assert parse_percentage("13.25%") == 13.25
    assert parse_percentage("0,56%") == 0.56
    assert parse_memory_to_mib("1GiB") == 1024.0
    assert parse_memory_to_mib("512MiB") == 512.0
    assert parse_memory_to_mib("1024KiB") == 1.0


def test_summarize_resource_samples_groups_by_service():
    summary = summarize_resource_samples(
        [
            {
                "captured_at": "2026-05-07T00:00:00Z",
                "containers": {
                    "backend": {"cpu_percent": 10.0, "memory_mib": 128.0, "memory_percent": 1.6, "pids": 18.0},
                    "worker": {"cpu_percent": 20.0, "memory_mib": 900.0, "memory_percent": 11.8, "pids": 15.0},
                },
            },
            {
                "captured_at": "2026-05-07T00:00:01Z",
                "containers": {
                    "backend": {"cpu_percent": 30.0, "memory_mib": 132.0, "memory_percent": 1.7, "pids": 18.0},
                },
            },
        ]
    )

    assert summary["backend"]["cpu_percent"]["mean"] == 20.0
    assert summary["backend"]["memory_mib"]["max"] == 132.0
    assert summary["worker"]["memory_percent"]["mean"] == 11.8
