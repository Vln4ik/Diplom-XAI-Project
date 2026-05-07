# Load Baseline

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
- Profile: `2` параллельных пользовательских прогона

Полный raw output сохранён в [docs/load-baseline.json](/Users/vinchik/Desktop/Diplom/docs/load-baseline.json).

## Как запускалось

```bash
./.venv/bin/python backend/scripts/benchmark_live_api.py \
  --runs 2 \
  --concurrency 2 \
  --output docs/load-baseline.json
```

## Итог профиля

- `requested_runs`: `2`
- `completed_runs`: `2`
- `failed_runs`: `0`
- `concurrency`: `2`
- `total_wall_time_seconds`: `18.6948`
- `throughput_runs_per_minute`: `6.4189`
- `success_rate`: `1.0`

## Сводка по этапам

| Этап | Mean, s | P95, s |
|---|---:|---:|
| `upload_total` | `0.0268` | `0.0275` |
| `process_total` | `4.1509` | `4.1519` |
| `search` | `0.0557` | `0.0573` |
| `create_report` | `0.0095` | `0.0108` |
| `analyze` | `1.0166` | `1.0167` |
| `fetch_requirements` | `0.0050` | `0.0050` |
| `fetch_matrix` | `0.0078` | `0.0079` |
| `generate` | `13.2132` | `13.2153` |
| `export_docx` | `0.0401` | `0.0404` |
| `export_matrix` | `0.0109` | `0.0110` |
| `export_package` | `0.0367` | `0.0367` |
| `export_explanations` | `0.0056` | `0.0060` |

## Выводы

- Под параллельной нагрузкой самым чувствительным этапом остаётся `generate`.
- По сравнению с последовательным baseline генерация выросла примерно с `~7.1s` до `~13.2s`.
- `process` и `analyze` деградируют слабо: их профиль остаётся почти стабильным.
- На текущем local MVP параллельная конкуренция в основном упирается в генерацию разделов отчёта и shared local LLM runtime.

## Что ещё не покрыто

- Нет профиля выше `2x` concurrency.
- Нет отдельного стресс-теста на длинные документы и большие наборы evidence.
- Нет корреляции с `CPU/RAM` контейнеров и host runtime.
- Нет сравнительного профиля `fallback` vs `Ollama model` под одной и той же нагрузкой.
