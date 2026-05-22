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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a markdown report from a benchmark JSON artifact.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--timezone", default="Europe/Moscow")
    parser.add_argument("--notes")
    return parser.parse_args()


def _load_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_date(captured_at: str, timezone_name: str) -> str:
    try:
        dt = datetime.fromisoformat(captured_at)
        local_dt = dt.astimezone(ZoneInfo(timezone_name))
        return f"{local_dt:%Y-%m-%d} ({timezone_name})"
    except Exception:
        return captured_at


def _format_float(value: object, digits: int = 4) -> str:
    if not isinstance(value, int | float):
        return str(value)
    return f"{float(value):.{digits}f}"


def _build_stage_table(summary: dict[str, object]) -> list[str]:
    lines = [
        "| Этап | Mean, s | P95, s |",
        "|---|---:|---:|",
    ]
    for stage, metrics in summary.items():
        if not isinstance(metrics, dict):
            continue
        lines.append(
            f"| `{stage}` | `{_format_float(metrics.get('mean', 0.0))}` | `{_format_float(metrics.get('p95', 0.0))}` |"
        )
    return lines


def _build_resource_section(resource_profile: dict[str, object]) -> list[str]:
    lines = ["## Ресурсный профиль"]
    mode = str(resource_profile.get("mode") or "unknown")
    lines.append("")
    lines.append(f"- mode: `{mode}`")
    if resource_profile.get("resource_alias"):
        lines.append(f"- host alias: `{resource_profile['resource_alias']}`")
    if resource_profile.get("process_match"):
        lines.append(f"- host process match: `{resource_profile['process_match']}`")
    lines.append(f"- sample interval: `{resource_profile.get('sample_interval_seconds', 0.0)}s`")
    lines.append(f"- sample count: `{resource_profile.get('sample_count', 0)}`")
    lines.append("")

    summary = resource_profile.get("summary")
    if not isinstance(summary, dict):
        return lines

    for service_name, metrics in summary.items():
        if not isinstance(metrics, dict):
            continue
        lines.append(f"### {service_name}")
        lines.append("")
        for metric_name, metric_values in metrics.items():
            if not isinstance(metric_values, dict):
                continue
            lines.append(f"- `{metric_name} mean`: `{_format_float(metric_values.get('mean', 0.0))}`")
            lines.append(f"- `{metric_name} p95`: `{_format_float(metric_values.get('p95', 0.0))}`")
        lines.append("")
    return lines


def render_markdown(
    payload: dict[str, object],
    *,
    title: str,
    timezone_name: str,
    notes: str | None,
    input_name: str,
) -> str:
    captured_at = str(payload.get("captured_at") or "")
    summary = payload.get("summary")
    resource_profile = payload.get("resource_profile")
    ai_status = payload.get("ai_status")
    samples = payload.get("samples")
    query = payload.get("query")

    lines = [
        f"# {title}",
        "",
        f"Дата фиксации: `{_format_date(captured_at, timezone_name)}`",
        "",
        "## Контур измерения",
        "",
        "- Backend: `FastAPI + PostgreSQL + pgvector + Celery`",
    ]

    if isinstance(ai_status, dict):
        embeddings = ai_status.get("embeddings")
        llm = ai_status.get("llm")
        if isinstance(embeddings, dict):
            lines.append(
                f"- Embeddings: `{embeddings.get('provider')} + {embeddings.get('configured_model')}`"
            )
        if isinstance(llm, dict):
            lines.append(f"- LLM: `{llm.get('provider')} + {llm.get('configured_model')}`")

    if isinstance(samples, list) and samples:
        lines.append("- Dataset:")
        for sample in samples:
            lines.append(f"  - `{sample}`")

    if isinstance(query, str) and query:
        lines.append(f"- Query: `{query}`")

    lines.extend(
        [
            f"- Profile: `{payload.get('concurrency', 0)}` параллельных пользовательских прогона",
        ]
    )
    if isinstance(resource_profile, dict):
        mode = str(resource_profile.get("mode") or "unknown")
        lines.append(f"- Resource sampler: `{mode}`")

    lines.extend(
        [
            "",
            f"Полный raw output сохранён в [{input_name}]({input_name}).",
            "",
            "## Итог профиля",
            "",
            f"- `requested_runs`: `{payload.get('requested_runs', 0)}`",
            f"- `completed_runs`: `{payload.get('completed_runs', 0)}`",
            f"- `failed_runs`: `{payload.get('failed_runs', 0)}`",
            f"- `concurrency`: `{payload.get('concurrency', 0)}`",
            f"- `total_wall_time_seconds`: `{_format_float(payload.get('total_wall_time_seconds', 0.0))}`",
            f"- `throughput_runs_per_minute`: `{_format_float(payload.get('throughput_runs_per_minute', 0.0))}`",
            f"- `success_rate`: `{_format_float(payload.get('success_rate', 0.0))}`",
            "",
            "## Сводка по этапам",
            "",
        ]
    )

    if isinstance(summary, dict):
        lines.extend(_build_stage_table(summary))

    lines.append("")
    if isinstance(resource_profile, dict):
        lines.extend(_build_resource_section(resource_profile))

    lines.extend(
        [
            "## Выводы",
            "",
        ]
    )

    generate_summary = summary.get("generate") if isinstance(summary, dict) else None
    process_summary = summary.get("process_total") if isinstance(summary, dict) else None
    analyze_summary = summary.get("analyze") if isinstance(summary, dict) else None
    if isinstance(generate_summary, dict):
        lines.append(
            f"- Главным bottleneck остаётся `generate`: mean `{_format_float(generate_summary.get('mean', 0.0))}s`, p95 `{_format_float(generate_summary.get('p95', 0.0))}s`."
        )
    if isinstance(process_summary, dict) and isinstance(analyze_summary, dict):
        lines.append(
            f"- `process_total` (`{_format_float(process_summary.get('mean', 0.0))}s`) и `analyze` (`{_format_float(analyze_summary.get('mean', 0.0))}s`) остаются стабильными относительно генерации."
        )
    if isinstance(resource_profile, dict):
        mode = str(resource_profile.get("mode") or "")
        if mode == "hybrid":
            lines.append("- Профиль впервые включает одновременно Docker-контейнеры и host-level `Ollama`, поэтому виден реальный вклад локального AI runtime.")
        if isinstance(resource_profile.get("summary"), dict) and "host_ollama" in resource_profile["summary"]:
            host_ollama = resource_profile["summary"]["host_ollama"]
            if isinstance(host_ollama, dict):
                cpu_metric = host_ollama.get("cpu_percent")
                memory_metric = host_ollama.get("memory_mib")
                if isinstance(cpu_metric, dict) and isinstance(memory_metric, dict):
                    lines.append(
                        f"- `host_ollama` под `4x` нагрузкой доходит до p95 CPU `{_format_float(cpu_metric.get('p95', 0.0))}` и p95 memory `{_format_float(memory_metric.get('p95', 0.0))} MiB`."
                    )

    if notes:
        lines.extend(["", "## Дополнительные замечания", "", notes])

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    payload = _load_payload(args.input)
    rendered = render_markdown(
        payload,
        title=args.title,
        timezone_name=args.timezone,
        notes=args.notes,
        input_name=args.input.name,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Written {args.output}")
    return 0


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(main())
