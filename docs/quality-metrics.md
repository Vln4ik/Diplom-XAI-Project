# Quality Metrics

Дата фиксации: `2026-05-07`

## Метрики для demo/MVP

- `requirements_created`: число требований после анализа.
- `deduplicated_requirements`: отсутствие дублей по заголовкам в acceptance flow.
- `evidence_coverage`: доля требований с хотя бы одним evidence.
- `xai_coverage`: доля требований с explanation и заполненным `logic_json`.
- `export_success`: успешность генерации `DOCX/XLSX/ZIP/HTML`.
- `review_flow_success`: успешность переходов `submit -> approve/return-to-revision`.

## Как измеряется сейчас

- Автоматически через `backend/tests/test_pipeline.py`.
- Автоматически через `backend/tests/test_acceptance_demo_flow.py`.
- Косвенно через `dashboard`, `notifications` и `audit log`.
- Отдельно через live benchmark: [docs/performance-baseline.md](/Users/vinchik/Desktop/Diplom/docs/performance-baseline.md).
- Отдельно через concurrency/load profile: [docs/load-baseline.md](/Users/vinchik/Desktop/Diplom/docs/load-baseline.md).

## Ограничения текущей фиксации

- Нет отдельного benchmark-набора с эталонной разметкой.
- Нет формальной метрики precision/recall для requirement extraction.
- Есть начальный local baseline для `PostgreSQL + Ollama`, включая `2x` concurrency, но нет профиля на больших данных и нет системных `CPU/RAM` замеров.
