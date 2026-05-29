# Системный обзор

Дата актуализации: `2026-05-29`

## 1. Назначение системы

`EvidenceXAI` — это web-first платформа для подготовки объяснимой отчётности по проверочным и надзорным сценариям.

В интерфейсе продукт использует компактную метку `EX.AI`, а термин `XAI` сохраняется как название XAI-контура и объяснений.

Текущая завершённая версия `MVP 1` ориентирована на сценарий:

- регулятор: `Рособрнадзор`
- тип организации: образовательная организация
- результат: проект отчёта о готовности к проверке с доказательствами, рисками и XAI-объяснениями

Текущий код также содержит расширенный прикладной трек:

- государственная экспертиза проектной документации;
- спецотчёт проверки достоверности сметной стоимости по `ПП 145`;
- спецотчёт проверки разделов проектной документации по `ПП 87`;
- workflow findings, user decisions, XAI и export по каждому спецотчёту.

## 2. Что система решает

Система убирает основную боль ручной подготовки отчётности:

- требования находятся в разрозненных источниках
- доказательства ищутся вручную
- разные версии отчёта требуют повторной ручной сверки
- руководитель не видит прозрачную логику вывода

Практический результат системы:

- требования собраны в единый реестр
- доказательства связаны с требованиями
- риски и пробелы вынесены явно
- проект отчёта формируется быстрее
- пользователь видит, почему система приняла каждое важное решение

## 3. Статус продукта

Текущий статус:

- `MVP 1` завершён
- активный следующий этап: `MVP 2`

Это означает:

- основной сквозной контур уже работает
- проект не находится в стадии “первой сборки”
- новые крупные усиления идут как отдельные версии, а не как бесконечное расширение `MVP 1`

## 4. Что уже умеет `MVP 1`

### 4.1. Документы

- upload документов
- обработка `PDF`, `DOCX`, `DOC`, `XLSX`, `CSV`, `TXT`, `JSON`, `XML`, `ZIP`, `SIG`, `P7S`, `GGE`, `JPG/PNG/TIFF/BMP`
- базовый OCR-контур для image-файлов и image-only `PDF`
- chunking и индексирование фрагментов
- поиск по фрагментам
- progress-индикаторы обработки в web UI

### 4.1.a. Организации

- создание и редактирование организаций через modal-форму
- удаление организации
- попытка автозаполнения реквизитов из уже обработанных вложений
- demo-pack из `10` тестовых организаций для локального smoke/demo-сценария

### 4.2. Аналитика

- извлечение требований
- applicability
- evidence linking
- confidence
- risk generation
- сохранённые XAI-объяснения
- специализированные findings для государственной экспертизы:
  - соответствие названия файла содержанию;
  - комплектность по `ПП РФ N 145`;
  - содержание разделов по `ПП РФ N 87`;
  - качество документа, OCR/text-layer, подписи/печати, терминология.

### 4.3. Отчётный результат

- жизненный цикл отчёта
- section generation
- versioning
- export `DOCX`, `XLSX`, `ZIP`, `HTML`
- базовый контур review / submit / approve
- export спецworkflow `DOCX/XLSX/XAI HTML/ZIP`

### 4.4. Инженерная зрелость `MVP 1`

- tests
- benchmark artifacts
- pilot `real_corpus`
- calibration sweep
- базовый observability-контур
- synthetic benchmark проектно-сметного спецworkflow

## 5. Пользователи и роли

В текущем `MVP 1` предусмотрены роли:

- `system_admin`
- `org_admin`
- `specialist`
- `approver`
- `viewer`
- `external_expert`

Главный пользовательский контур строится вокруг:

- `specialist`
- `approver`

## 6. Какие данные использует система

Основные типы входных данных:

- нормативные документы
- локальные акты
- доказательные документы
- профиль организации
- табличные метрики

Поддерживаемые форматы:

- `PDF`
- `DOCX`
- `DOC`
- `XLSX`
- `CSV`
- `TXT`
- `JSON`
- `XML`
- `ZIP`
- `SIG/P7S`
- `GGE`
- `JPG/PNG/TIFF/BMP`

## 7. Текущий пользовательский путь `MVP 1`

