#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.quality_benchmark import run_quality_benchmark  # noqa: E402
from app.services.real_corpus import load_real_corpus_case_paths, summarize_real_corpus_manifest  # noqa: E402


METRIC_ACCESSORS = {
    "requirement_f1_min": lambda report: float(report["requirement_extraction"]["f1"]),
    "status_accuracy_min": lambda report: float(report["requirement_extraction"]["status_accuracy"]),
    "evidence_f1_min": lambda report: float(report["evidence_linking"]["f1"]),
    "section_coverage_min": lambda report: float(report["report_sections"]["source_requirement_coverage"]),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate real corpus case-level quality targets.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "samples" / "real_corpus" / "manifests" / "pilot-redacted.json",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=PROJECT_ROOT / "docs" / "real-corpus-target-evaluation.json",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=PROJECT_ROOT / "docs" / "real-corpus-target-evaluation.md",
    )
    parser.add_argument("--timezone", default="Europe/Moscow")
    return parser.parse_args()


def _captured_at(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).isoformat()


def _format_ratio(value: float) -> str:
    return f"{value:.4f}"


def build_report(manifest_path: Path, *, timezone_name: str) -> dict[str, object]:
    summary = summarize_real_corpus_manifest(manifest_path)
    case_paths = load_real_corpus_case_paths(manifest_path)
    case_reports_by_id = {case["case_id"]: case for case in summary["cases"]}

    case_results: list[dict[str, object]] = []
    passed_cases = 0
    total_targets = 0
    passed_targets = 0
    for case_path in case_paths:
        payload = json.loads(case_path.read_text(encoding="utf-8"))
        case_id = str(payload["case_id"])
        case_report = case_reports_by_id[case_id]
        benchmark_path = PROJECT_ROOT / str(payload["annotations"]["benchmark_path"])
        benchmark_report = run_quality_benchmark(benchmark_path)

        target_results: list[dict[str, object]] = []
        case_passed = True
        for target_name, threshold in case_report["quality_targets"].items():
            accessor = METRIC_ACCESSORS.get(target_name)
            if accessor is None:
                continue
            actual_value = round(accessor(benchmark_report), 4)
            target_value = round(float(threshold), 4)
            passed = actual_value >= target_value
            total_targets += 1
            if passed:
                passed_targets += 1
            else:
                case_passed = False
            target_results.append(
                {
                    "metric": target_name,
                    "actual": actual_value,
                    "target": target_value,
                    "passed": passed,
                }
            )

        if case_passed:
            passed_cases += 1
        case_results.append(
            {
                "case_id": case_id,
                "scenario": case_report["scenario"],
                "difficulty": case_report["difficulty"],
                "analysis_focus": case_report["analysis_focus"],
                "targets": target_results,
                "case_passed": case_passed,
                "benchmark": {
                    "requirement_f1": round(float(benchmark_report["requirement_extraction"]["f1"]), 4),
                    "status_accuracy": round(float(benchmark_report["requirement_extraction"]["status_accuracy"]), 4),
                    "evidence_f1": round(float(benchmark_report["evidence_linking"]["f1"]), 4),
                    "section_coverage": round(float(benchmark_report["report_sections"]["source_requirement_coverage"]), 4),
                },
            }
        )

    return {
        "captured_at": _captured_at(timezone_name),
        "manifest_name": summary["manifest_name"],
        "case_total": len(case_results),
        "cases_passed": passed_cases,
        "target_total": total_targets,
        "targets_passed": passed_targets,
        "cases": case_results,
    }


def render_markdown(report: dict[str, object], *, timezone_name: str) -> str:
    captured_at = datetime.fromisoformat(str(report["captured_at"])).astimezone(ZoneInfo(timezone_name))
    lines = [
        "# Real Corpus Target Evaluation",
        "",
        f"Дата фиксации: `{captured_at:%Y-%m-%d}`",
        "",
        "## 1. Сводка",
        "",
        f"- manifest: `{report['manifest_name']}`",
        f"- cases: `{report['case_total']}`",
        f"- cases_passed: `{report['cases_passed']}`",
        f"- targets_passed: `{report['targets_passed']}/{report['target_total']}`",
        "",
        "## 2. Кейсы",
        "",
    ]
    for case in report["cases"]:
        lines.extend(
            [
                f"### {case['case_id']}",
                "",
                f"- scenario: `{case['scenario']}`",
                f"- difficulty: `{case['difficulty']}`",
                f"- case_passed: `{case['case_passed']}`",
                f"- requirement_f1: `{_format_ratio(float(case['benchmark']['requirement_f1']))}`",
                f"- status_accuracy: `{_format_ratio(float(case['benchmark']['status_accuracy']))}`",
                f"- evidence_f1: `{_format_ratio(float(case['benchmark']['evidence_f1']))}`",
                f"- section_coverage: `{_format_ratio(float(case['benchmark']['section_coverage']))}`",
                "",
            ]
        )
        if case["analysis_focus"]:
            lines.append("Фокусы анализа:")
            lines.extend(f"- `{item}`" for item in case["analysis_focus"])
            lines.append("")
        if case["targets"]:
            lines.append("Сравнение с quality targets:")
            for item in case["targets"]:
                lines.append(
                    f"- `{item['metric']}`: actual `{_format_ratio(float(item['actual']))}` vs target `{_format_ratio(float(item['target']))}` -> `{item['passed']}`"
                )
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = build_report(args.manifest, timezone_name=args.timezone)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report, timezone_name=args.timezone) + "\n", encoding="utf-8")
    print(f"Written {args.output_json}")
    print(f"Written {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
