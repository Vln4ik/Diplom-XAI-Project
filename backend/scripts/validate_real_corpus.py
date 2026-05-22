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

from app.services.real_corpus import summarize_real_corpus_manifest  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate real corpus manifest and render readiness report.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "samples" / "real_corpus" / "manifests" / "pilot-redacted.json",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=PROJECT_ROOT / "docs" / "real-corpus-status.json",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=PROJECT_ROOT / "docs" / "real-corpus-status.md",
    )
    parser.add_argument("--timezone", default="Europe/Moscow")
    return parser.parse_args()


def _captured_date(timezone_name: str) -> str:
    return f"{datetime.now(ZoneInfo(timezone_name)):%Y-%m-%d}"


def _format_counter(counter: dict[str, object]) -> list[str]:
    lines: list[str] = []
    for key, value in counter.items():
        lines.append(f"- `{key}`: `{value}`")
    return lines or ["- данных нет"]


def render_markdown(report: dict[str, object], *, timezone_name: str) -> str:
    lines = [
        "# Real Corpus Status",
        "",
        f"Дата фиксации: `{_captured_date(timezone_name)}`",
        "",
        "## 1. Назначение документа",
        "",
        "Документ фиксирует структуру и readiness pilot real-world corpus слоя,",
        "который используется как мост между committed demo corpus и будущим",
        "расширенным benchmark-корпусом на более реалистичных кейсах.",
        "",
        f"- manifest: `{report['manifest_name']}`",
        f"- total cases: `{report['case_total']}`",
        f"- benchmark-ready cases: `{report['benchmark_ready_case_total']}`",
        f"- total issues: `{report['issue_total']}`",
        "",
        "## 2. Сводные распределения",
        "",
        "### Статусы кейсов",
        "",
    ]
    lines.extend(_format_counter(dict(report["case_status_counts"])))
    lines.extend(
        [
            "",
            "### Уровни редактирования",
            "",
        ]
    )
    lines.extend(_format_counter(dict(report["redaction_level_counts"])))
    lines.extend(
        [
            "",
            "### Категории документов",
            "",
        ]
    )
    lines.extend(_format_counter(dict(report["document_category_counts"])))
    lines.extend(
        [
            "",
            "### Форматы документов",
            "",
        ]
    )
    lines.extend(_format_counter(dict(report["document_format_counts"])))
    lines.extend(
        [
            "",
            "## 3. Кейсы pilot корпуса",
            "",
        ]
    )
    for case in report["cases"]:
        lines.extend(
            [
                f"### {case['case_id']}",
                "",
                f"- scenario: `{case['scenario']}`",
                f"- status: `{case['status']}`",
                f"- report_type: `{case['report_type']}`",
                f"- redaction_level: `{case['redaction_level']}`",
                f"- documents: `{case['document_total']}`",
                f"- benchmark_ready: `{case['benchmark_ready']}`",
                f"- benchmark_path: `{case['benchmark_path']}`",
                "",
            ]
        )
        if case["issues"]:
            lines.append("Проблемы:")
            lines.extend(f"- {issue}" for issue in case["issues"])
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = summarize_real_corpus_manifest(args.manifest)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report, timezone_name=args.timezone) + "\n", encoding="utf-8")
    print(f"Written {args.output_json}")
    print(f"Written {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
