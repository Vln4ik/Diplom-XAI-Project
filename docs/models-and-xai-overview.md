# Модели и XAI: обзор для диплома и разработки

Дата актуализации: `2026-05-29`

## 1. Зачем нужен этот документ

Документ даёт компактный, но проверенный по коду обзор:

- какие модели и baseline-провайдеры используются сейчас;
- какие методы принимают прикладные решения;
- как устроен XAI;
- что уже реализовано в `MVP 1` и начатом `MVP 2`;
- что нельзя заявлять как готовую возможность.

Подробный метод описан в [llm-xai-method.md](llm-xai-method.md).

## 2. Короткий ответ

В проекте используются:

- локальная embedding-модель для semantic retrieval;
- локальная generative LLM для summary/section generation и optional classifier assist;
- rule-based decision layer для applicability, status, confidence, risk и части спецworkflow;
- локальный OCR через `Tesseract`;
- локальные visual/terminology baselines;
- persisted XAI как объяснимый trace результата.

В проекте не используется как готовый контур:

- end-to-end LLM decision making;
- explainability внутренних весов модели;
- production-grade multimodal vision;
- domain fine-tuning;
- юридическая проверка подлинности подписи/печати.

## 3. Текущие модели и providers

| Слой | Текущая реализация | Назначение |
|---|---|---|
| Embeddings | `Ollama + all-minilm` в `baseline` | semantic search по fragments |
| LLM | `Ollama + gemma3:270m` в `baseline` | summary и generation sections |
| OCR | `Tesseract` | image files и image-only PDF |
| Visual signature/seal | `layout-baseline-v1` | bbox/confidence/evidence по signature-like/seal-like областям |
| Visual quality | `layout-quality-baseline-v1` | contrast/sharpness/resolution/blank-like checks |
| Terminology | `local-terminology-rules-v1` | проектно-сметная терминология, OCR noise, типовые ошибки |
| Fallback embeddings | `hash-fallback` | аварийная деградация |
| Fallback LLM | `template-fallback` | аварийная деградация |

## 4. AI runtime profiles

Код поддерживает три локальных профиля:

- `baseline`: `all-minilm + gemma3:270m`;
- `quality`: `nomic-embed-text / mxbai-embed-large` + `qwen2.5:3b / llama3.2:3b / gemma3:1b / gemma3:270m`;
- `quality_plus`: `mxbai-embed-large / nomic-embed-text` + `qwen2.5:7b / llama3.1:8b / qwen2.5:3b / llama3.2:3b / gemma3:1b / gemma3:270m`.

Профиль задаётся через `XAI_APP_AI_RUNTIME_PROFILE`.

`/api/system/ai-status` показывает:

- active profile;
- configured provider;
- candidate models;
- resolved model;
- доступность `Ollama`;
- mode `model` или `fallback`;
- статус OCR, vision, visual quality и terminology providers.

## 5. Метод анализа

Система работает как гибридный pipeline:

1. Документы загружаются и сохраняются локально.
2. Backend извлекает текст или запускает локальный OCR.
3. Текст делится на fragments.
4. Fragments получают embeddings.
5. Retrieval использует PostgreSQL full-text, `pgvector`, lexical overlap и fallback scoring.
6. Нормативные fragments превращаются в candidate requirements.
7. Applicability считается rule-based.
8. Evidence linking ранжирует fragments через lexical/vector/focus/hint/penalty scoring.
9. Confidence/status/risk рассчитываются на основе evidence и calibration settings.
10. LLM генерирует sections только после evidence-grounded этапов.
11. XAI сохраняет trace вывода и evidence payload.

Главная граница: LLM помогает с текстом и optional classification, но не заменяет audit-friendly decision logic.

## 6. Что такое XAI в EvidenceXAI

XAI — это сохранённый прикладной trace, а не отдельная нейросеть.

Для требований XAI хранит:

- conclusion;
- source requirement/document/fragment;
- evidence snippets;
- matched keywords;
- direct/focus match ratios;
- hint markers;
- confidence;
- risk;
- recommended action.

Для findings государственной экспертизы XAI хранит:

- stage;
- severity;
- normative basis;
- source reference;
- confidence;
- recommendation;
- `xai_json` со steps, snippets, classifier/visual/terminology evidence.

## 7. Что видит пользователь

Пользователь получает ответы:

- какое требование или замечание найдено;
- почему оно применимо или проблемно;
- какие документы и фрагменты стали evidence;
- какие маркеры совпали;
- насколько система уверена;
- какой риск остаётся;
- что делать дальше: подтвердить, отклонить, пропустить или загрузить замену.

## 8. Реализованный прикладной слой государственной экспертизы

В коде уже есть:

- `ПП 145` спецworkflow: `filename_content`, `completeness`, `quality_spell_signature`, `final`;
- `ПП 87` спецworkflow: `filename_content`, `section_content`, `quality_spell_signature`, `final`;
- hybrid classifier `rules + optional LLM`;
- local terminology and OCR-noise baseline;
- visual quality baseline;
- signature/seal-like baseline;
- findings persistence;
- user decisions;
- replacement re-check;
- audit trail;
- export `DOCX/XLSX/XAI HTML/ZIP`.

Текущий model/rule state:

- `MODEL_VERSION = estimate-expertise-local-terminology-baseline-v7`;
- `ПП 145 RULE_VERSION = estimate-cost-pp145-rules-pack-v8`;
- `ПП 87 RULE_VERSION = estimate-cost-pp87-rules-pack-v3`.

## 9. Подтверждающие метрики

Базовый gold benchmark:

- requirement extraction F1: `1.0000`;
- evidence linking F1: `1.0000`;
- section source coverage: `1.0000`.

Committed suite:

- `7` scenarios;
- evidence linking precision: `0.9714`;
- evidence linking F1: `0.9855`;
- section quality pass share: `100.00%`.

Pilot `real_corpus`:

- `5/5` cases;
- `20/20` targets;
- aggregate evidence precision/recall/F1: `1.0000`;
- hardest OCR-backed residual case: `college_gamma_ocr_package`, `evidence_f1 = 0.7742`.

Estimate expertise synthetic benchmark:

- `4/4` cases;
- `10/10` targets;
- rule pack in generated artifact: `estimate-cost-pp145-rules-pack-v8`.

## 10. Правильная формулировка для защиты

> `EvidenceXAI` использует гибридный AI/XAI-контур: локальные transformer embeddings для retrieval, локальную generative LLM для generation и optional classifier assist, rule-based логику для applicability/confidence/risk, локальный OCR/visual baseline и persisted XAI. XAI объясняет прикладной вывод через evidence, logic chain, confidence, risk, normative basis и recommended action, а не внутренние веса модели.

## 11. Следующие шаги

`MVP 2` по блоку моделей и XAI остаётся сфокусирован на:

- comparative benchmark профилей `baseline / quality / quality_plus`;
- расширении `real_corpus`;
- реальном обезличенном корпусе проектно-сметной документации;
- усилении OCR/vision beyond baseline;
- снижении false-positive в `filename -> content`;
- semantic section quality;
- улучшении evidence reranking без потери recall.
