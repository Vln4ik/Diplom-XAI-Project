# XAI Report Builder

Репозиторий выпускной квалификационной работы, посвящённой разработке `web-first MVP` платформы для формирования объяснимой отчётности по надзорным и проверочным сценариям.

Текущий фокус проекта:

- регуляторный сценарий: `Рособрнадзор`
- тип организации: образовательная организация
- целевой результат: проект отчёта о готовности к проверке с доказательной базой, XAI-объяснениями, матрицей требований и реестром рисков

## Актуальность проекта

Подготовка к проверке в образовательной организации обычно строится на ручной работе со множеством разрозненных источников:

- нормативные документы
- локальные акты
- сведения с официального сайта
- таблицы с показателями и метриками
- внутренние подтверждающие материалы

На практике это приводит к ряду типовых проблем:

- требования выделяются вручную и могут быть пропущены
- доказательная база собирается в разных файлах и таблицах
- повторные версии отчёта требуют повторного ручного анализа
- руководитель получает результат без прозрачной трассировки `вывод -> источник -> доказательство`

Проект направлен на снижение трудоёмкости этого процесса и повышение его прозрачности за счёт сочетания document pipeline, retrieval, локальных AI-моделей и XAI-подхода.

## Цель работы

Целью проекта является разработка программной системы, позволяющей автоматизировать первичную подготовку отчёта о готовности организации к проверке, сохранив при этом проверяемость, объяснимость и управляемость результата.

## Задачи работы

В рамках проекта решаются следующие задачи:

1. Централизованный приём документов организации в различных форматах.
2. Извлечение текста, разбиение документов на фрагменты и индексирование данных.
3. Выделение требований из нормативных и локальных документов.
4. Определение применимости требований к конкретной организации.
5. Поиск подтверждающих evidence в загруженных материалах.
6. Формирование confidence, рекомендаций и реестра рисков.
7. Сохранение XAI-цепочки для каждого существенного вывода.
8. Генерация проекта отчёта и экспортных артефактов.
9. Поддержка ручного review, согласования, аудита и версионности.

## Научно-практическая идея проекта

Ключевая идея работы состоит в том, что в задачах регуляторной отчётности ценность создаёт не просто генерация текста через LLM, а связка нескольких уровней:

- обработка документов
- hybrid retrieval
- requirement mining
- evidence grounding
- persisted XAI
- human-in-the-loop review

Таким образом, система формирует не только итоговый текст отчёта, но и объяснимую аналитическую основу, на которой этот отчёт построен.

## Функциональные возможности текущего MVP

На текущем этапе проект поддерживает:

- загрузку документов `PDF`, `DOCX`, `XLSX`, `CSV`, `TXT`, `JSON`
- извлечение текста и разбиение документов на фрагменты
- поиск по фрагментам через hybrid retrieval
- формирование реестра требований
- построение матрицы `требование -> доказательство`
- генерацию XAI-объяснений
- формирование списка рисков и рекомендованных действий
- генерацию проекта отчёта
- экспорт `DOCX`, `XLSX`, `ZIP`, `HTML`
- уведомления, аудит, review-flow и versioning

## Архитектура и технологический стек

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

### Инфраструктура

- `Docker Compose`
- локальное файловое хранилище
- локальный AI runtime через `Ollama`

### Локальные AI-модели

- embeddings: `Ollama + all-minilm`
- LLM: `Ollama + gemma3:270m`

Важно: текущая реализация остаётся text-centric и transformer-based. При этом в MVP уже работает `Tesseract OCR` для image-файлов и image-only PDF, но `CNN` и полноценный document-vision/layout-analysis контур для сложных сканов в проект пока не входят.

## Пользовательский сценарий

Основной пользовательский путь в системе выглядит следующим образом:

1. Пользователь входит в систему.
2. Создаёт организацию или выбирает существующую.
3. Переходит в раздел `Документы`.
4. Загружает нормативные, доказательные и служебные документы.
5. Для каждого документа запускает обработку.
6. Проверяет результаты поиска по фрагментам.
7. Переходит в раздел `Отчёты`.
8. Создаёт новый отчёт и привязывает к нему нужные документы.
9. Нажимает `Анализ`.
10. Проверяет `Требования`, `Объяснения`, `Матрицу` и `Риски`.
11. При необходимости вручную подтверждает, отклоняет или редактирует спорные требования.
12. Нажимает `Генерация`.
13. Проверяет сформированные разделы в `Редакторе отчёта`.
14. Выгружает `DOCX`, `XLSX`, `ZIP`, `XAI HTML`.
15. Отправляет отчёт на согласование.

Развёрнутое описание прикладного сценария приведено в [docs/user-flow.md](docs/user-flow.md).

## Практическая значимость и ожидаемый эффект

### Уже измеренные результаты на demo dataset

