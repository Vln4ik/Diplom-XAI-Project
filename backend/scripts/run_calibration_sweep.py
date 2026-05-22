#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.analysis import clear_analysis_calibration_cache  # noqa: E402
from app.services.quality_benchmark import load_benchmark_paths_from_manifest, run_quality_benchmark_suite  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run calibration sweep for evidence reranker and confidence thresholds.")
    parser.add_argument(
        "--profiles-file",
        type=Path,
        default=PROJECT_ROOT / "samples" / "calibration" / "evidence_confidence_profiles.json",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=PROJECT_ROOT / "docs" / "calibration-sweep-results.json",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=PROJECT_ROOT / "docs" / "calibration-sweep-results.md",
    )
    parser.add_argument(
        "--suite-manifest",
        type=Path,
        default=None,
        help="Optional benchmark suite manifest with relative benchmark paths.",
    )
    parser.add_argument("--timezone", default="Europe/Moscow")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _captured_at(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).isoformat()


def _format_ratio(value: float) -> str:
    return f"{value:.4f}"


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _clear_runtime_caches() -> None:
    get_settings.cache_clear()
    clear_analysis_calibration_cache()


def _apply_profile_env(profile_env: dict[str, str], *, tracked_keys: set[str], previous_env: dict[str, str | None]) -> None:
    for key in tracked_keys:
        if key in profile_env:
            os.environ[key] = str(profile_env[key])
        else:
            previous_value = previous_env.get(key)
            if previous_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous_value
    _clear_runtime_caches()


def _objective_score(aggregate: dict[str, object]) -> float:
    extraction = aggregate["requirement_extraction"]
    evidence = aggregate["evidence_linking"]
    sections = aggregate["report_sections"]
    applicability = aggregate["applicability"]
    return round(
        float(evidence["f1"]) * 0.4
        + float(evidence["precision"]) * 0.2
        + float(extraction["status_accuracy_mean"]) * 0.15
        + float(sections["source_requirement_coverage_mean"]) * 0.15
        + float(applicability["accuracy_mean"]) * 0.1,
        4,
    )


def _delta(current: float, baseline: float) -> float:
    return round(current - baseline, 4)


def build_report(
    profiles_payload: dict[str, object],
    *,
    timezone_name: str,
    benchmark_paths: list[Path] | None = None,
) -> dict[str, object]:
    profile_entries = profiles_payload.get("profiles", [])
    if not isinstance(profile_entries, list) or not profile_entries:
        raise ValueError("Calibration profiles payload must contain non-empty 'profiles' list")

    if benchmark_paths is None:
        benchmark_paths = sorted((PROJECT_ROOT / "samples" / "benchmarks").glob("*.json"))
    if not benchmark_paths:
        raise ValueError("No benchmark files found")

    tracked_keys = {
        str(key)
        for profile in profile_entries
        if isinstance(profile, dict)
        for key in (profile.get("env") or {}).keys()
    }
    previous_env = {key: os.environ.get(key) for key in tracked_keys}

    profile_results: list[dict[str, object]] = []
    try:
        for profile in profile_entries:
            if not isinstance(profile, dict):
                continue
            name = str(profile.get("name") or "").strip()
            if not name:
                continue
            description = str(profile.get("description") or "").strip()
            env = {str(key): str(value) for key, value in dict(profile.get("env") or {}).items()}
            _apply_profile_env(env, tracked_keys=tracked_keys, previous_env=previous_env)
            suite_report = run_quality_benchmark_suite(benchmark_paths)
            aggregate = suite_report["aggregate"]
            profile_results.append(
                {
                    "name": name,
                    "description": description,
                    "env": env,
                    "aggregate": aggregate,
                    "objective_score": _objective_score(aggregate),
                }
            )
    finally:
        _apply_profile_env({}, tracked_keys=tracked_keys, previous_env=previous_env)

    if not profile_results:
        raise ValueError("No calibration profiles were evaluated")

    baseline = profile_results[0]
    baseline_aggregate = baseline["aggregate"]
    baseline_evidence = baseline_aggregate["evidence_linking"]
    baseline_extraction = baseline_aggregate["requirement_extraction"]
    baseline_sections = baseline_aggregate["report_sections"]

    for item in profile_results:
        aggregate = item["aggregate"]
        evidence = aggregate["evidence_linking"]
        extraction = aggregate["requirement_extraction"]
        sections = aggregate["report_sections"]
        item["delta"] = {
            "objective_score": _delta(float(item["objective_score"]), float(baseline["objective_score"])),
            "evidence_precision": _delta(float(evidence["precision"]), float(baseline_evidence["precision"])),
            "evidence_recall": _delta(float(evidence["recall"]), float(baseline_evidence["recall"])),
            "evidence_f1": _delta(float(evidence["f1"]), float(baseline_evidence["f1"])),
            "status_accuracy_mean": _delta(
                float(extraction["status_accuracy_mean"]),
                float(baseline_extraction["status_accuracy_mean"]),
            ),
            "section_coverage_mean": _delta(
                float(sections["source_requirement_coverage_mean"]),
                float(baseline_sections["source_requirement_coverage_mean"]),
            ),
        }

    ranked_profiles = sorted(
        profile_results,
        key=lambda item: (
            float(item["objective_score"]),
            float(item["aggregate"]["evidence_linking"]["f1"]),
            float(item["aggregate"]["evidence_linking"]["precision"]),
            float(item["aggregate"]["requirement_extraction"]["status_accuracy_mean"]),
        ),
        reverse=True,
    )
    best_profile = ranked_profiles[0]

    return {
        "captured_at": _captured_at(timezone_name),
        "benchmark_count": len(benchmark_paths),
        "profile_count": len(profile_results),
        "baseline_profile": baseline["name"],
        "best_profile": best_profile["name"],
        "profiles": profile_results,
        "ranked_profiles": [item["name"] for item in ranked_profiles],
        "recommendation": {
            "name": best_profile["name"],
            "description": best_profile["description"],
            "env": best_profile["env"],
            "objective_score": best_profile["objective_score"],
        },
    }


