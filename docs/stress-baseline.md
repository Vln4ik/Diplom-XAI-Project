# Stress Baseline

Дата фиксации: `2026-05-07` (`Europe/Moscow`)

## Контур измерения

- Backend: `FastAPI + PostgreSQL + pgvector + Celery`
- Embeddings: `Ollama + all-minilm`
- LLM: `Ollama + gemma3:270m`
- Dataset:
  - `rosobrnadzor_sample.txt`
  - `rosobrnadzor_evidence_site.txt`
  - `organization_profile.json`
  - `education_metrics.csv`
- Query: `лицензия локальные акты`
- Profile: `3` параллельных пользовательских прогона
- Resource sampler: `docker stats`, шаг `1s`

Полный raw output сохранён в [docs/stress-baseline.json](stress-baseline.json).

## Как запускалось

```bash
./.venv/bin/python backend/scripts/benchmark_live_api.py \
  --runs 3 \
  --concurrency 3 \
  --resource-profile docker \
  --resource-interval 1.0 \
  --output docs/stress-baseline.json
```

## Итог профиля

- `requested_runs`: `3`
- `completed_runs`: `3`
- `failed_runs`: `0`
- `concurrency`: `3`
- `total_wall_time_seconds`: `28.7982`
- `throughput_runs_per_minute`: `6.2504`
- `success_rate`: `1.0`

## Сводка по этапам

| Этап | Mean, s | P95, s |
|---|---:|---:|
| `upload_total` | `0.0673` | `0.0681` |
| `process_total` | `4.1975` | `4.1993` |
| `search` | `0.0579` | `0.0619` |
| `create_report` | `0.0146` | `0.0169` |
| `analyze` | `1.0357` | `1.0392` |
| `fetch_requirements` | `0.0125` | `0.0129` |
| `fetch_matrix` | `0.0175` | `0.0180` |
| `generate` | `20.3659` | `21.2762` |
| `export_docx` | `0.0302` | `0.0335` |
| `export_matrix` | `0.0099` | `0.0115` |
| `export_package` | `0.0293` | `0.0309` |
| `export_explanations` | `0.0053` | `0.0060` |

## Ресурсный профиль контейнеров

### Backend

- `cpu_percent mean`: `4.049`
- `cpu_percent p95`: `8.262`
- `memory_mib mean`: `140.08`
- `memory_mib p95`: `150.25`
- `pids mean`: `21.5`

### Worker

- `cpu_percent mean`: `1.27`
- `cpu_percent p95`: `4.094`
- `memory_mib mean`: `982.48`
- `memory_mib p95`: `982.955`
- `pids mean`: `15.0`

### PostgreSQL

- `cpu_percent mean`: `0.748`
- `cpu_percent p95`: `2.5515`
- `memory_mib mean`: `55.423`
- `memory_mib p95`: `56.592`
- `pids mean`: `14.0`

### Redis

- `cpu_percent mean`: `0.758`
- `cpu_percent p95`: `1.0095`
- `memory_mib mean`: `10.682`
- `memory_mib p95`: `10.7755`
- `pids mean`: `6.0`

## Выводы

- При `3x` concurrency главным bottleneck остаётся `generate`: среднее время выросло до `~20.37s` при сохранении стабильных `process` и `analyze`.
- На стороне контейнеров самым тяжёлым по памяти остаётся `worker`: около `982 MiB`.
- `backend` деградирует умеренно: CPU растёт, но memory footprint остаётся сравнительно компактным.
- `PostgreSQL` и `Redis` под текущим demo-корпусом не являются ограничивающими узлами.

## Ограничения измерения

- Текущий resource sampler фиксирует только Docker-контейнеры.
- В этом профиле `Ollama` не вошёл в контейнерный снимок, потому что runtime был подключён через `host.docker.internal:11434`, то есть фактически работал как внешний host service.
- Следующий инженерный шаг для более полного профиля: host-level sampling для `Ollama`, а также сравнение `fallback` vs `model` под одинаковой нагрузкой.
