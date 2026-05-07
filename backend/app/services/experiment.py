from __future__ import annotations

from collections.abc import Mapping


def summarize_min_max_ranges(items: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    min_total = round(sum(float(value["min"]) for value in items.values()), 4)
    max_total = round(sum(float(value["max"]) for value in items.values()), 4)
    midpoint_total = round((min_total + max_total) / 2, 4)
    return {
        "min": min_total,
        "max": max_total,
        "midpoint": midpoint_total,
    }


def seconds_to_minutes(seconds: float) -> float:
    return round(float(seconds) / 60.0, 4)


def compare_time_ranges(
    *,
    manual_minutes: Mapping[str, float],
    automated_minutes: Mapping[str, float],
) -> dict[str, float]:
    manual_min = float(manual_minutes["min"])
    manual_max = float(manual_minutes["max"])
    manual_mid = float(manual_minutes["midpoint"])
    automated_min = float(automated_minutes["min"])
    automated_max = float(automated_minutes["max"])
    automated_mid = float(automated_minutes["midpoint"])

    min_minutes_saved = round(manual_min - automated_max, 4)
    max_minutes_saved = round(manual_max - automated_min, 4)
    midpoint_minutes_saved = round(manual_mid - automated_mid, 4)

    min_reduction_percent = round(max(0.0, (1.0 - automated_max / manual_min) * 100.0), 2)
    max_reduction_percent = round(max(0.0, (1.0 - automated_min / manual_max) * 100.0), 2)
    midpoint_reduction_percent = round(max(0.0, (1.0 - automated_mid / manual_mid) * 100.0), 2)

    return {
        "min_minutes_saved": min_minutes_saved,
        "max_minutes_saved": max_minutes_saved,
        "midpoint_minutes_saved": midpoint_minutes_saved,
        "min_reduction_percent": min_reduction_percent,
        "max_reduction_percent": max_reduction_percent,
        "midpoint_reduction_percent": midpoint_reduction_percent,
    }