- `4/4` документа успешно обрабатываются
- `3/3` требования имеют evidence
- `3/3` требования имеют XAI logic chain
- `4/4` export-артефакта создаются успешно
- полный машинный цикл `process + analyze + generate` составляет около `12.27s`

### Первые формальные quality-метрики

На текущем `gold benchmark` для сценария `Рособрнадзор + образовательная организация` зафиксированы следующие результаты:

- `requirement extraction precision`: `1.0000`
- `requirement extraction recall`: `1.0000`
- `requirement extraction F1`: `1.0000`
- `applicability accuracy`: `1.0000`
- `evidence linking precision`: `0.8571`
- `evidence linking recall`: `1.0000`
- `evidence linking F1`: `0.9231`
- `report sections source coverage`: `1.0000`

Эти значения показывают, что текущий MVP уже устойчиво извлекает сами требования, но слой подбора и ранжирования evidence всё ещё требует дальнейшей калибровки. Детализация вынесена в [docs/quality-benchmark-results.md](docs/quality-benchmark-results.md).

### Расширенный benchmark-suite

Дополнительно в проекте собран `benchmark-suite` из четырёх сценариев:

- полный пакет документов;
- компактный пакет `нормативная база + evidence`;
- mixed-scope сценарий с требованием, требующим ручной проверки применимости;
- gap-сценарий `только нормативная база`.

Агрегированные результаты suite:

- `requirement extraction F1`: `1.0000`
- `status_accuracy_mean`: `0.9167`
- `applicability accuracy mean`: `1.0000`
- `evidence linking precision`: `0.8421`
- `evidence linking recall`: `1.0000`
- `evidence linking F1`: `0.9143`
- `report sections source coverage mean`: `0.9583`

Детализация вынесена в [docs/quality-benchmark-suite-results.md](docs/quality-benchmark-suite-results.md).

### OCR benchmark

Для нового OCR-контура добавлен отдельный benchmark на committed corpus из пяти сценариев:

- clean image
- noisy image
- table-like image
- image-only PDF
- mixed-layout PDF

Агрегированные результаты:

- `char_similarity_mean`: `0.9100`
- `token_precision_mean`: `0.9818`
- `token_recall_mean`: `0.9818`
- `token_f1_mean`: `0.9818`
- `keyword_coverage_mean`: `1.0000`
- `requires_review_rate`: `0.0000`

Практически это означает, что базовый `Tesseract OCR` с multi-pass обработкой уже устойчиво извлекает ключевые признаки во всех пяти OCR-сценариях. Самым слабым сценарием теперь остаётся `mixed-layout PDF`, но уже не по coverage, а по `char similarity`: слова и ключевые сигналы извлекаются, однако порядок и layout fidelity ещё проседают. Следующий шаг в OCR-части связан уже не с общим “усилить OCR”, а с `layout-aware OCR / document structure reconstruction`.

### Stress и ресурсный профиль

Дополнительно для текущего MVP зафиксирован отдельный `3x` stress baseline с container-level profiling:

- `concurrency`: `3`
- `success_rate`: `1.0`
- `throughput_runs_per_minute`: `6.2504`
- `generate mean`: `20.3659s`
- `backend memory mean`: `140.08 MiB`
- `worker memory mean`: `982.48 MiB`

Это позволяет говорить не только о latency, но и о реальном ресурсоёмком узле текущей системы: под параллельной нагрузкой главным bottleneck остаётся генерация разделов отчёта и связанный с ней AI runtime. Детализация вынесена в [docs/stress-baseline.md](docs/stress-baseline.md).

### Оценка выигрыша по времени

Для малого пакета документов ручной сценарий обычно занимает:

- `2.5-6` часов

При использовании текущего инструмента и с учётом ручного review реалистичная инженерная оценка выглядит так:

- `20-45` минут на малый пакет документов
- `45-120` минут на средний пакет

Консервативная оценка эффекта:

- ускорение первичной подготовки отчёта: `40-70%`
- ускорение повторных review-циклов: `25-50%`

### Оценка возможного прироста качества

Предварительно можно предполагать:

- снижение вероятности пропуска требования: `15-30%`
- улучшение полноты evidence-покрытия: `20-40%`
- повышение воспроизводимости и единообразия проверки: `25-50%`

Важно: теперь в проекте уже есть первый формальный benchmark с `precision/recall/F1`, но он пока построен на малом demo corpus. Для строгой научной валидации всё ещё требуется расширенный размеченный benchmark и экспертное сравнение на репрезентативной выборке кейсов.

## Ограничения текущего MVP

В текущую версию сознательно не включены:

- полноценный `iOS`-клиент
- интеграции с внешними государственными системами
- электронная подпись
- multi-regulator production scope
- domain fine-tuning на большом размеченном корпусе

При этом в текущем MVP уже работает базовый `OCR`-контур:

