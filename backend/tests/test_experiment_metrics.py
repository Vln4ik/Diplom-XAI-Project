from __future__ import annotations

from app.services.experiment import compare_time_ranges, seconds_to_minutes, summarize_min_max_ranges


def test_summarize_min_max_ranges():
    summary = summarize_min_max_ranges(
        {
            "step_a": {"min": 10, "max": 20},
            "step_b": {"min": 5, "max": 15},
        }
    )
    assert summary == {"min": 15.0, "max": 35.0, "midpoint": 25.0}


def test_seconds_to_minutes():
    assert seconds_to_minutes(12.27) == 0.2045


def test_compare_time_ranges():
    comparison = compare_time_ranges(
        manual_minutes={"min": 150, "max": 360, "midpoint": 255},
        automated_minutes={"min": 40.2, "max": 90.2, "midpoint": 65.2},
    )
    assert comparison["min_minutes_saved"] == 59.8
    assert comparison["max_minutes_saved"] == 319.8
    assert comparison["midpoint_minutes_saved"] == 189.8
    assert comparison["min_reduction_percent"] == 39.87
    assert comparison["max_reduction_percent"] == 88.83
    assert comparison["midpoint_reduction_percent"] == 74.43
