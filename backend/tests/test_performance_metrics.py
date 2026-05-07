from __future__ import annotations

from app.services.performance import flatten_timing_metrics, percentile, success_rate, summarize_metric, throughput_per_minute


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
