# XAI Report Builder

Репозиторий выпускной квалификационной работы и инженерного MVP платформы для подготовки объяснимой отчётности по проверочным и надзорным сценариям.

Текущий статус проекта:

- `MVP 1` завершён
- активный следующий горизонт: `MVP 2`
- основной сценарий текущей версии: `Рособрнадзор + образовательная организация`

## Что это за система

`XAI Report Builder` превращает набор разрозненных документов организации в управляемый контур подготовки отчёта:

- загружает и обрабатывает документы
- выделяет требования
- подбирает доказательства
- рассчитывает статус, confidence и риски
- сохраняет XAI-цепочку по каждому выводу
- генерирует проект отчёта и экспортные артефакты

Система не сводится к генерации текста через LLM. Её ценность строится на связке:

- обработка документов
- гибридный поиск
- извлечение требований
- привязка доказательств
- `XAI`
- проверка человеком

## Что уже входит в `MVP 1`

Текущий завершённый функциональный контур включает:

- backend на `FastAPI + SQLAlchemy + Alembic`
- web-клиент на `React + TypeScript + Vite`
- хранение данных в `PostgreSQL`, брокер задач `Redis`, background jobs через `Celery`
- загрузку документов `PDF`, `DOCX`, `XLSX`, `CSV`, `TXT`, `JSON`
- извлечение текста, chunking, embeddings, поиск по фрагментам
- реестр требований, матрицу доказательств, реестр рисков
- сохранённые XAI-объяснения
- генерацию отчёта, версионность и экспорт `DOCX`, `XLSX`, `ZIP`, `HTML`
- базовый OCR-контур на `Tesseract` для image-файлов и image-only `PDF`
- базовый observability-контур на `Prometheus + Grafana + Alertmanager`
- контур тестирования, benchmark-оценки и acceptance-проверки

Подробный статус вынесен в [docs/roadmap-status.md](docs/roadmap-status.md).

## Что уже подтверждено артефактами

### Базовый gold benchmark

Для основного benchmark-сценария `Рособрнадзор + образовательная организация` зафиксировано:

- `requirement extraction F1`: `1.0000`
- `applicability accuracy`: `1.0000`
- `evidence linking F1`: `0.9231`
- `report sections source coverage`: `1.0000`

Источник: [docs/quality-benchmark-results.md](docs/quality-benchmark-results.md)

### Расширенный committed benchmark-suite

Для `7` committed сценариев, включая OCR-augmented cases:

- `requirement extraction F1`: `1.0000`
- `status_accuracy_mean`: `100.00%`
- `applicability accuracy mean`: `100.00%`
- `evidence linking precision`: `0.8293`
- `evidence linking recall`: `1.0000`
- `evidence linking F1`: `0.9067`
- `source requirement coverage mean`: `100.00%`
- `section quality pass share mean`: `100.00%`

Источник: [docs/quality-benchmark-suite-results.md](docs/quality-benchmark-suite-results.md)

### Пилотный `real_corpus`

В репозитории уже есть пилотный слой `real_corpus`:

- `5` кейсов, готовых к benchmark-проверке
- `5 из 5` кейсов прошли проверку
- `20 из 20` целевых критериев качества выполнены
- `requirement extraction F1`: `1.0000`
- `status_accuracy_mean`: `100.00%`
- `applicability accuracy mean`: `100.00%`
- `evidence linking precision`: `0.7500`
- `evidence linking recall`: `0.9565`
- `evidence linking F1`: `0.8408`
- `source requirement coverage mean`: `100.00%`
- `section quality pass share mean`: `100.00%`

Источники:

- [docs/real-corpus-status.md](docs/real-corpus-status.md)
- [docs/real-corpus-quality-suite-results.md](docs/real-corpus-quality-suite-results.md)
- [docs/real-corpus-target-evaluation.md](docs/real-corpus-target-evaluation.md)

### Calibration

Сейчас есть два разных calibration-среза:

- на committed `7`-сценарном suite лучшим профилем остался `baseline_current`
- на pilot `real_corpus` устойчивым базовым профилем остался `baseline_current`

Это важный вывод для roadmap: в `MVP 2` нужно не только калибровать пороги, но и улучшать сам evidence linking на большем real-world корпусе.

Источники:

- [docs/calibration-sweep-results.md](docs/calibration-sweep-results.md)
- [docs/real-corpus-calibration-sweep.md](docs/real-corpus-calibration-sweep.md)

### Базовый OCR-контур

Для OCR benchmark зафиксировано:

- `char_similarity_mean`: `0.9100`
- `token_f1_mean`: `0.9818`
- `keyword_coverage_mean`: `1.0000`

Это подтверждает, что базовый OCR-контур уже рабочий, но layout-aware vision-контур остаётся задачей `MVP 2+`.

Источник: [docs/ocr-benchmark-results.md](docs/ocr-benchmark-results.md)

## Текущий стек

### Backend

