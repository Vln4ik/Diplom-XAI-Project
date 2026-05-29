# Продуктовый roadmap

Дата актуализации: `2026-05-29`

## 1. Назначение документа

Этот документ является каноническим продуктовым roadmap проекта `EvidenceXAI`.

Обозначения:

- `EvidenceXAI` — имя продукта;
- `EX.AI` — компактная UI-метка;
- `XAI` — explainability-функция внутри продукта.

Фактический статус реализации ведётся отдельно в [roadmap-status.md](roadmap-status.md). Если нужен ответ "что уже сделано прямо сейчас", начинать нужно с него.

## 2. Текущее состояние

Проект находится в состоянии:

- `MVP 1` завершён;
- активный этап: `MVP 2`;
- основной завершённый сценарий: `Рособрнадзор + образовательная организация`;
- расширенный прикладной трек текущего кода: государственная экспертиза проектной документации, включая `ПП 145` и `ПП 87`.

Текущий продукт уже закрывает базовый сценарий подготовки объяснимого проекта отчёта с требованиями, evidence, рисками, XAI и export.

## 3. `MVP 1` — функциональное ядро

### Цель

Собрать работоспособный web-first MVP для сквозного сценария подготовки отчётности.

### Состав

- backend, frontend и infra-контур;
- document pipeline;
- реестр требований;
- матрица доказательств;
- XAI-объяснения;
- risks;
- generation sections;
- export;
- базовый review / submit / approve;
- OCR baseline;
- benchmark / acceptance / observability baseline.

### Статус

`MVP 1` завершён.

Завершение подтверждают:

- основной web-сценарий без Swagger;
- экспорт и versioning;
- XAI и evidence в UI;
- backend tests и acceptance flow;
- committed benchmark-suite;
- pilot `real_corpus`;
- OCR benchmark;
- runtime/load/stress artifacts.

## 4. `MVP 2` — AI quality first

### Цель

Повысить качество аналитического контура на более реалистичных данных и усилить document understanding без отказа от локального runtime и auditable XAI.

### Уже реализовано в рамках `MVP 2`

- profile-aware локальный AI runtime: `baseline`, `quality`, `quality_plus`;
- выбор resolved model через `Ollama` candidate list;
- `/api/system/ai-status` для проверки profile/provider/model/fallback state;
- Docker/launcher default на `ollama` providers;
- configurable runtime ports для backend/frontend/postgres/redis;
- online installer для Apple Silicon Mac;
- weighted readiness dashboard и более явный operational UI;
- стабилизированный committed benchmark-suite;
- pilot `real_corpus` с `5/5` cases и `20/20` targets;
- marker-based section quality benchmark;
- state expertise workflow для `ПП 145` и `ПП 87`;
- staged frontend flow для findings, user decisions и replacement loop;
- synthetic benchmark проектно-сметного спецworkflow: `4/4` cases, `10/10` targets;
- local baseline providers для terminology, visual quality, signature/seal evidence.

### Что остаётся сделать

- расширить `real_corpus` за пределы pilot;
- добавить обезличенный real corpus для проектно-сметного спецworkflow;
- провести comparative benchmark `baseline` vs `quality` vs `quality_plus`;
- усилить OCR/vision для scan-heavy и mixed-layout документов;
- улучшить reranking/evidence linking на более сложных пакетах;
- снизить false-positive в `filename -> content` classifier;
- оптимизировать API/UI для больших папок документов;
- расширить semantic evaluation generated sections.

### Критерии завершения

`MVP 2` можно считать завершённым, когда:

- расширенный corpus включён в validation contour;
- quality профили измерены на одинаковом benchmark-протоколе;
- OCR-backed residual cases улучшены относительно текущего baseline;
- state expertise real corpus проходит target evaluation;
- section quality оценивается не только marker-based, но и более семантически;
- большие папки документов не создают UI/API bottleneck.

## 5. `MVP 3` — процессный контур и интеграции

### Цель

Перевести систему от аналитической подготовки черновика к более зрелому процессу согласования и выпуска пакета.

### Состав

- расширенный контур согласования;
- enterprise process governance;
- task routing;
- более богатые уведомления;
- электронная подпись;
- внешние интеграции;
- multi-regulator templates.

### Критерии завершения

- пользователь проходит не только подготовку отчёта, но и выпускной процесс;
- поддерживается больше одного регуляторного шаблона;
- согласование и выпуск опираются на встроенный процессный контур.

## 6. `MVP 4` — production / platform maturity

### Цель

Сделать систему pilot-ready с точки зрения эксплуатации и платформенной зрелости.

### Состав

- security hardening;
- CI/CD;
- deployment profiles;
- retention / backup / recovery;
- production-grade observability;
- stress `10x+`;
- эксплуатационные runbooks.

### Критерии завершения

- есть стабильный deployment-контур;
- есть monitoring / alerting / recovery;
- подтверждён более высокий нагрузочный профиль;
- описаны эксплуатационные процедуры.

## 7. `Post-MVP / исследовательский горизонт`

- multimodal document understanding;
- layout-aware document vision beyond baseline;
- domain fine-tuning;
- mobile branch / thin iOS client;
- масштабирование за пределы текущих pilot-сценариев.

## 8. Отраслевой трек: государственная экспертиза

Этот трек расширяет `EvidenceXAI` на проектные организации и предварительную проверку проектной документации перед государственной экспертизой.

Уже реализованный прикладной слой:

- report type `state_expertise_estimate_cost_verification` для `ПП 145`;
- report type `state_expertise_estimate_cost_verification_pp87` для `ПП 87`;
- backend/Celery workflow со stages, findings, user decisions, replacement re-check, audit trail, XAI и export;
- frontend stage rail, sequential current-stage findings и отдельная верхняя панель действий выбранного отчёта;
- local terminology / visual quality / signature-seal baseline;
- synthetic benchmark and validator;
- реальный локальный прогон `Водоканалпроект / 1. ИРД / ПП 145`.

Ограничение: это предварительная автоматизированная проверка с XAI, а не юридическая замена государственной экспертизы.

Подробно:

- [state-expertise-roadmap.md](state-expertise-roadmap.md);
- [state-expertise-estimate-cost-report-tz-roadmap.md](state-expertise-estimate-cost-report-tz-roadmap.md);
- [current-project-status.md](current-project-status.md).

## 9. Приоритетность работ

Текущий порядок:

1. Довести активный `MVP 2`.
2. После стабилизации качества перейти к `MVP 3`.
3. После зрелого процессного контура перейти к `MVP 4`.
4. Исследовательские темы держать в `Post-MVP`, не смешивая их с завершённым `MVP 1`.

## 10. Связанные документы

- фактический статус: [roadmap-status.md](roadmap-status.md);
- master plan: [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md);
- системный обзор: [system-handbook.md](system-handbook.md);
- архитектура: [architecture.md](architecture.md);
- AI/XAI метод: [llm-xai-method.md](llm-xai-method.md);
- модели и XAI: [models-and-xai-overview.md](models-and-xai-overview.md).
