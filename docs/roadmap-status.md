# Статус roadmap

Дата актуализации: `2026-05-29`

## 1. Назначение документа

Этот документ является единой фактической веткой roadmap для `EvidenceXAI`.

Он не заменяет продуктовый roadmap, но фиксирует текущее состояние реализации:

- что уже закрыто;
- что реализовано частично;
- что осталось в активной работе;
- какие документы и generated artifacts подтверждают статус.

При расхождении narrative-документов и generated artifacts приоритет такой:

1. код и тесты в `backend`, `frontend`, `infra`;
2. generated artifacts в `docs/*.json` и соответствующие generated `*.md`;
3. этот документ;
4. остальные обзорные документы.

Канонический roadmap версий: [product-roadmap.md](product-roadmap.md).
Текущий runtime и последний реальный прогон: [current-project-status.md](current-project-status.md).

## 2. Сводка по версиям

| Версия | Статус | Что означает сейчас |
|---|---|---|
| `MVP 1` | `завершён` | web-first функциональное ядро, документы, требования, evidence, XAI, отчёты, экспорт, базовая валидация |
| `MVP 2` | `активный этап` | усиление AI quality, OCR/vision, real corpus, прикладный трек государственной экспертизы |
| `MVP 3` | `запланирован` | процессный контур, интеграции, ЭП, governance, multi-regulator templates |
| `MVP 4` | `запланирован` | production/platform maturity, security, CI/CD, backup, stress `10x+`, mature observability |
| `Post-MVP` | `исследовательский горизонт` | multimodal document understanding, fine-tuning, mobile branch, новые отрасли |

## 3. Что закрыто в `MVP 1`

### 3.1. Продуктовый scope

Завершённый базовый контур включает:

- web-first сценарий работы специалиста и approver;
- multi-tenant организации, роли и membership;
- загрузку документов и работу с папочным деревом;
- обработку документов, фрагменты, поиск и embeddings;
- реестр требований, applicability, evidence linking, confidence, risks;
- сохранённые XAI-объяснения по требованиям;
- генерацию разделов отчёта;
- versioning, review / submit / approve;
- export `DOCX`, `XLSX`, `ZIP`, `HTML`;
- базовый demo/acceptance/benchmark contour.

### 3.2. Инженерный scope

Реализованы:

- backend: `FastAPI`, `SQLAlchemy 2`, `Alembic`, `Pydantic Settings`;
- data layer: `PostgreSQL`, `pgvector`, local filesystem storage;
- async layer: `Celery + Redis`;
- frontend: `React 18`, `TypeScript`, `Vite`, `React Router`;
- local AI runtime: `Ollama` для embeddings и LLM;
- OCR: локальный `Tesseract`;
- fallback providers: `hash-fallback` embeddings и `template-fallback` LLM как аварийная деградация;
- observability baseline: `Prometheus`, `Grafana`, `Alertmanager`.

### 3.3. Validation scope

В репозитории есть:

- backend tests;
- acceptance demo flow;
- gold quality benchmark;
- committed benchmark-suite;
- pilot `real_corpus`;
- calibration sweep;
- OCR benchmark;
- performance / load / stress artifacts;
- synthetic benchmark для проектно-сметного спецworkflow;
- manifest validator для будущего real corpus государственной экспертизы.

## 4. Подтверждающие артефакты

### 4.1. Core benchmark layer

| Артефакт | Статус |
|---|---|
| [quality-benchmark-results.md](quality-benchmark-results.md) | gold benchmark: extraction, applicability, evidence, sections = `1.0000` |
| [quality-benchmark-suite-results.md](quality-benchmark-suite-results.md) | `7` committed сценариев, evidence precision `0.9714`, recall `1.0000`, F1 `0.9855` |
| [calibration-sweep-results.md](calibration-sweep-results.md) | recommended profile на committed suite: `baseline_current` |

### 4.2. Real corpus layer

| Артефакт | Статус |
|---|---|
| [real-corpus-status.md](real-corpus-status.md) | pilot corpus готов к benchmark-проверке |
| [real-corpus-quality-suite-results.md](real-corpus-quality-suite-results.md) | aggregate precision/recall/F1 = `1.0000` |
| [real-corpus-target-evaluation.md](real-corpus-target-evaluation.md) | `5/5` cases, `20/20` targets |
| [real-corpus-calibration-sweep.md](real-corpus-calibration-sweep.md) | recommended profile на pilot corpus: `baseline_current` |

Жёсткий residual case: `college_gamma_ocr_package` в target evaluation всё ещё имеет `evidence_f1 = 0.7742`. Это уже выше target `0.3500`, но именно такой OCR-backed case-level слой остаётся хорошим фокусом `MVP 2`.

### 4.3. OCR, runtime and operations

| Артефакт | Статус |
|---|---|
| [ocr-benchmark-results.md](ocr-benchmark-results.md) | `char_similarity_mean = 0.9100`, `token_f1_mean = 0.9818`, `keyword_coverage_mean = 1.0000` |
| [performance-baseline.md](performance-baseline.md) | живой пользовательский контур измерен на `Ollama + all-minilm + gemma3:270m` |
| [runtime-comparison-performance.md](runtime-comparison-performance.md) | fallback быстрее, но `Ollama` нужен для качественной narrative generation |
| [load-baseline.md](load-baseline.md), [stress-baseline.md](stress-baseline.md), [stress-4x-baseline.md](stress-4x-baseline.md) | базовые load/stress срезы зафиксированы |
| [observability-stack.md](observability-stack.md) | baseline monitoring and alerting contour реализован |

