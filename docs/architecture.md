# Архитектура системы

Дата актуализации: `2026-05-29`

## 1. Назначение документа

Документ фиксирует текущую архитектуру `EvidenceXAI`, завершённый контур `MVP 1` и развитие в активном `MVP 2`.

Фактический roadmap-статус: [roadmap-status.md](roadmap-status.md).

## 2. Runtime-контур

Текущий runtime состоит из:

- `frontend` — web-клиент на `React 18 + TypeScript + Vite`;
- `backend-api` — REST API на `FastAPI`;
- `backend-worker` — `Celery` worker для долгих document/report/expertise задач;
- `postgres` — transactional data, full-text search, `pgvector`;
- `redis` — broker/result backend и shared runtime state;
- `filesystem storage` — исходные документы и export artifacts;
- `host Ollama` — штатный локальный AI runtime для embeddings и LLM;
- optional `ollama` compose service — контейнерный вариант хранения моделей;
- optional `prometheus / grafana / alertmanager` — observability profile.

Основной запуск для разработки и демонстрации:

```bash
bash infra/start_full_stack.sh
```

Он проверяет Docker, host Ollama, модели `all-minilm` и `gemma3:270m`, затем запускает backend/worker/frontend с `ollama` providers.

## 3. Доменная модель

Ключевые сущности:

- users, organizations, organization members;
- documents, document fragments;
- reports, sections, versions, exports;
- requirements;
- evidence;
- explanations;
- risks;
- audit logs;
- notifications;
- expertise workflows, stages, findings, user decisions.

Смысл доменной цепочки:

`organization -> document -> fragment -> requirement -> evidence -> explanation/XAI -> risk -> report/export`

Для государственной экспертизы добавляется:

`report -> expertise workflow -> stages -> findings -> user decisions/replacements -> XAI/export`

## 4. Документный pipeline

1. Пользователь загружает документ или папочный набор.
2. API сохраняет metadata, файл и `relative_path`.
3. Задача уходит в `document_process`.
4. Worker извлекает текст:
   - parser для text/json/xml/csv/xlsx/docx/pdf;
   - локальный converter/fallback для legacy `DOC`;
   - nested extraction для `ZIP`;
   - metadata/evidence handling для `SIG/P7S/GGE`;
   - локальный `Tesseract` для image files и image-only PDF.
5. Текст режется на fragments.
6. Для fragments считаются embeddings.
7. Fragments сохраняются в `PostgreSQL`, vector values — в `pgvector` или JSON fallback для SQLite tests.

## 5. Аналитический pipeline

1. Пользователь создаёт отчёт и выбирает документы.
2. Для обычных report types запускается `report_analyze`.
3. Система выделяет requirements из нормативных fragments.
4. Applicability считается rule-based.
5. Evidence linking ранжирует candidate fragments.
6. Confidence/status/risk рассчитываются по calibration settings.
7. XAI сохраняется как `Explanation`.
8. LLM генерирует sections на основе уже подготовленного context.
9. Export формирует `DOCX`, `XLSX`, `ZIP`, `HTML`.

Спецтипы государственной экспертизы не используют обычные `analyze/generate`. Для них запускается отдельный state expertise workflow.

## 6. AI/XAI контур

### 6.1. Local AI providers

- embeddings: `OllamaEmbeddingProvider`;
- LLM: `OllamaLLMProvider`;
- fallback embeddings: `HashEmbeddingProvider`;
- fallback LLM: `DeterministicFallbackLLMProvider`;
- optional local transformers provider остаётся доступным как альтернативный локальный path, но штатный demo path сейчас через `Ollama`.

### 6.2. Runtime profiles

Поддерживаются профили:

- `baseline`;
- `quality`;
- `quality_plus`.

Профиль задаёт ordered candidate list для embeddings и LLM. Resolver выбирает фактически доступную модель в локальном `Ollama`.

### 6.3. XAI storage

XAI хранится не как transient response модели, а как persisted domain artifact:

- для requirements: `Explanation`;
- для state expertise: `ExpertiseFinding.xai_json`;
- для user decisions: audit payload with XAI snapshot;
- для exports: XAI HTML и ZIP package.

Подробно: [llm-xai-method.md](llm-xai-method.md).

## 7. State expertise architecture

Реализованы два спецтипа:

- `state_expertise_estimate_cost_verification` — `ПП 145`;
- `state_expertise_estimate_cost_verification_pp87` — `ПП 87`.

Backend contour:

- `ExpertiseWorkflow`;
- `ExpertiseWorkflowStage`;
- `ExpertiseFinding`;
- `ExpertiseUserDecision`;
- Celery task `estimate_expertise_start_task`;
- Celery task `estimate_expertise_replacement_recheck_task`;
- API endpoints `start/state/approve/skip/replacement`.

`ПП 145` stages:

- `start`;
- `filename_content`;
- `completeness`;
- `quality_spell_signature`;
- `final`.

`ПП 87` stages:

- `start`;
- `filename_content`;
- `section_content`;
- `quality_spell_signature`;
- `final`.

Stage logic включает:

- hybrid rules + optional LLM classifier;
- rules pack для required document groups;
- terminology baseline;
- visual quality baseline;
- signature/seal baseline;
- XAI per finding;
- user decision and replacement loop.

## 8. Storage boundaries

- Business data: `PostgreSQL`.
- Vectors: `pgvector` in `PostgreSQL`.
- Source files: local filesystem / Docker volume.
- Export files: filesystem + DB records.
- Runtime task state: `Redis`.
- Local model runtime: host `Ollama` или optional compose service.

Документы не отправляются во внешние OCR/LLM API.

## 9. Observability

Реализован baseline:

- `GET /api/system/health`;
- `GET /api/system/ai-status`;
- `GET /api/system/metrics`;
- `GET /api/system/metrics/prometheus`;
- Prometheus scraping;
- Grafana dashboard `EvidenceXAI Overview`;
- Alertmanager routing baseline;
- alerts по backend availability, task failures, latency, queued tasks.

Это инженерный baseline, не полный production monitoring stack.

## 10. Архитектурное развитие

### `MVP 2`

- расширенный `real_corpus`;
- comparative AI profile benchmark;
- OCR/vision beyond current baseline;
- stronger evidence reranking;
- semantic section quality;
- real corpus для государственной экспертизы;
- API/UI optimization для больших document folders.

### `MVP 3`

- enterprise workflow;
- approval/governance;
- electronic signature;
- integrations;
- multi-regulator templates.

### `MVP 4`

- security hardening;
- CI/CD;
- deployment profiles;
- backup/recovery/retention;
- stress `10x+`;
- production-grade observability.

## 11. Итог

Архитектура уже достаточна для завершённого `MVP 1` и частично закрытого активного `MVP 2`: ядро не нужно переписывать, дальнейшее развитие идёт через усиление качества данных, моделей, OCR/vision, workflow и эксплуатации.