def render_markdown(report: dict[str, object], *, timezone_name: str) -> str:
    captured_at = datetime.fromisoformat(str(report["captured_at"])).astimezone(ZoneInfo(timezone_name))
    lines = [
        "# Calibration Sweep Results",
        "",
        f"Дата фиксации: `{captured_at:%Y-%m-%d}`",
        "",
        "## 1. Назначение документа",
        "",
        "Документ фиксирует автоматический sweep по calibration-профилям для слоя",
        "`evidence reranker + confidence thresholds` на текущем benchmark-suite.",
        "",
        f"- benchmark scenarios: `{report['benchmark_count']}`",
        f"- evaluated profiles: `{report['profile_count']}`",
        f"- baseline profile: `{report['baseline_profile']}`",
        f"- recommended profile: `{report['best_profile']}`",
        "",
        "## 2. Сводная таблица профилей",
        "",
        "| Профиль | Objective | Evidence precision | Evidence recall | Evidence F1 | Status accuracy | Section coverage | Delta vs baseline |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for profile in report["profiles"]:
        aggregate = profile["aggregate"]
        evidence = aggregate["evidence_linking"]
        extraction = aggregate["requirement_extraction"]
        sections = aggregate["report_sections"]
        delta = profile["delta"]
        lines.append(
            f"| `{profile['name']}` | `{_format_ratio(float(profile['objective_score']))}` | "
            f"`{_format_ratio(float(evidence['precision']))}` | `{_format_ratio(float(evidence['recall']))}` | "
            f"`{_format_ratio(float(evidence['f1']))}` | `{_format_percent(float(extraction['status_accuracy_mean']))}` | "
            f"`{_format_percent(float(sections['source_requirement_coverage_mean']))}` | "
            f"`{delta['objective_score']:+.4f}` |"
        )

    lines.extend(
        [
            "",
            "## 3. Рекомендованный профиль",
            "",
            f"- profile: `{report['recommendation']['name']}`",
            f"- objective_score: `{_format_ratio(float(report['recommendation']['objective_score']))}`",
            f"- rationale: `{report['recommendation']['description']}`",
            "",
            "### Активные env overrides",
            "",
        ]
    )

    recommendation_env = report["recommendation"]["env"]
    if recommendation_env:
        for key, value in recommendation_env.items():
            lines.append(f"- `{key}={value}`")
    else:
        lines.append("- дополнительные overrides не требуются; рекомендован текущий baseline")

    lines.extend(
        [
            "",
            "## 4. Интерпретация",
            "",
            "- Sweep не заменяет большой реальный корпус, но делает подбор порогов воспроизводимым.",
            "- Профили оцениваются не по одной метрике, а по composite objective с упором на `evidence F1`, `precision`, `status accuracy` и `section coverage`.",
            "- Следующий исследовательский шаг — прогон этого же контура на расширенном реальном benchmark-корпусе организаций.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    profiles_payload = _load_json(args.profiles_file)
    benchmark_paths = (
        load_benchmark_paths_from_manifest(args.suite_manifest)
        if args.suite_manifest is not None
        else sorted((PROJECT_ROOT / "samples" / "benchmarks").glob("*.json"))
    )
    report = build_report(profiles_payload, timezone_name=args.timezone, benchmark_paths=benchmark_paths)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report, timezone_name=args.timezone) + "\n", encoding="utf-8")
    print(f"Written {args.output_json}")
    print(f"Written {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
