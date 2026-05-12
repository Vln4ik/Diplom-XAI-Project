#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.quality_benchmark import run_quality_benchmark  # noqa: E402


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_ratio(value: float) -> str:
    return f"{value:.4f}"


def render_markdown(report: dict[str, object]) -> str:
    extraction = report["requirement_extraction"]
    applicability = report["applicability"]
    evidence = report["evidence_linking"]
    sections = report["report_sections"]
    lines = [
        "# Quality Benchmark Results",
        "",
        "Дата фиксации: `2026-05-07`",
        "",
        "## 1. Назначение документа",
        "",
        "Документ фиксирует первые формальные quality-метрики по `gold benchmark` для сценария",
        "`Рособрнадзор + образовательная организация`.",
        "",
        f"- benchmark: `{report['benchmark_name']}`",
        f"- ожидаемых требований: `{report['expected_requirements']}`",
        f"- предсказанных требований: `{report['predicted_requirements']}`",
        "",
        "## 2. Requirement extraction",
        "",
        "| Метрика | Значение |",
        "|---|---:|",
        f"| `precision` | `{_format_ratio(extraction['precision'])}` |",
        f"| `recall` | `{_format_ratio(extraction['recall'])}` |",
        f"| `f1` | `{_format_ratio(extraction['f1'])}` |",
        f"| `category_accuracy` | `{_format_percent(extraction['category_accuracy'])}` |",
        f"| `status_accuracy` | `{_format_percent(extraction['status_accuracy'])}` |",
        f"| `average_match_similarity` | `{_format_ratio(extraction['average_match_similarity'])}` |",
        "",
        "## 3. Applicability",
        "",
        "| Метрика | Значение |",
        "|---|---:|",
        f"| `accuracy` | `{_format_percent(applicability['accuracy'])}` |",
        f"| `matched_total` | `{applicability['matched_total']}` |",
        "",
        "## 4. Evidence linking",
        "",
        "| Метрика | Значение |",
        "|---|---:|",
        f"| `precision` | `{_format_ratio(evidence['precision'])}` |",
        f"| `recall` | `{_format_ratio(evidence['recall'])}` |",
        f"| `f1` | `{_format_ratio(evidence['f1'])}` |",
        f"| `grounded_requirements_share` | `{_format_percent(evidence['grounded_requirements_share'])}` |",
        f"| `matched_evidence_pairs` | `{evidence['matched_total']}` |",
        "",
        "## 5. Report sections",
        "",
        "| Метрика | Значение |",
        "|---|---:|",
        f"| `presence_rate` | `{_format_percent(sections['presence_rate'])}` |",
        f"| `non_empty_content_share` | `{_format_percent(sections['non_empty_content_share'])}` |",
        f"| `source_requirement_coverage` | `{_format_percent(sections['source_requirement_coverage'])}` |",
        f"| `min_source_requirement_pass_share` | `{_format_percent(sections['min_source_requirement_pass_share'])}` |",
        "",
        "## 6. Интерпретация",
        "",
        "- `requirement extraction` показывает, насколько полно система находит эталонные требования из нормативного корпуса.",
        "- `applicability` показывает, насколько корректно система отделяет явно применимые требования от спорных и требующих ручной проверки.",
        "- `evidence linking` показывает, насколько точно система связывает найденные требования с ожидаемыми подтверждениями.",
        "- `report sections` показывает, насколько корректно требования попадают в ожидаемые разделы отчета и не теряются при генерации.",
        "- различие между extraction и evidence-метриками позволяет разделять проблемы извлечения требований и проблемы ранжирования доказательств.",
        "",
        "## 7. Детализация по требованиям",
        "",
    ]
    for item in evidence["per_requirement"]:
        lines.extend(
            [
                f"### {item['expected_id']}",
                "",
                f"- `precision`: `{_format_ratio(item['precision'])}`",
                f"- `recall`: `{_format_ratio(item['recall'])}`",
                f"- `matched_total`: `{item['matched_total']}` из `{item['expected_total']}` ожидаемых evidence",
                "",
            ]
        )
        for match in item["matches"]:
            lines.append(
                f"- expected: `{match['expected_snippet']}` -> predicted: `{match['predicted_snippet']}` "
                f"(similarity `{_format_ratio(match['similarity'])}`)"
            )
        if not item["matches"]:
            lines.append("- совпадения не обнаружены")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    benchmark_path = PROJECT_ROOT / "samples" / "benchmarks" / "rosobrnadzor_quality_benchmark.json"
    report = run_quality_benchmark(benchmark_path)
    output_json = PROJECT_ROOT / "docs" / "quality-benchmark-results.json"
    output_md = PROJECT_ROOT / "docs" / "quality-benchmark-results.md"
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(f"Written {output_json}")
    print(f"Written {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