- `FastAPI`
- `SQLAlchemy 2`
- `Alembic`
- `Celery`
- `Redis`
- `PostgreSQL`
- `pgvector`

### Frontend

- `React`
- `TypeScript`
- `Vite`

### AI / XAI

- embeddings: `Ollama + all-minilm`
- local LLM: `Ollama + gemma3:270m`
- rule-based applicability / confidence / risk logic
- сохранённые XAI-объяснения

### Infra

- `Docker Compose`
- локальное файловое хранилище
- optional-контур наблюдаемости: `Prometheus`, `Grafana`, `Alertmanager`

## Новый roadmap проекта

Каноническая модель развития теперь выглядит так:

- `MVP 1` — функциональное ядро, завершён
- `MVP 2` — `AI quality first`
- `MVP 3` — процессный контур, согласование, интеграции, ЭП
- `MVP 4` — production/platform maturity
- `Post-MVP` — исследовательский горизонт: multimodal, fine-tuning, mobile branch

Канонический roadmap: [docs/product-roadmap.md](docs/product-roadmap.md)

### Что входит в `MVP 2`

- расширенный `real_corpus`
- усиленный OCR / vision-контур
- улучшение reranker и evidence linking
- benchmark качества разделов
- более сильные локальные embeddings / LLM
- воспроизводимая calibration-стратегия на большем корпусе

### Что входит в `MVP 3`

- развитие процессного контура и согласования
- enterprise process governance
- электронная подпись
- внешние интеграции
- multi-regulator templates

### Что входит в `MVP 4`

- security hardening
- CI/CD и deployment profiles
- stress `10x+`
- retention / backup
- production-grade observability и эксплуатация

## Пользовательский результат в `MVP 1`

Специалист организации уже может:

1. войти в систему и выбрать организацию
2. загрузить и обработать документы
3. создать отчёт и запустить анализ
4. проверить требования, XAI, матрицу и риски
5. вручную откорректировать спорные места
6. сгенерировать проект отчёта
7. выгрузить итоговый пакет
8. отправить отчёт на согласование

Подробные пользовательские документы:

- [docs/user-flow.md](docs/user-flow.md)
- [docs/demo-scenario.md](docs/demo-scenario.md)
- [docs/acceptance-checklist.md](docs/acceptance-checklist.md)

## Документация проекта

### Product / roadmap

- [docs/product-roadmap.md](docs/product-roadmap.md)
- [docs/roadmap-status.md](docs/roadmap-status.md)
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

### Architecture / engineering

- [docs/architecture.md](docs/architecture.md)
- [docs/architecture-decisions.md](docs/architecture-decisions.md)
- [docs/system-handbook.md](docs/system-handbook.md)

### AI / XAI / эксперименты

- [docs/llm-xai-method.md](docs/llm-xai-method.md)
- [docs/models-and-xai-overview.md](docs/models-and-xai-overview.md)
- [docs/quality-metrics.md](docs/quality-metrics.md)
- [docs/experimental-methodology.md](docs/experimental-methodology.md)
- [docs/experimental-results.md](docs/experimental-results.md)

### Usage / demo / acceptance

- [docs/user-flow.md](docs/user-flow.md)
- [docs/demo-scenario.md](docs/demo-scenario.md)
- [docs/acceptance-checklist.md](docs/acceptance-checklist.md)

## Структура репозитория

```text
backend/   API, доменная логика, workers, тесты
frontend/  web-клиент
infra/     docker-compose, скрипты, observability
docs/      narrative-документация и generated benchmark-артефакты
samples/   demo-корпус, benchmarks, real corpus, calibration-профили
```

## Запуск проекта

### Базовый локальный запуск через Docker

```bash
docker compose -f infra/docker-compose.yml up --build
```

### Запуск с локальным AI через Ollama

```bash
COMPOSE_PROFILES=local-ai docker compose -f infra/docker-compose.yml up --build
bash infra/enable-ollama.sh
```

### Запуск с контуром наблюдаемости

```bash
COMPOSE_PROFILES=observability,local-ai docker compose -f infra/docker-compose.yml up --build
```

## Команды проверки

```bash
./.venv/bin/pytest -q backend/tests
cd frontend && npm run build
```

Отдельные репортинг-команды:

```bash
./.venv/bin/python backend/scripts/generate_quality_benchmark_report.py
./.venv/bin/python backend/scripts/generate_quality_benchmark_suite_report.py --suite-manifest samples/benchmark_suites/extended.json
./.venv/bin/python backend/scripts/validate_real_corpus.py
./.venv/bin/python backend/scripts/evaluate_real_corpus_targets.py
```

## Статус проекта

На текущем этапе проект уже можно честно описывать как:

- завершённый `MVP 1`
- с рабочим сквозным web-сценарием
- с локальным AI/XAI-контуром
- с формальным контуром валидации
- с понятным roadmap на `MVP 2`, `MVP 3` и `MVP 4+`
