# План развития EvidenceXAI

Дата актуализации: `2026-05-29`

## 1. Назначение документа

Это master plan проекта. Он связывает продуктовый roadmap, текущий статус, архитектуру, AI/XAI-метод и validation artifacts.

Единый фактический статус по завершённым и незавершённым пунктам ведётся в [docs/roadmap-status.md](docs/roadmap-status.md). Этот файл отвечает за стратегическую структуру версий.

## 2. Текущая точка

Состояние проекта:

- `MVP 1` завершён;
- активный этап: `MVP 2`;
- основной завершённый сценарий: `Рособрнадзор + образовательная организация`;
- текущий расширенный прикладной трек: государственная экспертиза проектной документации, `ПП 145` и `ПП 87`;
- штатный demo/runtime путь: локальный `Ollama + Tesseract + rule-based/XAI` без внешних OCR/LLM API.
- актуальный delivery layer: Docker Compose launcher с configurable ports и macOS online installer для Apple Silicon.

## 3. Что включает завершённый `MVP 1`

### 3.1. Backend и данные

- `FastAPI + SQLAlchemy + Alembic`;
- роли и multi-tenant organization scope;
- документы, фрагменты, требования, evidence, explanations, risks, reports;
- report versions, exports, audit, notifications;
- `PostgreSQL + pgvector`;
- `Celery + Redis`;
- local filesystem storage.

### 3.2. Документный контур

- upload документов и папочных наборов;
- обработка `PDF`, `DOCX`, `DOC`, `XLSX`, `CSV`, `TXT`, `JSON`, `XML`, `ZIP`, `SIG`, `P7S`, `GGE`, `JPG/PNG/TIFF/BMP`;
- chunking и индексирование;
- embeddings и retrieval;
- базовый OCR-контур через локальный `Tesseract`.

### 3.3. Аналитический контур

- извлечение требований;
- applicability;
- evidence linking;
- confidence;
- risk generation;
- сохранённые XAI-объяснения;
- section generation.

### 3.4. Пользовательский результат

- web UI основного сценария;
- документы и дерево папок;
- требования, матрица, риски, XAI;
- weighted readiness dashboard;
- сортировка документов по проблемности;
- report workflow;
- export `DOCX/XLSX/ZIP/HTML`;
- review / submit / approve.

### 3.5. Контур валидации

- tests;
- acceptance demo-сценарий;
- gold quality benchmark;
- committed benchmark-suite;
- pilot `real_corpus`;
- calibration sweep;
- OCR benchmark;
- performance / load / stress artifacts;
- observability baseline.

## 4. Активный этап `MVP 2`

### Цель

Усилить качество AI/document-understanding контура на реалистичных корпусах и расширить прикладной сценарий государственной экспертизы, сохранив локальность runtime и объяснимость вывода.

### Уже реализовано

- profile-aware AI runtime `baseline / quality / quality_plus`;
- resolved model selection для локального `Ollama`;
- `/api/system/ai-status`;
- Docker/launcher default на `XAI_APP_EMBEDDING_PROVIDER=ollama` и `XAI_APP_LLM_PROVIDER=ollama`;
- Docker/launcher port overrides для backend/frontend/postgres/redis;
- macOS online installer и install/start/stop/open/check command package;
- committed benchmark-suite с evidence precision `0.9714` и F1 `0.9855`;
- pilot `real_corpus`: `5/5` cases, `20/20` targets;
- marker-based section quality benchmark;
- state expertise workflow для `ПП 145` и `ПП 87`;
- findings, user decisions, replacement re-check, audit trail, XAI summary и export для спецworkflow;
- frontend stage rail и sequential current-stage findings для спецworkflow;
- local terminology, visual quality и signature/seal baseline providers;
- synthetic estimate expertise benchmark: `4/4` cases, `10/10` targets;
- реальный локальный прогон `Водоканалпроект / 1. ИРД / ПП 145`.

### Осталось реализовать

- расширенный `real_corpus`;
- обезличенный real corpus проектно-сметной документации;
- comparative benchmark `baseline` vs `quality` vs `quality_plus`;
- более сильный OCR/vision contour;
- улучшение reranker/evidence linking на сложных документах;
- снижение false-positive в `filename -> content`;
- API/UI optimization для больших папок;
- semantic section quality поверх marker-based проверки;
- внутренняя нормативная проверка rules pack государственной экспертизы.

## 5. `MVP 3`

Цель: перейти от аналитического инструмента к workflow-aware platform.

Состав:

- расширенный approval/governance workflow;
- richer notifications и task routing;
- electronic signature;
- external integrations;
- multi-regulator templates;
- более зрелая логика выпуска и фиксации итогового пакета.

## 6. `MVP 4`

Цель: platform maturity и pilot-ready эксплуатация.

Состав:

- security hardening;
- CI/CD;
- deployment profiles;
- retention / backup / recovery;
- production-grade observability;
- stress `10x+`;
- operational runbooks.

## 7. Post-MVP

Исследовательский горизонт:

- multimodal document understanding;
- production-grade layout-aware vision beyond current baseline;
- domain fine-tuning;
- mobile branch / thin iOS client;
- новые отрасли и регуляторы.

## 8. Принципы развития

- `MVP 1` не расширяется бесконечно: крупные новые задачи относятся к `MVP 2+`.
- Generated artifacts считаются источником истины по числам.
- Narrative docs должны интерпретировать артефакты, а не заменять их.
- Локальный runtime остаётся ключевой архитектурной границей.
- XAI описывает прикладной вывод, evidence и decision trace, а не внутренние веса нейросети.
- Все юридически чувствительные проверки формулируются как предварительная автоматизированная проверка с human review.

## 9. Канонические документы

- версионный roadmap: [docs/product-roadmap.md](docs/product-roadmap.md);
- фактический статус: [docs/roadmap-status.md](docs/roadmap-status.md);
- текущий runtime и реальный прогон: [docs/current-project-status.md](docs/current-project-status.md);
- системный обзор: [docs/system-handbook.md](docs/system-handbook.md);
- архитектура: [docs/architecture.md](docs/architecture.md);
- AI/XAI метод: [docs/llm-xai-method.md](docs/llm-xai-method.md);
- модели и XAI: [docs/models-and-xai-overview.md](docs/models-and-xai-overview.md);
- государственная экспертиза: [docs/state-expertise-roadmap.md](docs/state-expertise-roadmap.md);
- спецworkflow `ПП 145 / ПП 87`: [docs/state-expertise-estimate-cost-report-tz-roadmap.md](docs/state-expertise-estimate-cost-report-tz-roadmap.md).
