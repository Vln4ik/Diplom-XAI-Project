# XAI Report Builder

Monorepo for the web-first MVP of a reporting platform for supervisory authorities.

## Structure

- `backend/` — FastAPI, SQLAlchemy, Alembic, Celery, document pipeline, export services
- `frontend/` — React + TypeScript + Vite client
- `infra/` — Docker Compose and local infrastructure bootstrap
- `docs/` — architecture notes and implementation roadmap
- `samples/` — sample files for demo and testing

## Branch Strategy

- `legacy-prototype` — archive pointer to the old FastAPI prototype
- `roadmap` — planning and architecture branch
- `main` — implementation branch
- `feature/*` — short-lived task branches

## Quick Start

The primary local workflow is Docker-based.

```bash
docker compose -f infra/docker-compose.yml up --build
```

This starts the stable fallback mode: hash embeddings plus deterministic section assembly.

## Local AI Modes

Recommended local AI runtime: `Ollama`.

Start the stack with the local AI profile and switch providers:

```bash
COMPOSE_PROFILES=local-ai \
XAI_APP_EMBEDDING_PROVIDER=ollama \
XAI_APP_LLM_PROVIDER=ollama \
docker compose -f infra/docker-compose.yml up --build
```

Recommended one-command bootstrap:

```bash
bash infra/enable-ollama.sh
```

Manual model pull, if you prefer:

```bash
docker compose -f infra/docker-compose.yml exec ollama ollama pull all-minilm
docker compose -f infra/docker-compose.yml exec ollama ollama pull gemma3:270m
```

Experimental in-process `transformers` mode is still available, but only as opt-in:

```bash
INSTALL_LOCAL_AI=1 \
XAI_APP_EMBEDDING_PROVIDER=sentence_transformers \
XAI_APP_LLM_PROVIDER=local_transformers \
docker compose -f infra/docker-compose.yml up --build
```

Services:

- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

## Current Scope

The first implementation targets:

- `Рособрнадзор`
- educational organizations
- web-first MVP
- local file storage
- local LLM integration through a provider abstraction
- local embedding model with fallback to deterministic hash embeddings

## Notes

- GitHub remote is not configured yet.
- `gh` is installed locally, but GitHub authentication is not configured yet.
- The old prototype is preserved through the local `legacy-prototype` branch.
- Docker bootstrap admin credentials: `admin@example.com` / `ChangeMe123!`

## Demo And Acceptance

- Demo dataset: [samples/documents](/Users/vinchik/Desktop/Diplom/samples/documents)
- System handbook: [docs/system-handbook.md](/Users/vinchik/Desktop/Diplom/docs/system-handbook.md)
- User flow: [docs/user-flow.md](/Users/vinchik/Desktop/Diplom/docs/user-flow.md)
- LLM and XAI method: [docs/llm-xai-method.md](/Users/vinchik/Desktop/Diplom/docs/llm-xai-method.md)
- Architecture decisions: [docs/architecture-decisions.md](/Users/vinchik/Desktop/Diplom/docs/architecture-decisions.md)
- Roadmap status: [docs/roadmap-status.md](/Users/vinchik/Desktop/Diplom/docs/roadmap-status.md)
- GitHub publication status: [docs/github-publication-status.md](/Users/vinchik/Desktop/Diplom/docs/github-publication-status.md)
- Manual demo scenario: [docs/demo-scenario.md](/Users/vinchik/Desktop/Diplom/docs/demo-scenario.md)
- Acceptance checklist: [docs/acceptance-checklist.md](/Users/vinchik/Desktop/Diplom/docs/acceptance-checklist.md)
- Quality metrics note: [docs/quality-metrics.md](/Users/vinchik/Desktop/Diplom/docs/quality-metrics.md)
- Performance baseline: [docs/performance-baseline.md](/Users/vinchik/Desktop/Diplom/docs/performance-baseline.md)
- Load baseline: [docs/load-baseline.md](/Users/vinchik/Desktop/Diplom/docs/load-baseline.md)

## User Journey

Коротко путь пользователя на сайте выглядит так:

1. Залогиниться.
2. Создать организацию.
3. Перейти в `Документы`.
4. Загрузить нормативные, доказательные и служебные документы.
5. Нажать `Обработать` для каждого документа.
6. Проверить поиск по фрагментам.
7. Перейти в `Отчёты`.
8. Создать новый отчёт и привязать к нему загруженные документы.
9. Нажать `Анализ`.
10. Проверить `Требования`, `Объяснения`, `Матрицу`, `Риски`.
11. При необходимости вручную скорректировать спорные требования и риски.
12. Нажать `Генерация`.
13. Проверить итоговые разделы в `Редакторе отчёта`.
14. Выгрузить `DOCX`, `XLSX`, `ZIP`, `XAI HTML`.
15. Отправить отчёт на согласование.

Развёрнутая версия этого сценария описана в [docs/user-flow.md](/Users/vinchik/Desktop/Diplom/docs/user-flow.md).

## Estimated Impact

Что уже измерено на demo dataset:

- `4/4` документа успешно обрабатываются
- `3/3` требования имеют evidence
- `3/3` требования имеют XAI logic chain
- `4/4` export-артефакта формируются успешно
- машинный цикл `process + analyze + generate` занимает около `12.27s`

Практическая инженерная оценка эффекта:

- ручной сценарий для малого пакета документов: `2.5-6` часов
- автоматизированный сценарий с review: примерно `20-45` минут
- ускорение первичной подготовки: `40-70%`
- ускорение повторных review-циклов: `25-50%`

Предварительная оценка прироста качества проверки:

- снижение вероятности пропуска требования: `15-30%`
- улучшение полноты evidence-покрытия: `20-40%`
- повышение воспроизводимости и единообразия проверки: `25-50%`

Важно:

- это предварительные инженерные оценки
- они не равны formal `precision/recall/F1`
- для строгой scientific-валидации нужен отдельный размеченный benchmark

Verification commands:

```bash
./.venv/bin/pytest -q backend/tests
cd frontend && npm run build
cd frontend && npm run e2e
```

Performance benchmark:

```bash
./.venv/bin/python backend/scripts/benchmark_live_api.py \
  --runs 2 \
  --output docs/performance-baseline.json
```

Concurrency/load benchmark:

```bash
./.venv/bin/python backend/scripts/benchmark_live_api.py \
  --runs 2 \
  --concurrency 2 \
  --output docs/load-baseline.json
```

## Local AI Runtime

- Embeddings:
  recommended: `Ollama + all-minilm`; experimental in-process option: `sentence-transformers`.
- LLM:
  recommended: `Ollama + gemma3:270m`; experimental in-process option: `transformers`.
- Runtime status:
  `GET /api/system/ai-status`
- Important:
  vectors are still stored in the configured `embedding_size` dimension. For Ollama embeddings the app requests this dimension from `/api/embed`; for other providers it adapts vectors to the current `32`-dimensional storage. A dedicated `pgvector` dimension expansion/tuning step is still pending.