### 4.4. State expertise layer

| Артефакт | Статус |
|---|---|
| [state-expertise-roadmap.md](state-expertise-roadmap.md) | отраслевой roadmap государственной экспертизы |
| [state-expertise-estimate-cost-report-tz-roadmap.md](state-expertise-estimate-cost-report-tz-roadmap.md) | детальное ТЗ и текущий статус спецworkflow |
| [estimate-expertise-corpus-evaluation.md](estimate-expertise-corpus-evaluation.md) | synthetic corpus: `4/4` cases, `10/10` targets, rule pack `estimate-cost-pp145-rules-pack-v8` |
| [estimate-expertise-corpus-validation.md](estimate-expertise-corpus-validation.md) | synthetic manifest валиден |
| [current-project-status.md](current-project-status.md) | реальный локальный прогон `Водоканалпроект / 1. ИРД / ПП 145` |

Реальный локальный прогон `ПП 145`:

- `180` выбранных документов;
- `153 processed`;
- `27 requires_review`;
- `0 failed`;
- workflow status: `blocked`;
- `48` findings;
- `35` unresolved findings.

Статус `blocked` корректен: система нашла замечания, которые должен обработать пользователь.

## 5. Что уже выполнено в активном `MVP 2`

`MVP 2` уже не пустой план. В коде и артефактах закрыты следующие подзадачи:

- profile-aware AI runtime: `baseline`, `quality`, `quality_plus`;
- model resolver для `Ollama`: выбор лучшей доступной модели из профиля;
- `/api/system/ai-status` показывает runtime profile, providers, candidate models, resolved models, fallback/model mode;
- Docker Compose и launcher по умолчанию переводят backend/worker в `ollama` provider mode;
- Docker Compose и launcher поддерживают overrides портов `XAI_BACKEND_PORT`, `XAI_FRONTEND_PORT`, `XAI_POSTGRES_PORT`, `XAI_REDIS_PORT`;
- добавлен online installer для Apple Silicon Mac с `.command`-скриптами установки, запуска, остановки, открытия и проверки;
- `quality-benchmark-suite` и pilot `real_corpus` стабилизированы после calibration work;
- marker-based section quality уже измеряется и на committed suite, и на real corpus;
- state expertise workflow для `ПП 145` и `ПП 87` перенесён в backend/Celery persistence contour;
- для `ПП 145` реализованы этапы `start -> filename_content -> completeness -> quality_spell_signature -> final`;
- для `ПП 87` вместо комплектности подачи по `ПП 145` используется этап `section_content`;
- реализованы findings, user decisions, replacement re-check, audit trail, XAI summary и export для спецworkflow;
- frontend показывает stage rail спецworkflow сверху и последовательно раскрывает findings текущего этапа;
- dashboard readiness переведён на weighted score по documents/reports/requirements/unresolved risks;
- добавлены локальные baseline-провайдеры `layout-baseline-v1`, `layout-quality-baseline-v1`, `local-terminology-rules-v1`;
- synthetic benchmark проектно-сметного спецworkflow проходит `4/4` cases и `10/10` targets;
- реальный локальный пакет `Водоканалпроект / 1. ИРД` подтверждает работу на большом наборе документов.

## 6. Что остаётся в `MVP 2`

Активные незакрытые задачи:

1. Расширить `real_corpus` за пределы текущего pilot-слоя.
2. Добавить обезличенные реальные проектно-сметные кейсы поверх `samples/estimate_expertise_corpus/real-corpus-template.json`.
3. Провести comparative benchmark профилей `baseline`, `quality`, `quality_plus`.
4. Улучшить OCR-backed case-level evidence quality, особенно для mixed-layout и scan-heavy документов.
5. Усилить reranker / evidence linking на multi-evidence кейсах без потери recall.
6. Снизить false-positive в classifier `filename -> content` на хаотичных реальных названиях файлов.
7. Оптимизировать API списка документов для больших папок: не возвращать полный `extracted_text` в реестре.
8. Расширить semantic section quality поверх текущей marker-based проверки.
9. Провести внутреннюю нормативную проверку rules pack государственной экспертизы перед pilot/production use.
10. Усилить `.doc` converter/parser и определить дальнейшую стратегию по `.gge`.

## 7. Что запланировано на `MVP 3`

После стабилизации `MVP 2` следующий слой:

- расширенный approval/governance workflow;
- task routing и richer notifications;
- электронная подпись;
- внешние интеграции;
- multi-regulator templates;
- более зрелая работа с версиями и выпуском пакета.

## 8. Что запланировано на `MVP 4`

Platform maturity:

- security hardening;
- CI/CD;
- deployment profiles;
- retention / backup / recovery;
- stress `10x+`;
- production-grade observability;
- эксплуатационные runbooks.

## 9. Что не входит в текущий завершённый контур

Проект пока не следует описывать как:

- production SaaS;
- юридически финальную систему государственной экспертизы;
- систему проверки подлинности подписи/печати;
- полноценный multimodal document understanding stack;
- domain-fine-tuned model;
- решение с внешними OCR/LLM API;
- iOS/mobile product.

Корректная формулировка:

> `EvidenceXAI` — локально разворачиваемая web-first платформа объяснимой подготовки отчётности. `MVP 1` завершён, а активный `MVP 2` уже содержит profile-aware локальный AI runtime, расширенные benchmark-артефакты, weighted readiness dashboard, macOS installer и прикладной спецworkflow государственной экспертизы с findings, XAI, user decisions и export, но production-grade vision, широкий real-world corpus и enterprise workflow ещё остаются задачами следующих этапов.
