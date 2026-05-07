# Performance Baseline

Дата фиксации: `2026-05-07` (`Europe/Moscow`)

## Контур измерения

- Backend: `FastAPI + PostgreSQL + pgvector + Celery`
- Retrieval: `PostgreSQL full-text + pgvector candidate selection`
- Embeddings: `Ollama + all-minilm`
- LLM: `Ollama + gemma3:270m`
- Dataset:
  - `rosobrnadzor_sample.txt`
  - `rosobrnadzor_evidence_site.txt`
  - `organization_profile.json`
  - `education_metrics.csv`
- Query: `лицензия локальные акты`

Полный raw output сохранён в [docs/performance-baseline.json](/Users/vinchik/Desktop/Diplom/docs/performance-baseline.json).

## Как запускалось

```bash
./.venv/bin/python backend/scripts/benchmark_live_api.py \
  --runs 2 \
  --output docs/performance-baseline.json
```

Benchmark проходит живой пользовательский контур:

1. `login`
2. `create organization`
3. `upload 4 documents`
4. `process documents`
5. `search`
6. `create report`
7. `analyze`
8. `fetch requirements/matrix`
9. `generate`
10. `export DOCX/XLSX/ZIP/HTML`

## Сводка по 2 итерациям

| Этап | Mean, s | P95, s |
|---|---:|---:|
| `upload_total` | `0.0178` | `0.0192` |
| `process_total` | `4.1443` | `4.1634` |
| `search` | `0.0532` | `0.0543` |
| `create_report` | `0.0093` | `0.0093` |
| `analyze` | `1.0202` | `1.0219` |
| `fetch_requirements` | `0.0083` | `0.0093` |
| `fetch_matrix` | `0.0114` | `0.0127` |
| `generate` | `7.1013` | `8.0184` |
| `export_docx` | `0.0363` | `0.0402` |
| `export_matrix` | `0.0088` | `0.0089` |
| `export_package` | `0.0282` | `0.0294` |
| `export_explanations` | `0.0046` | `0.0048` |

## Наблюдения

- Главный узкий участок текущего MVP: `generate`, в среднем `~7.1s` на 9 разделов, с заметной вариативностью между прогонами.
- `analyze` стабилен около `1.02s` на demo-наборе.
- Обработка 4 документов держится около `4.14s`, то есть примерно `~1.02-1.03s` на документ в текущем pipeline.
- Экспортный контур остаётся быстрым: все типы экспорта укладываются менее чем в `0.05s`.
- На момент фиксации и `embeddings`, и `llm` были в режиме `model`, а не `fallback`.
- Отдельный параллельный профиль вынесен в [docs/load-baseline.md](/Users/vinchik/Desktop/Diplom/docs/load-baseline.md).

## Что baseline пока не покрывает

- Нет отдельной фиксации CPU/RAM по контейнерам.
- Нет benchmark-набора на больших документах и длинных разделах отчёта.
- Нет отдельного профиля для сравнения `fallback` vs `Ollama model`.
