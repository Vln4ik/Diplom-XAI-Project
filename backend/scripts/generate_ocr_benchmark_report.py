#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ocr_benchmark import run_ocr_benchmark  # noqa: E402


def _format_ratio(value: float) -> str:
    return f"{value:.4f}"


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_markdown(report: dict[str, object]) -> str:
    aggregate = report["aggregate"]
    lines = [
        "# OCR Benchmark Results",
        "",
        "Дата фиксации: `2026-05-12`",
        "",
        f"- benchmark: `{report['benchmark_name']}`",
        f"- OCR provider: `{report['ocr_provider']['provider']}`",
        f"- mode: `{report['ocr_provider']['mode']}`",
        "",
        "## 1. Агрегированные метрики",
        "",
        f"- `case_total`: `{aggregate['case_total']}`",
        f"- `char_similarity_mean`: `{_format_ratio(aggregate['char_similarity_mean'])}`",
        f"- `token_precision_mean`: `{_format_ratio(aggregate['token_precision_mean'])}`",
        f"- `token_recall_mean`: `{_format_ratio(aggregate['token_recall_mean'])}`",
        f"- `token_f1_mean`: `{_format_ratio(aggregate['token_f1_mean'])}`",
        f"- `keyword_coverage_mean`: `{_format_ratio(aggregate['keyword_coverage_mean'])}`",
        f"- `requires_review_rate`: `{_format_percent(aggregate['requires_review_rate'])}`",
        "",
        "## 2. По форматам",
        "",
    ]

    for fmt, summary in report["by_format"].items():
        lines.extend(
            [
                f"### {fmt}",
                "",
                f"- `case_total`: `{summary['case_total']}`",
                f"- `char_similarity_mean`: `{_format_ratio(summary['char_similarity_mean'])}`",
                f"- `token_f1_mean`: `{_format_ratio(summary['token_f1_mean'])}`",
                f"- `keyword_coverage_mean`: `{_format_ratio(summary['keyword_coverage_mean'])}`",
                f"- `requires_review_rate`: `{_format_percent(summary['requires_review_rate'])}`",
                "",
            ]
        )

    lines.extend(
        [
            "## 3. По сценариям",
            "",
        ]
    )
    for case in report["cases"]:
        lines.extend(
            [
                f"### {case['benchmark_id']}",
                "",
                f"- scenario: `{case['scenario']}`",
                f"- file: `{case['file_name']}`",
                f"- format: `{case['format']}`",
                f"- `requires_review`: `{case['requires_review']}`",
                f"- `char_similarity`: `{_format_ratio(case['char_similarity'])}`",
                f"- `token_f1`: `{_format_ratio(case['token_f1'])}`",
                f"- `keyword_coverage`: `{_format_ratio(case['keyword_coverage'])}`",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    manifest_path = PROJECT_ROOT / "samples" / "ocr_benchmarks" / "ocr_benchmark_manifest.json"
    report = run_ocr_benchmark(manifest_path)
    output_json = PROJECT_ROOT / "docs" / "ocr-benchmark-results.json"
    output_md = PROJECT_ROOT / "docs" / "ocr-benchmark-results.md"
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(f"Written {output_json}")
    print(f"Written {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
