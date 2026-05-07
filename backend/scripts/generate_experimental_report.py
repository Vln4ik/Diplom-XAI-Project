#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.experiment import compare_time_ranges, seconds_to_minutes, summarize_min_max_ranges  # noqa: E402

MANUAL_LABELS = {
    "review_regulatory_basis": "Анализ нормативной базы",
    "identify_applicable_requirements": "Выделение и отбор применимых требований",
    "search_and_verify_evidence": "Поиск и проверка evidence",
    "compile_requirement_matrix": "Сборка матрицы требований",
    "draft_report_text": "Подготовка черновика отчёта",
    "internal_alignment_and_revision": "Внутреннее согласование и правки",
}

AUTOMATED_LABELS = {
    "upload_and_categorize_documents": "Загрузка и категоризация документов",
    "verify_processing_and_search_results": "Проверка обработки и результатов поиска",
    "review_requirements_and_risks": "Review требований и рисков",
    "final_editorial_review": "Финальная редакторская проверка",
    "export_and_submit_report": "Экспорт и отправка на согласование",
}

QUALITY_LABELS = {
    "requirement_omission_risk_reduction": "Снижение риска пропуска требования",
    "evidence_completeness_improvement": "Улучшение полноты evidence-покрытия",
    "review_reproducibility_improvement": "Повышение воспроизводимости проверки",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_minutes(value: float) -> str:
    return f"{value:.2f}"


def _format_percent(value: float) -> str:
    return f"{value:.2f}%"


def build_report() -> dict[str, object]:
    assumptions = _load_json(PROJECT_ROOT / "docs" / "experiment-assumptions.json")
    performance = _load_json(PROJECT_ROOT / "docs" / "performance-baseline.json")
    load = _load_json(PROJECT_ROOT / "docs" / "load-baseline.json")

    machine_cycle_seconds = (
        float(performance["summary"]["process_total"]["mean"])
        + float(performance["summary"]["analyze"]["mean"])
        + float(performance["summary"]["generate"]["mean"])
    )
    machine_cycle_minutes = seconds_to_minutes(machine_cycle_seconds)

    manual_summary = summarize_min_max_ranges(assumptions["manual_process_minutes"])
    automated_human_summary = summarize_min_max_ranges(assumptions["automated_human_minutes"])
    automated_total_summary = {
        "min": round(automated_human_summary["min"] + machine_cycle_minutes, 4),
        "max": round(automated_human_summary["max"] + machine_cycle_minutes, 4),
        "midpoint": round(automated_human_summary["midpoint"] + machine_cycle_minutes, 4),
    }
    comparison = compare_time_ranges(
        manual_minutes=manual_summary,
        automated_minutes=automated_total_summary,
    )

    return {
        "scenario": assumptions["scenario"],
        "manual_process_minutes": assumptions["manual_process_minutes"],
        "manual_process_summary_minutes": manual_summary,
        "automated_human_minutes": assumptions["automated_human_minutes"],
        "automated_human_summary_minutes": automated_human_summary,
        "machine_cycle_seconds_mean": round(machine_cycle_seconds, 4),
        "machine_cycle_minutes_mean": machine_cycle_minutes,
        "automated_total_summary_minutes": automated_total_summary,
        "time_comparison": comparison,
        "conservative_reporting_reduction_percent": assumptions["conservative_reporting_reduction_percent"],
        "quality_gain_assumptions_percent": assumptions["quality_gain_assumptions_percent"],
        "quality_proxy_observed": assumptions["quality_proxy_observed"],
        "performance_baseline_snapshot": {
            "process_total_seconds_mean": float(performance["summary"]["process_total"]["mean"]),
            "analyze_seconds_mean": float(performance["summary"]["analyze"]["mean"]),
            "generate_seconds_mean": float(performance["summary"]["generate"]["mean"]),
            "load_generate_seconds_mean": float(load["summary"]["generate"]["mean"]),
            "load_success_rate": float(load["success_rate"]),
            "load_throughput_runs_per_minute": float(load["throughput_runs_per_minute"]),
        },
    }


def render_markdown(report: dict[str, object]) -> str:
    manual_steps = report["manual_process_minutes"]
    automated_steps = report["automated_human_minutes"]
    manual_summary = report["manual_process_summary_minutes"]
    automated_human_summary = report["automated_human_summary_minutes"]
    automated_total = report["automated_total_summary_minutes"]
    comparison = report["time_comparison"]
    quality_assumptions = report["quality_gain_assumptions_percent"]
    quality_proxy = report["quality_proxy_observed"]
    perf = report["performance_baseline_snapshot"]
    conservative = report["conservative_reporting_reduction_percent"]

    lines = [
        "# Experimental Results",
        "",
        "Дата фиксации: `2026-05-07`",
        "",
        "## 1. Назначение документа",
        "",
        "Документ фиксирует формализованную экспериментальную сводку по сценарию",
        "`Рособрнадзор + образовательная организация` и сравнивает:",
        "",
        "- ручной процесс подготовки отчёта",
        "- автоматизированный процесс с использованием `XAI Report Builder`",
        "",
        "## 2. Базовый сценарий сравнения",
        "",
        "- входной пакет: `4` документа",
        "- после анализа: `3` требования",
        "- после генерации: `9` разделов отчёта",
        "- export-артефакты: `DOCX`, `XLSX`, `ZIP`, `HTML explanations`",
        "",
        "## 3. Ручной процесс: принятые временные допущения",
        "",
        "| Этап | Min, мин | Max, мин |",
        "|---|---:|---:|",
    ]
    for title, values in manual_steps.items():
        label = MANUAL_LABELS.get(title, title)
        lines.append(f"| {label} | `{_format_minutes(values['min'])}` | `{_format_minutes(values['max'])}` |")
    lines.extend(
        [
            f"| `Итого` | `{_format_minutes(manual_summary['min'])}` | `{_format_minutes(manual_summary['max'])}` |",
            "",
            "## 4. Автоматизированный процесс: принятые временные допущения",
            "",
            "| Этап | Min, мин | Max, мин |",
            "|---|---:|---:|",
        ]
    )
    for title, values in automated_steps.items():
        label = AUTOMATED_LABELS.get(title, title)
        lines.append(f"| {label} | `{_format_minutes(values['min'])}` | `{_format_minutes(values['max'])}` |")
    lines.extend(
        [
            f"| `Итого ручных действий пользователя` | `{_format_minutes(automated_human_summary['min'])}` | `{_format_minutes(automated_human_summary['max'])}` |",
            "",
            "## 5. Фактически измеренный машинный цикл",
            "",
            f"- `process_total`: `{perf['process_total_seconds_mean']:.4f}s`",
            f"- `analyze`: `{perf['analyze_seconds_mean']:.4f}s`",
            f"- `generate`: `{perf['generate_seconds_mean']:.4f}s`",
            f"- полный машинный цикл: `{report['machine_cycle_seconds_mean']:.4f}s` (`{_format_minutes(report['machine_cycle_minutes_mean'])}` мин)",
            "",
            "## 6. Сводное сравнение времени",
            "",
            "| Сценарий | Min, мин | Max, мин | Midpoint, мин |",
            "|---|---:|---:|---:|",
            f"| `Ручной процесс` | `{_format_minutes(manual_summary['min'])}` | `{_format_minutes(manual_summary['max'])}` | `{_format_minutes(manual_summary['midpoint'])}` |",
            f"| `Автоматизированный процесс (человек + система)` | `{_format_minutes(automated_total['min'])}` | `{_format_minutes(automated_total['max'])}` | `{_format_minutes(automated_total['midpoint'])}` |",
            "",
            "## 7. Выигрыш по времени",
            "",
            f"- минимально ожидаемая экономия времени: `{_format_minutes(comparison['min_minutes_saved'])}` мин",
            f"- максимально ожидаемая экономия времени: `{_format_minutes(comparison['max_minutes_saved'])}` мин",
            f"- экономия времени по midpoint-сценарию: `{_format_minutes(comparison['midpoint_minutes_saved'])}` мин",
            f"- reduction в худшем случае: `{_format_percent(comparison['min_reduction_percent'])}`",
            f"- reduction в лучшем случае: `{_format_percent(comparison['max_reduction_percent'])}`",
            f"- reduction по midpoint-сценарию: `{_format_percent(comparison['midpoint_reduction_percent'])}`",
            "",
            "Для публичной и дипломной коммуникации используется более консервативный интервал:",
            f"`{_format_percent(conservative['min'])} - {_format_percent(conservative['max'])}`.",
            "",
            "## 8. Proxy-метрики качества, уже подтверждённые системой",
            "",
            f"- `documents_processed_share`: `{_format_percent(quality_proxy['documents_processed_share'] * 100)}`",
            f"- `evidence_coverage`: `{_format_percent(quality_proxy['evidence_coverage'] * 100)}`",
            f"- `xai_coverage`: `{_format_percent(quality_proxy['xai_coverage'] * 100)}`",
            f"- `export_success_rate`: `{_format_percent(quality_proxy['export_success_rate'] * 100)}`",
            f"- `requirements_count`: `{quality_proxy['requirements_count']}`",
            f"- `sections_count`: `{quality_proxy['sections_count']}`",
            "",
            "## 9. Предварительная экспертно-инженерная оценка прироста качества",
            "",
            "| Показатель | Предполагаемый диапазон улучшения |",
            "|---|---:|",
        ]
    )
    for title, values in quality_assumptions.items():
        label = QUALITY_LABELS.get(title, title)
        lines.append(f"| {label} | `{_format_percent(values['min'])} - {_format_percent(values['max'])}` |")
    lines.extend(
        [
            "",
            "## 10. Параллельная нагрузка",
            "",
            f"- `generate` при `2x concurrency`: `{perf['load_generate_seconds_mean']:.4f}s`",
            f"- `load success rate`: `{_format_percent(perf['load_success_rate'] * 100)}`",
            f"- `throughput`: `{perf['load_throughput_runs_per_minute']:.4f}` runs/min",
            "",
            "## 11. Интерпретация результатов",
            "",
            "Текущие данные позволяют сделать следующие выводы:",
            "",
            "- система уже демонстрирует воспроизводимый машинный цикл подготовки отчёта;",
            "- даже с учётом ручного review автоматизированный сценарий существенно короче ручного;",
            "- на demo dataset достигается полное покрытие evidence/XAI/export по текущему сценарию;",
            "- главный узкий участок при нагрузке — генерация разделов отчёта.",
            "",
            "## 12. Ограничения эксперимента",
            "",
            "- временные оценки ручного сценария являются экспертно-инженерными допущениями;",
            "- quality improvement пока не выражен через `precision/recall/F1`;",
            "- сравнение построено на demo dataset малого объёма;",
            "- для строгой научной валидации нужен отдельный gold benchmark и экспертная разметка.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    report = build_report()
    output_json = PROJECT_ROOT / "docs" / "experimental-results.json"
    output_md = PROJECT_ROOT / "docs" / "experimental-results.md"
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(f"Written {output_json}")
    print(f"Written {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
