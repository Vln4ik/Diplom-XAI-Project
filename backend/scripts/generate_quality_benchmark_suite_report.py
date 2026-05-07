#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.quality_benchmark import run_quality_benchmark_suite  # noqa: E402


def _format_ratio(value: float) -> str:
    return f"{value:.4f}"


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_markdown(report: dict[str, object]) -> str:
    aggregate = report["aggregate"]
    extraction = aggregate["requirement_extraction"]
    evidence = aggregate["evidence_linking"]
    lines = [
        "# Quality Benchmark Suite Results",
        "",
        "Дата фиксации: `2026-05-07`",
        "",
        f"- сценариев в suite: `{report['suite_size']}`",
        "",
        "## 1. Агрегированные метрики",
        "",
        "### Requirement extraction",
        "",
        f"- `precision`: `{_format_ratio(extraction['precision'])}`",
        f"- `recall`: `{_format_ratio(extraction['recall'])}`",
        f"- `f1`: `{_format_ratio(extraction['f1'])}`",
        f"- `category_accuracy_mean`: `{_format_percent(extraction['category_accuracy_mean'])}`",
        f"- `status_accuracy_mean`: `{_format_percent(extraction['status_accuracy_mean'])}`",
        "",
        "### Evidence linking",
        "",
        f"- `precision`: `{_format_ratio(evidence['precision'])}`",
        f"- `recall`: `{_format_ratio(evidence['recall'])}`",
        f"- `f1`: `{_format_ratio(evidence['f1'])}`",
        f"- `grounded_requirements_share_mean`: `{_format_percent(evidence['grounded_requirements_share_mean'])}`",
        "",
        "## 2. Результаты по сценариям",
        "",
    ]
    for benchmark in report["benchmarks"]:
        lines.extend(
            [
                f"### {benchmark['benchmark_name']}",
                "",
                f"- scenario: `{benchmark['scenario']}`",
                f"- extraction F1: `{_format_ratio(benchmark['requirement_extraction']['f1'])}`",
                f"- evidence F1: `{_format_ratio(benchmark['evidence_linking']['f1'])}`",
                f"- evidence precision: `{_format_ratio(benchmark['evidence_linking']['precision'])}`",
                f"- evidence recall: `{_format_ratio(benchmark['evidence_linking']['recall'])}`",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    benchmark_dir = PROJECT_ROOT / "samples" / "benchmarks"
    benchmark_paths = sorted(benchmark_dir.glob("*.json"))
    report = run_quality_benchmark_suite(benchmark_paths)
    output_json = PROJECT_ROOT / "docs" / "quality-benchmark-suite-results.json"
    output_md = PROJECT_ROOT / "docs" / "quality-benchmark-suite-results.md"
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(f"Written {output_json}")
    print(f"Written {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
