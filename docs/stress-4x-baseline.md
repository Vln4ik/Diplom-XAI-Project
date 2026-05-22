# Stress 4x Baseline

Дата фиксации: `2026-05-22 (Europe/Moscow)`

## Контур измерения

- Backend: `FastAPI + PostgreSQL + pgvector + Celery`
- Embeddings: `ollama + all-minilm`
- LLM: `ollama + gemma3:270m`
- Dataset:
  - `rosobrnadzor_sample.txt`
  - `rosobrnadzor_evidence_site.txt`
  - `organization_profile.json`
  - `education_metrics.csv`
- Query: `лицензия локальные акты`
- Profile: `4` параллельных пользовательских прогона
- Resource sampler: `hybrid`

Полный raw output сохранён в [stress-4x-baseline.json](stress-4x-baseline.json).

## Итог профиля

- `requested_runs`: `4`
- `completed_runs`: `4`
- `failed_runs`: `0`
- `concurrency`: `4`
- `total_wall_time_seconds`: `25.9529`
- `throughput_runs_per_minute`: `9.2475`
- `success_rate`: `1.0000`

## Сводка по этапам

| Этап | Mean, s | P95, s |
|---|---:|---:|
| `analyze` | `1.0325` | `1.0355` |
| `create_organization` | `0.0167` | `0.0203` |
| `create_report` | `0.0177` | `0.0206` |
| `export_docx` | `0.0542` | `0.0626` |
| `export_explanations` | `0.0068` | `0.0079` |
| `export_matrix` | `0.0171` | `0.0201` |
| `export_package` | `0.0445` | `0.0509` |
| `fetch_matrix` | `0.0201` | `0.0226` |
| `fetch_requirements` | `0.0136` | `0.0144` |
| `generate` | `17.5828` | `18.1913` |
| `login` | `0.0702` | `0.0725` |
| `process_education_metrics.csv` | `1.0193` | `1.0261` |
| `process_organization_profile.json` | `1.0226` | `1.0292` |
| `process_rosobrnadzor_evidence_site.txt` | `1.0346` | `1.0383` |
| `process_rosobrnadzor_sample.txt` | `1.0377` | `1.0415` |
| `process_total` | `4.2266` | `4.2324` |
| `search` | `0.0595` | `0.0655` |
| `upload_education_metrics.csv` | `0.0107` | `0.0111` |
| `upload_organization_profile.json` | `0.0111` | `0.0112` |
| `upload_rosobrnadzor_evidence_site.txt` | `0.0109` | `0.0112` |
| `upload_rosobrnadzor_sample.txt` | `0.0203` | `0.0209` |
| `upload_total` | `0.0543` | `0.0552` |

## Ресурсный профиль

- mode: `hybrid`
- host alias: `host_ollama`
- host process match: `ollama`
- sample interval: `1.0s`
- sample count: `10`

### backend

- `cpu_percent mean`: `3.3260`
- `cpu_percent p95`: `9.1620`
- `memory_mib mean`: `185.8600`
- `memory_mib p95`: `197.0650`
- `memory_percent mean`: `2.3680`
- `memory_percent p95`: `2.5105`
- `pids mean`: `23.1000`
- `pids p95`: `24.0000`

### host_ollama

- `cpu_percent mean`: `52.0900`
- `cpu_percent p95`: `177.0800`
- `memory_mib mean`: `581.0406`
- `memory_mib p95`: `889.6148`
- `process_count mean`: `2.8000`
- `process_count p95`: `3.0000`

### postgres

- `cpu_percent mean`: `0.9800`
- `cpu_percent p95`: `3.2020`
- `memory_mib mean`: `82.1830`
- `memory_mib p95`: `84.8575`
- `memory_percent mean`: `1.0490`
- `memory_percent p95`: `1.0855`
- `pids mean`: `14.9000`
- `pids p95`: `15.0000`

### redis

- `cpu_percent mean`: `0.7620`
- `cpu_percent p95`: `1.0150`
- `memory_mib mean`: `18.9040`
- `memory_mib p95`: `19.0800`
- `memory_percent mean`: `0.2400`
- `memory_percent p95`: `0.2400`
- `pids mean`: `6.0000`
- `pids p95`: `6.0000`

### worker

- `cpu_percent mean`: `4.8960`
- `cpu_percent p95`: `21.6165`
- `memory_mib mean`: `830.8300`
- `memory_mib p95`: `833.6650`
- `memory_percent mean`: `10.6030`
- `memory_percent p95`: `10.6400`
- `pids mean`: `15.0000`
- `pids p95`: `15.0000`

## Выводы

- Главным bottleneck остаётся `generate`: mean `17.5828s`, p95 `18.1913s`.
- `process_total` (`4.2266s`) и `analyze` (`1.0325s`) остаются стабильными относительно генерации.
- Профиль впервые включает одновременно Docker-контейнеры и host-level `Ollama`, поэтому виден реальный вклад локального AI runtime.
- `host_ollama` под `4x` нагрузкой доходит до p95 CPU `177.0800` и p95 memory `889.6148 MiB`.

## Дополнительные замечания

Профиль снят на локальном AI runtime через host Ollama. В этом прогоне backend и worker работали в Docker, а embeddings/LLM обслуживались внешним host service по адресу host.docker.internal:11434.