- распознавание `PNG/JPG/TIFF/BMP`;
- OCR-fallback для image-only `PDF`;
- автоматическое включение `Tesseract` в Docker-окружении и launcher-скриптах.
- отдельный OCR benchmark на committed corpus.
- multi-pass OCR с несколькими `PSM` и image-variants.

Следующим этапом остаются более тяжёлые OCR/vision-задачи:

- layout analysis сложных PDF;
- OCR noisy-сканов с низким качеством;
- vision-first обработка таблиц и многостраничных mixed-layout документов;
- улучшение именно mixed-layout OCR и восстановления порядка контента, так как это сейчас самый слабый OCR-сценарий по layout fidelity.

## Структура репозитория

- `backend/` — backend-система, API, workers, бизнес-логика, тесты
- `frontend/` — пользовательский web-интерфейс
- `infra/` — docker-compose и инфраструктурные скрипты
- `docs/` — документация проекта
- `samples/` — sample dataset для demo и acceptance-сценариев

## Запуск проекта

### Базовый локальный запуск

```bash
docker compose -f infra/docker-compose.yml up --build
```

Эта команда запускает стабильный `fallback`-режим.

### Запуск с локальным AI через Ollama

```bash
COMPOSE_PROFILES=local-ai \
XAI_APP_EMBEDDING_PROVIDER=ollama \
XAI_APP_LLM_PROVIDER=ollama \
docker compose -f infra/docker-compose.yml up --build
```

Рекомендуемый bootstrap:

```bash
bash infra/enable-ollama.sh
```

Если модели нужно загрузить вручную:

```bash
docker compose -f infra/docker-compose.yml exec ollama ollama pull all-minilm
docker compose -f infra/docker-compose.yml exec ollama ollama pull gemma3:270m
```

### Экспериментальный режим через transformers

```bash
INSTALL_LOCAL_AI=1 \
XAI_APP_EMBEDDING_PROVIDER=sentence_transformers \
XAI_APP_LLM_PROVIDER=local_transformers \
docker compose -f infra/docker-compose.yml up --build
```

## Доступные сервисы

- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

Локальные bootstrap-учётные данные:

- `admin@example.com`
- `ChangeMe123!`

## Служебные runtime endpoint-ы

- `GET /api/system/ai-status` — активные `AI/OCR` provider-ы
- `GET /api/system/health` — состояние базы, storage и runtime-конфигурации
- `GET /api/system/metrics` — JSON snapshot request-метрик
- `GET /api/system/metrics/prometheus` — Prometheus-compatible exposition

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

## Stress benchmark с resource profiling

```bash
./.venv/bin/python backend/scripts/benchmark_live_api.py \
  --runs 3 \
  --concurrency 3 \
  --resource-profile docker \
  --resource-interval 1.0 \
  --output docs/stress-baseline.json
```

## Formal quality benchmark

```bash
./.venv/bin/python backend/scripts/generate_quality_benchmark_report.py
```

## Quality benchmark suite

```bash
./.venv/bin/python backend/scripts/generate_quality_benchmark_suite_report.py
```

## Документация проекта

- системное руководство: [docs/system-handbook.md](docs/system-handbook.md)
- пользовательский путь: [docs/user-flow.md](docs/user-flow.md)
- описание LLM и XAI-метода: [docs/llm-xai-method.md](docs/llm-xai-method.md)
- подробное объяснение моделей и XAI-блока: [docs/models-and-xai-overview.md](docs/models-and-xai-overview.md)
- архитектурные решения: [docs/architecture-decisions.md](docs/architecture-decisions.md)
- статус роадмапа: [docs/roadmap-status.md](docs/roadmap-status.md)
- методика эксперимента: [docs/experimental-methodology.md](docs/experimental-methodology.md)
- результаты эксперимента: [docs/experimental-results.md](docs/experimental-results.md)
- ручной demo-сценарий: [docs/demo-scenario.md](docs/demo-scenario.md)
- acceptance-checklist: [docs/acceptance-checklist.md](docs/acceptance-checklist.md)
- метрики качества: [docs/quality-metrics.md](docs/quality-metrics.md)
- quality benchmark report: [docs/quality-benchmark-results.md](docs/quality-benchmark-results.md)
- quality benchmark suite: [docs/quality-benchmark-suite-results.md](docs/quality-benchmark-suite-results.md)
- performance baseline: [docs/performance-baseline.md](docs/performance-baseline.md)
- load baseline: [docs/load-baseline.md](docs/load-baseline.md)
- stress baseline: [docs/stress-baseline.md](docs/stress-baseline.md)

## Статус проекта

Проект реализован как рабочий `web-first MVP` с локальным AI-контуром, XAI-слоем, экспортом, acceptance-сценарием, browser e2e, quality benchmark, load baseline и `3x` stress baseline с container-level profiling. Следующий этап развития связан с повышением качества evidence linking, расширением benchmark-контуров и дальнейшей формализацией научных и эксплуатационных метрик качества.
