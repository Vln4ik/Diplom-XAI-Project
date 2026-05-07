# XAI Report Builder

Monorepo проекта `web-first MVP` платформы для формирования объяснимой отчётности по надзорным и проверочным сценариям.

## Структура

- `backend/` — `FastAPI`, `SQLAlchemy`, `Alembic`, `Celery`, document pipeline, export-сервисы
- `frontend/` — клиент на `React + TypeScript + Vite`
- `infra/` — `Docker Compose` и локальная инфраструктура запуска
- `docs/` — архитектурная и проектная документация
- `samples/` — примеры входных файлов для demo и тестов

## Стратегия веток

- `legacy-prototype` — архивная ветка старого прототипа
- `roadmap` — ветка планирования и архитектурной документации
- `main` — основная ветка реализации
- `feature/*` — короткоживущие рабочие ветки

## Быстрый старт

Основной локальный сценарий запуска построен вокруг `Docker`.

```bash
docker compose -f infra/docker-compose.yml up --build
```

Эта команда запускает стабильный `fallback`-режим: hash embeddings и детерминированную сборку разделов отчёта.

## Локальные AI-режимы

Рекомендуемый локальный AI runtime: `Ollama`.

Запуск стека с локальным AI-профилем:

```bash
COMPOSE_PROFILES=local-ai \
XAI_APP_EMBEDDING_PROVIDER=ollama \
XAI_APP_LLM_PROVIDER=ollama \
docker compose -f infra/docker-compose.yml up --build
```

Рекомендуемый однокомандный bootstrap:

```bash
bash infra/enable-ollama.sh
```

Если хочешь загрузить модели вручную:

```bash
docker compose -f infra/docker-compose.yml exec ollama ollama pull all-minilm
docker compose -f infra/docker-compose.yml exec ollama ollama pull gemma3:270m
```

Экспериментальный in-process режим через `transformers` тоже доступен, но только как `opt-in`:

```bash
INSTALL_LOCAL_AI=1 \
XAI_APP_EMBEDDING_PROVIDER=sentence_transformers \
XAI_APP_LLM_PROVIDER=local_transformers \
docker compose -f infra/docker-compose.yml up --build
```

Доступные сервисы:

- API: `http://localhost:8000`
- API-документация: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

## Текущий scope

Первая реализация ориентирована на:

- `Рособрнадзор`
- образовательные организации
- `web-first MVP`
- локальное файловое хранилище
- локальную интеграцию LLM через provider abstraction
- локальную embedding-модель с fallback на детерминированные hash embeddings

## Актуальные примечания

- проект уже опубликован в GitHub: `Vln4ik/Diplom-XAI-Project`
- старый прототип сохранён в ветке `legacy-prototype`
- локальные bootstrap-учётные данные Docker-стенда: `admin@example.com` / `ChangeMe123!`

## Demo и acceptance

- demo dataset: [samples/documents](/Users/vinchik/Desktop/Diplom/samples/documents)
- системное руководство: [docs/system-handbook.md](/Users/vinchik/Desktop/Diplom/docs/system-handbook.md)
- пользовательский путь: [docs/user-flow.md](/Users/vinchik/Desktop/Diplom/docs/user-flow.md)
- описание LLM и XAI-метода: [docs/llm-xai-method.md](/Users/vinchik/Desktop/Diplom/docs/llm-xai-method.md)
- архитектурные решения: [docs/architecture-decisions.md](/Users/vinchik/Desktop/Diplom/docs/architecture-decisions.md)
- статус роадмапа: [docs/roadmap-status.md](/Users/vinchik/Desktop/Diplom/docs/roadmap-status.md)
- статус GitHub-публикации: [docs/github-publication-status.md](/Users/vinchik/Desktop/Diplom/docs/github-publication-status.md)
- ручной demo-сценарий: [docs/demo-scenario.md](/Users/vinchik/Desktop/Diplom/docs/demo-scenario.md)
- acceptance-checklist: [docs/acceptance-checklist.md](/Users/vinchik/Desktop/Diplom/docs/acceptance-checklist.md)
- метрики качества: [docs/quality-metrics.md](/Users/vinchik/Desktop/Diplom/docs/quality-metrics.md)
- performance baseline: [docs/performance-baseline.md](/Users/vinchik/Desktop/Diplom/docs/performance-baseline.md)
- load baseline: [docs/load-baseline.md](/Users/vinchik/Desktop/Diplom/docs/load-baseline.md)

## Путь пользователя

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

## Оценка эффекта

Что уже измерено на demo dataset:

- `4/4` документа успешно обрабатываются
- `3/3` требования имеют evidence
- `3/3` требования имеют `XAI logic chain`
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
- они не равны формальным `precision/recall/F1`
- для строгой научной валидации нужен отдельный размеченный benchmark

## Команды проверки

```bash
./.venv/bin/pytest -q backend/tests
cd frontend && npm run build
cd frontend && npm run e2e
```

## Performance benchmark

```bash
./.venv/bin/python backend/scripts/benchmark_live_api.py \
  --runs 2 \
  --output docs/performance-baseline.json
```

## Concurrency/load benchmark

```bash
./.venv/bin/python backend/scripts/benchmark_live_api.py \
  --runs 2 \
  --concurrency 2 \
  --output docs/load-baseline.json
```

## Локальный AI runtime

- Embeddings:
  рекомендуемый вариант — `Ollama + all-minilm`; экспериментальный in-process вариант — `sentence-transformers`
- LLM:
  рекомендуемый вариант — `Ollama + gemma3:270m`; экспериментальный in-process вариант — `transformers`
- Runtime status:
  `GET /api/system/ai-status`
- Важно:
  векторы пока сохраняются в настроенной размерности `embedding_size`. Для `Ollama embeddings` приложение запрашивает эту размерность через `/api/embed`; для других провайдеров векторы адаптируются к текущему хранилищу размерности `32`. Отдельный этап расширения и tuning `pgvector` всё ещё остаётся в плане.