1. Пользователь входит в систему и выбирает организацию.
2. При необходимости редактирует профиль организации или пробует подтянуть поля из вложений.
3. Загружает документы и назначает категории.
4. Запускает обработку документов.
5. Проверяет поиск по фрагментам.
6. Создаёт отчёт и выбирает документы.
7. Запускает анализ.
8. Проверяет требования, XAI, матрицу и риски.
9. Выполняет ручной review спорных мест.
10. Запускает генерацию разделов отчёта.
11. Выгружает итоговый пакет и отправляет его на согласование.

Подробно это вынесено в [user-flow.md](user-flow.md) и [demo-scenario.md](demo-scenario.md).

## 8. Архитектурная схема `MVP 1`

Система состоит из следующих основных узлов:

- web frontend
- REST API
- background worker
- `PostgreSQL + pgvector`
- `Redis`
- filesystem storage
- local AI runtime
- optional observability-контур

Подробная техническая схема: [architecture.md](architecture.md)

## 9. AI / XAI в текущей версии

Текущий штатный demo-runtime использует:

- `Ollama + all-minilm` для neural embeddings
- `Ollama + gemma3:270m` для локальной generative LLM
- локальный `Tesseract` OCR
- локальные baseline-эвристики visual quality и signature/seal
- rule-based business logic
- сохранённые XAI-объяснения

На текущем активном этапе `MVP 2` код уже расширен до profile-aware локального runtime:

- `baseline`
- `quality`
- `quality_plus`

Профиль задаётся через `XAI_APP_AI_RUNTIME_PROFILE`, а system API показывает не только provider, но и фактически разрешённую модель для embeddings и LLM.

Важно: `Ollama` является целевым режимом проекта. Launcher `infra/start_full_stack.sh` проверяет host Ollama, модели и запускает backend/worker с `XAI_APP_EMBEDDING_PROVIDER=ollama`, `XAI_APP_LLM_PROVIDER=ollama`. Fallback providers нужны только для аварийной деградации и не считаются полноценным режимом демонстрации.

Важно:

- это не чистый “one-shot LLM product”
- это не multimodal system
- это не final vision stack

Подробно: [llm-xai-method.md](llm-xai-method.md) и [models-and-xai-overview.md](models-and-xai-overview.md)

## 10. Что подтверждает качество `MVP 1`

У проекта уже есть:

- gold benchmark
- committed benchmark-suite
- pilot `real_corpus`
- OCR benchmark
- performance / load / stress artifacts
- state expertise corpus validation
- estimate expertise synthetic benchmark: `4/4` cases, `10/10` targets
- реальный локальный прогон `Водоканалпроект / 1. ИРД / ПП 145`: `180` документов, `48` findings, `35` unresolved, корректный статус `blocked`

Это даёт не только demo, но и формальный validation contour.

## 11. Ограничения `MVP 1`

В текущую версию не входят как завершённые контуры:

- полноценный layout-aware vision-контур
- large real-world benchmark corpus
- продвинутый процессный контур с ЭП
- external integrations
- production-grade platform maturity
- iOS client

## 12. Что будет усиливаться дальше

### `MVP 2`

- AI quality
- расширенный `real_corpus`
- более сильный OCR / vision-контур
- более сильные модели
- более зрелая calibration-стратегия
- real corpus проектно-сметной документации
- снижение false-positive в `filename -> content`
- comparative benchmark `baseline / quality / quality_plus`

Инфраструктурная часть этого шага уже начата: локальные модели переключаются через runtime profiles, спецworkflow государственной экспертизы перенесён в backend/Celery, synthetic benchmark проходит целевые проверки. Следующий подэтап — расширить real corpus и сравнить профили на одном benchmark-протоколе.

### `MVP 3`

- развитие процессного контура
- approvals / governance
- integrations
- электронная подпись
- multi-regulator templates

### `MVP 4`

- platform maturity
- security
- deployment
- high-load and operations contour

## 13. Как правильно описывать проект сейчас

Корректная формулировка текущего состояния:

> `EvidenceXAI` — это завершённый `MVP 1` web-first платформы для объяснимой подготовки отчётности, уже включающий документный pipeline, контур требований/доказательств/XAI, генерацию отчёта, экспортные артефакты и контур валидации, с активным следующим этапом развития в сторону `MVP 2` и усиления AI quality.

Актуальная фактическая сводка по runtime и последнему реальному тесту находится в [current-project-status.md](current-project-status.md).
