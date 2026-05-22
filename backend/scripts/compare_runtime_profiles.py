#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SCRIPT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_ROOT.parents[1]
RUN_BENCHMARK_PROFILE = SCRIPT_ROOT / "run_benchmark_profile.py"

RUNTIME_PRESETS: dict[str, dict[str, str]] = {
    "fallback": {
        "embedding_provider": "hash",
        "llm_provider": "fallback",
        "label": "hash-fallback + template-fallback",
    },
    "ollama": {
        "embedding_provider": "ollama",
        "llm_provider": "ollama",
        "ollama_base_url": "http://host.docker.internal:11434/api",
        "label": "ollama + all-minilm + gemma3:270m",
    },
}

PROFILE_CHOICES = ("performance", "load-2x", "stress-3x", "stress-4x")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare fallback and Ollama runtimes on the same benchmark profile.")
    parser.add_argument("profile", choices=PROFILE_CHOICES, default="performance", nargs="?")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="ChangeMe123!")
    parser.add_argument("--wait-timeout", type=float, default=180.0)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--output-prefix", type=Path)
    parser.add_argument("--timezone", default="Europe/Moscow")
    return parser.parse_args()


def _request_json(url: str, *, timeout: float = 30.0) -> dict[str, object]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {detail or exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Connection failed for {url}: {exc.reason}") from exc


def _run_command(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=PROJECT_ROOT, env=env, text=True, capture_output=True, check=False)


def _format_command_error(fallback_message: str, result: subprocess.CompletedProcess[str]) -> str:
    details = result.stderr.strip() or result.stdout.strip()
    return details or fallback_message


def _ensure_compose_services() -> None:
    result = _run_command(["docker", "compose", "-f", "infra/docker-compose.yml", "up", "-d", "postgres", "redis"])
    if result.returncode != 0:
        raise RuntimeError(_format_command_error("Failed to start postgres/redis", result))


def _runtime_env(runtime_name: str) -> dict[str, str]:
    preset = RUNTIME_PRESETS[runtime_name]
    env = os.environ.copy()
    env["XAI_APP_EMBEDDING_PROVIDER"] = preset["embedding_provider"]
    env["XAI_APP_LLM_PROVIDER"] = preset["llm_provider"]
    env["XAI_APP_OLLAMA_BASE_URL"] = preset.get("ollama_base_url", "http://host.docker.internal:11434/api")
    return env


def _restart_runtime(runtime_name: str) -> None:
    result = _run_command(
        [
            "docker",
            "compose",
            "-f",
            "infra/docker-compose.yml",
            "up",
            "-d",
            "--force-recreate",
            "backend",
            "worker",
        ],
        env=_runtime_env(runtime_name),
    )
    if result.returncode != 0:
        raise RuntimeError(_format_command_error(f"Failed to restart runtime {runtime_name}", result))


def _wait_for_runtime(*, base_url: str, runtime_name: str, timeout_seconds: float, interval_seconds: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    preset = RUNTIME_PRESETS[runtime_name]
    last_error = "unknown runtime wait failure"

    while time.monotonic() < deadline:
        try:
            health = _request_json(f"{base_url.rstrip('/')}/api/system/health")
            ai_status = _request_json(f"{base_url.rstrip('/')}/api/system/ai-status")
            runtime = health.get("runtime", {})
            if not isinstance(runtime, dict):
                raise RuntimeError("Health runtime payload is malformed")

            if runtime.get("embedding_provider") != preset["embedding_provider"]:
                raise RuntimeError(f"Embedding provider mismatch: {runtime.get('embedding_provider')}")
            if runtime.get("llm_provider") != preset["llm_provider"]:
                raise RuntimeError(f"LLM provider mismatch: {runtime.get('llm_provider')}")

            embeddings = ai_status.get("embeddings", {})
            llm = ai_status.get("llm", {})
            if not isinstance(embeddings, dict) or not isinstance(llm, dict):
                raise RuntimeError("AI status payload is malformed")

            if runtime_name == "ollama":
                if embeddings.get("provider") != "ollama":
                    raise RuntimeError(f"Embedding provider not ready: {embeddings.get('provider')}")
                if llm.get("provider") != "ollama":
                    raise RuntimeError(f"LLM provider not ready: {llm.get('provider')}")
                if embeddings.get("mode") != "model":
                    raise RuntimeError(f"Embedding runtime not ready: {embeddings.get('mode')}")
                if llm.get("mode") != "model":
                    raise RuntimeError(f"LLM runtime not ready: {llm.get('mode')}")
                if not bool(embeddings.get("reachable")) or not bool(embeddings.get("model_available")):
                    raise RuntimeError("Embedding model is not reachable via Ollama")
                if not bool(llm.get("reachable")) or not bool(llm.get("model_available")):
                    raise RuntimeError("LLM model is not reachable via Ollama")
            else:
                if embeddings.get("provider") != "hash-fallback":
                    raise RuntimeError(f"Unexpected fallback embedding provider: {embeddings.get('provider')}")
                if llm.get("provider") != "template-fallback":
                    raise RuntimeError(f"Unexpected fallback llm provider: {llm.get('provider')}")
                if embeddings.get("mode") != "fallback":
                    raise RuntimeError(f"Fallback embedding mode mismatch: {embeddings.get('mode')}")
                if llm.get("mode") != "fallback":
                    raise RuntimeError(f"Fallback llm mode mismatch: {llm.get('mode')}")

            return {"health": health, "ai_status": ai_status}
        except Exception as exc:
            last_error = str(exc)
            time.sleep(interval_seconds)

    raise RuntimeError(f"Timed out waiting for runtime {runtime_name}: {last_error}")


def _default_output_prefix(profile: str) -> Path:
    return PROJECT_ROOT / "docs" / f"runtime-comparison-{profile}"


def _runtime_output_path(prefix: Path, runtime_name: str) -> Path:
    return prefix.parent / f"{prefix.name}-{runtime_name}.json"


def _run_benchmark(profile: str, *, base_url: str, email: str, password: str, output_path: Path) -> dict[str, object]:
    command = [
        sys.executable,
        str(RUN_BENCHMARK_PROFILE),
        profile,
        "--base-url",
        base_url,
        "--email",
        email,
        "--password",
        password,
        "--output",
        str(output_path),
    ]
    result = _run_command(command)
    if result.returncode != 0:
        raise RuntimeError(_format_command_error(f"Benchmark profile {profile} failed", result))

    if not output_path.exists():
        raise RuntimeError(f"Expected benchmark artifact not found: {output_path}")
    return json.loads(output_path.read_text(encoding="utf-8"))


def _metric_delta(baseline: float, candidate: float) -> dict[str, float]:
    delta = round(candidate - baseline, 4)
    if baseline == 0:
        delta_percent = 0.0
    else:
        delta_percent = round(delta / baseline * 100.0, 2)
    return {"delta": delta, "delta_percent": delta_percent}


def _common_stage_keys(fallback_payload: dict[str, object], ollama_payload: dict[str, object]) -> list[str]:
    fallback_summary = fallback_payload.get("summary", {})
    ollama_summary = ollama_payload.get("summary", {})
    if not isinstance(fallback_summary, dict) or not isinstance(ollama_summary, dict):
        return []
    return sorted(set(fallback_summary) & set(ollama_summary))


def build_comparison_payload(profile: str, fallback_payload: dict[str, object], ollama_payload: dict[str, object]) -> dict[str, object]:
    stage_comparison: dict[str, dict[str, object]] = {}
    fallback_summary = fallback_payload.get("summary", {})
    ollama_summary = ollama_payload.get("summary", {})
    if isinstance(fallback_summary, dict) and isinstance(ollama_summary, dict):
        for stage in _common_stage_keys(fallback_payload, ollama_payload):
            fallback_metrics = fallback_summary.get(stage, {})
            ollama_metrics = ollama_summary.get(stage, {})
            if not isinstance(fallback_metrics, dict) or not isinstance(ollama_metrics, dict):
                continue
            fallback_mean = float(fallback_metrics.get("mean", 0.0))
            ollama_mean = float(ollama_metrics.get("mean", 0.0))
            stage_comparison[stage] = {
                "fallback_mean": fallback_mean,
                "ollama_mean": ollama_mean,
                "fallback_p95": float(fallback_metrics.get("p95", 0.0)),
                "ollama_p95": float(ollama_metrics.get("p95", 0.0)),
                **_metric_delta(fallback_mean, ollama_mean),
            }

    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "profile": profile,
        "runtime_order": ["fallback", "ollama"],
        "runtime_labels": {
            "fallback": RUNTIME_PRESETS["fallback"]["label"],
            "ollama": RUNTIME_PRESETS["ollama"]["label"],
        },
        "fallback": fallback_payload,
        "ollama": ollama_payload,
        "headline_metrics": {
            "total_wall_time_seconds": {
                "fallback": float(fallback_payload.get("total_wall_time_seconds", 0.0)),
                "ollama": float(ollama_payload.get("total_wall_time_seconds", 0.0)),
                **_metric_delta(
                    float(fallback_payload.get("total_wall_time_seconds", 0.0)),
                    float(ollama_payload.get("total_wall_time_seconds", 0.0)),
                ),
            },
            "throughput_runs_per_minute": {
                "fallback": float(fallback_payload.get("throughput_runs_per_minute", 0.0)),
                "ollama": float(ollama_payload.get("throughput_runs_per_minute", 0.0)),
                **_metric_delta(
                    float(fallback_payload.get("throughput_runs_per_minute", 0.0)),
                    float(ollama_payload.get("throughput_runs_per_minute", 0.0)),
                ),
            },
        },
        "stage_comparison": stage_comparison,
    }


def _format_float(value: object, digits: int = 4) -> str:
    if not isinstance(value, int | float):
        return str(value)
    return f"{float(value):.{digits}f}"


def _format_date(value: str, timezone_name: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
        return f"{dt.astimezone(ZoneInfo(timezone_name)):%Y-%m-%d} ({timezone_name})"
    except Exception:
        return value


def _provider_line(payload: dict[str, object]) -> str:
    ai_status = payload.get("ai_status")
    if not isinstance(ai_status, dict):
        return "недоступно"
    embeddings = ai_status.get("embeddings")
    llm = ai_status.get("llm")
    if not isinstance(embeddings, dict) or not isinstance(llm, dict):
        return "недоступно"

    embedding_label = str(embeddings.get("provider") or "unknown")
    llm_label = str(llm.get("provider") or "unknown")
    embedding_model = embeddings.get("configured_model")
    llm_model = llm.get("configured_model")
    if embedding_model:
        embedding_label = f"{embedding_label} ({embedding_model})"
    if llm_model:
        llm_label = f"{llm_label} ({llm_model})"
    return f"embeddings `{embedding_label}`, llm `{llm_label}`"


def _format_delta_percent(payload: dict[str, object]) -> str:
    return f"{float(payload['delta_percent']):+.2f}%"


def render_markdown(
    comparison: dict[str, object],
    *,
    timezone_name: str,
    fallback_json_name: str,
    ollama_json_name: str,
) -> str:
    headline_metrics = comparison.get("headline_metrics", {})
    stage_comparison = comparison.get("stage_comparison", {})
    fallback_payload = comparison.get("fallback", {})
    ollama_payload = comparison.get("ollama", {})
    runtime_labels = comparison.get("runtime_labels", {})
    fallback_name = runtime_labels.get("fallback", "fallback")
    ollama_name = runtime_labels.get("ollama", "ollama")
    captured_at = _format_date(str(comparison.get("captured_at") or ""), timezone_name)

    lines = [
        f"# Сравнение runtime-профилей: fallback vs Ollama ({comparison['profile']})",
        "",
        f"Дата фиксации: `{captured_at}`",
        "",
        "## Сценарий",
        "",
        f"- profile: `{comparison['profile']}`",
        f"- fallback runtime: `{fallback_name}`",
        f"- ollama runtime: `{ollama_name}`",
        f"- fallback providers: {_provider_line(fallback_payload if isinstance(fallback_payload, dict) else {})}",
        f"- ollama providers: {_provider_line(ollama_payload if isinstance(ollama_payload, dict) else {})}",
        f"- raw fallback artifact: [{fallback_json_name}]({fallback_json_name})",
        f"- raw ollama artifact: [{ollama_json_name}]({ollama_json_name})",
        "",
        "## Ключевые метрики",
        "",
        "| Метрика | Fallback | Ollama | Delta | Delta % |",
        "|---|---:|---:|---:|---:|",
    ]

    if isinstance(headline_metrics, dict):
        for metric_name, payload in headline_metrics.items():
            if not isinstance(payload, dict):
                continue
            lines.append(
                f"| `{metric_name}` | `{float(payload['fallback']):.4f}` | `{float(payload['ollama']):.4f}` | `{float(payload['delta']):+.4f}` | `{_format_delta_percent(payload)}` |"
            )

    lines.extend(
        [
            "",
            "## Сравнение по этапам",
            "",
            "| Этап | Fallback mean, s | Ollama mean, s | Delta, s | Delta % |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    if isinstance(stage_comparison, dict):
        for stage, payload in stage_comparison.items():
            if not isinstance(payload, dict):
                continue
            lines.append(
                f"| `{stage}` | `{float(payload['fallback_mean']):.4f}` | `{float(payload['ollama_mean']):.4f}` | `{float(payload['delta']):+.4f}` | `{_format_delta_percent(payload)}` |"
            )

    generate_metrics = stage_comparison.get("generate") if isinstance(stage_comparison, dict) else None
    process_metrics = stage_comparison.get("process_total") if isinstance(stage_comparison, dict) else None
    analyze_metrics = stage_comparison.get("analyze") if isinstance(stage_comparison, dict) else None
    throughput_metrics = headline_metrics.get("throughput_runs_per_minute") if isinstance(headline_metrics, dict) else None

    lines.extend(
        [
            "",
            "## Интерпретация",
            "",
            "- Это сравнение показывает именно runtime-стоимость локальной модели, а не формальную semantic-оценку качества текста.",
            "- `fallback` режим опирается на `hash-fallback` embeddings и `template-fallback` generation, поэтому служит нижней границей по latency.",
            "- `Ollama` режим нужен не ради скорости, а ради более естественной генерации narrative sections при сохранении evidence-grounded pipeline.",
        ]
    )
    if isinstance(generate_metrics, dict):
        lines.append(
            f"- Наибольшая разница сосредоточена в `generate`: mean `{_format_float(generate_metrics.get('fallback_mean'))}s` -> `{_format_float(generate_metrics.get('ollama_mean'))}s` ({_format_delta_percent(generate_metrics)})."
        )
    if isinstance(process_metrics, dict) and isinstance(analyze_metrics, dict):
        lines.append(
            f"- Доменные этапы `process_total` и `analyze` меняются умеренно: `{_format_float(process_metrics.get('fallback_mean'))}s` -> `{_format_float(process_metrics.get('ollama_mean'))}s` и `{_format_float(analyze_metrics.get('fallback_mean'))}s` -> `{_format_float(analyze_metrics.get('ollama_mean'))}s`."
        )
    if isinstance(throughput_metrics, dict):
        lines.append(
            f"- Throughput меняется с `{_format_float(throughput_metrics.get('fallback'))}` до `{_format_float(throughput_metrics.get('ollama'))}` runs/min ({_format_delta_percent(throughput_metrics)})."
        )
    lines.extend(
        [
            "- Если различия по `process_total` и `analyze` малы, значит bottleneck сосредоточен в генеративном слое, а не в основном document/retrieval/XAI pipeline.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_prefix = args.output_prefix or _default_output_prefix(args.profile)
    fallback_output = _runtime_output_path(output_prefix, "fallback")
    ollama_output = _runtime_output_path(output_prefix, "ollama")
    comparison_output = output_prefix.with_suffix(".json")
    comparison_md_output = output_prefix.with_suffix(".md")

    _ensure_compose_services()
    artifacts: dict[str, dict[str, object]] = {}

    try:
        for runtime_name, output_path in (("fallback", fallback_output), ("ollama", ollama_output)):
            _restart_runtime(runtime_name)
            _wait_for_runtime(
                base_url=args.base_url,
                runtime_name=runtime_name,
                timeout_seconds=args.wait_timeout,
                interval_seconds=args.poll_interval,
            )
            artifacts[runtime_name] = _run_benchmark(
                args.profile,
                base_url=args.base_url,
                email=args.email,
                password=args.password,
                output_path=output_path,
            )

        comparison = build_comparison_payload(args.profile, artifacts["fallback"], artifacts["ollama"])
        comparison_output.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        comparison_md_output.write_text(
            render_markdown(
                comparison,
                timezone_name=args.timezone,
                fallback_json_name=fallback_output.name,
                ollama_json_name=ollama_output.name,
            )
            + "\n",
            encoding="utf-8",
        )
    finally:
        _restart_runtime("ollama")
        _wait_for_runtime(
            base_url=args.base_url,
            runtime_name="ollama",
            timeout_seconds=args.wait_timeout,
            interval_seconds=args.poll_interval,
        )

    print(f"Written {comparison_output}")
    print(f"Written {comparison_md_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
