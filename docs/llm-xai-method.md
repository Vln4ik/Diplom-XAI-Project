# LLM и XAI метод

Дата актуализации: `2026-05-29`

## 1. Назначение документа

Документ описывает текущий AI/XAI-метод `EvidenceXAI` по фактическому коду и артефактам:

- какие модели и providers реально подключены;
- где используется LLM, а где rule-based logic;
- как работает retrieval/evidence/confidence;
- что именно сохраняется как XAI;
- какие части подтверждены benchmark-артефактами;
- какие ограничения остаются задачами `MVP 2+`.

Термины:

- `EvidenceXAI` — название продукта;
- `EX.AI` — компактная UI-метка;
- `XAI` — explainability layer, то есть объяснение прикладного вывода.

## 2. Главный принцип метода

Проект не является one-shot LLM системой.

Текущая схема:

`documents -> extraction/OCR -> fragments -> embeddings -> retrieval -> requirement mining -> applicability -> evidence linking -> confidence/risk -> LLM generation -> persisted XAI`

Смысл этой архитектуры:

- LLM не принимает финальное регуляторное решение одна;
- решение строится на фрагментах документов, правилах, score и evidence;
- XAI сохраняется как бизнес-артефакт, доступный в UI и export;
- пользователь остаётся в контуре проверки и может подтвердить, отклонить или заменить спорный документ.

## 3. Runtime и стек моделей

### 3.1. Штатный локальный runtime

Штатный demo/runtime режим:

- embeddings: `Ollama + all-minilm`;
- LLM: `Ollama + gemma3:270m`;
- OCR: локальный `Tesseract`;
- visual signature/seal: `layout-baseline-v1`;
- visual quality: `layout-quality-baseline-v1`;
- terminology/spelling baseline: `local-terminology-rules-v1`;
- decision logic: rule-based Python services;
- XAI: persisted records in DB plus export payloads.

Внешние OCR/LLM API не используются как часть текущей архитектурной границы.

### 3.2. AI runtime profiles

В коде реализован profile-aware resolver:

| Profile | Embedding candidates | LLM candidates | Назначение |
|---|---|---|---|
| `baseline` | `all-minilm` | `gemma3:270m` | быстрый локальный запуск |
| `quality` | `nomic-embed-text`, `mxbai-embed-large`, `all-minilm` | `qwen2.5:3b`, `llama3.2:3b`, `gemma3:1b`, `gemma3:270m` | улучшение retrieval/generation на умеренном железе |
| `quality_plus` | `mxbai-embed-large`, `nomic-embed-text`, `all-minilm` | `qwen2.5:7b`, `llama3.1:8b`, `qwen2.5:3b`, `llama3.2:3b`, `gemma3:1b`, `gemma3:270m` | максимально сильный локальный профиль для benchmark/demo |

Resolver проверяет список моделей в `Ollama` и выбирает первую доступную модель из профиля. Для `baseline` приоритет сохраняется за configured model, для `quality` и `quality_plus` — за candidates профиля.

### 3.3. Fallback providers

Fallback providers нужны для отказоустойчивости, а не для полноценной демонстрации:

- `hash-fallback` embeddings строит нормализованный вектор по token buckets;
- `template-fallback` LLM возвращает детерминированный summary/section text;
- если `Ollama` недоступна, backend сохраняет работоспособность, но quality/demo режим считается деградировавшим.

`/api/system/ai-status` показывает provider, configured model, candidate models, resolved model, доступность `Ollama`, mode `model/fallback` и runtime profile.

## 4. Документный pipeline

### 4.1. Извлечение текста

Поддерживаемые источники включают:

- `PDF`;
- `DOCX`;
- legacy `DOC` через `antiword`/`LibreOffice` или fallback binary string extraction;
- `XLSX`, `CSV`;
- `TXT`, `JSON`, `XML`;
- `ZIP` с ограничениями по числу и размеру вложений;
- `SIG/P7S/GGE` как evidence/metadata-like источники;
- `JPG/PNG/TIFF/BMP`;
- image-only `PDF` через локальный OCR.

Если извлечение ненадёжно, документ может получить `requires_review`, но не обязательно считается failed.

### 4.2. OCR

`TesseractOCRProvider`:

- работает локально;
- проверяет несколько `psm` режимов: `3`, `4`, `11`;
- сравнивает OCR candidates по confidence, token count и структуре строк;
- использует варианты изображения `original` и `threshold`;
- пытается восстановить table-like rows через image layout heuristics.

Текущий OCR benchmark:

- `char_similarity_mean = 0.9100`;
- `token_f1_mean = 0.9818`;
- `keyword_coverage_mean = 1.0000`.

### 4.3. Fragment model

Документ режется на фрагменты:

- `paragraph`;
- `page`;
- `sheet_row`;
- `table_row`.

Фрагмент хранит:

- текст;
- page/sheet/row/paragraph metadata;
- search text;
- embedding vector.

Это основа для retrieval, evidence linking и XAI source references.

## 5. Retrieval и evidence linking

### 5.1. Embeddings

`OllamaEmbeddingProvider` вызывает локальный endpoint `/embed`:

- model: resolved embedding model;
- `dimensions`: `XAI_APP_EMBEDDING_SIZE`, сейчас default `32`;
- output адаптируется до target vector size.

Если `Ollama` недоступна или возвращает некорректный payload, используется `hash-fallback`.

### 5.2. Ranking

Retrieval использует гибридный scoring:

- PostgreSQL full-text score через `to_tsvector/plainto_tsquery/ts_rank_cd`, если backend работает на PostgreSQL;
- vector similarity через `pgvector` cosine distance;
- Python keyword overlap fallback;
- Python cosine similarity fallback;
- optional domain bonuses.

Итоговая формула в текущем `rank_fragments`:

`total_score = 0.56 * keyword_score + 0.34 * vector_score + bonus`

Score ограничивается сверху `0.99`. Для списков можно ограничивать число фрагментов на документ.

### 5.3. Evidence candidate scoring

Для требования дополнительно считаются:

- lexical score;
- direct token/root coverage;
- focus token coverage;
- aligned hint markers;
- structured row bonuses;
- penalties за generic/boolean/noisy evidence;
- narrative bonuses.

Это позволяет отличать:

- содержательное narrative evidence;
- structured rows;
- слишком общие или шумные совпадения;
- boolean hints, которые без контекста не должны давать чрезмерную уверенность.

## 6. Извлечение требований и decision logic

### 6.1. Requirement mining

Candidate requirements извлекаются из нормативных фрагментов через:

- marker hits: `должен`, `должна`, `обязан`, `требуется`, `необходимо`, `предоставить`, `разместить`;
- category markers;
- token roots;
- requirement signatures;
- similarity-based deduplication.

Требования получают title, category, required_data и source fragment.

### 6.2. Applicability

Applicability не отдаётся LLM. Он считается rule-based:

- учитывается report type;
- учитывается organization profile;
- проверяются разрешённые domain tokens;
- результат: `applicable`, `needs_clarification`, `not_applicable` и reason.

### 6.3. Confidence, status, risk

На основе applicability, evidence count, score и calibration settings выводятся:

- requirement status;
- confidence score;
- risk level;
- recommended action.

Примеры статусов:

- `data_found`;
- `data_partial`;
- `data_missing`;
- `needs_clarification`;
- `not_applicable`;
- `confirmed`;
- `rejected`;
- `included_in_report`.

Manual locks сохраняют пользовательское решение и не перетираются автоматическим пересчётом.

## 7. Где используется LLM

### 7.1. Основной отчётный контур

LLM используется после evidence/retrieval/decision layer:

- summary;
- generation report sections;
- narrative synthesis на переданном контексте.

LLM prompt прямо ограничивает генерацию:

- не выдумывать факты;
- опираться только на context;
- использовать деловой русский стиль.

### 7.2. Спецworkflow государственной экспертизы

В `estimate_expertise` LLM используется опционально как classifier assist:

- задача: классифицировать тип проектно-сметного документа;
- вход: имя файла, relative path, extracted text fragment;
- выход ожидается как JSON `label/confidence/reason`;
- если provider fallback или JSON не распарсился, workflow продолжает работу на rules.

Итоговый classifier остаётся гибридным:

- name evidence;
- content evidence;
- optional LLM label;
- weighted confidence;
- XAI steps с explanation.

## 8. Что такое XAI в проекте

### 8.1. Определение

XAI здесь — не объяснение внутренних весов transformer-модели.

XAI — это сохранённая trace-структура прикладного вывода:

- что система решила;
- на каких требованиях и документах основан вывод;
- какие evidence snippets совпали;
- какие score/coverage/confidence использованы;
- какой риск остался;
- что рекомендуется сделать пользователю.

### 8.2. XAI для требований

Для каждого requirement сохраняется `Explanation`:

- `conclusion`;
- `logic_json`;
- `source_document_id`;
- `source_fragment_id`;
- `evidence_json`;
- `confidence_score`;
- `risk_level`;
- `explanation_text`;
- `recommended_action`.

`evidence_json` содержит по фрагментам:

- `document_id`;
- `fragment_id`;
- `description`;
- `confidence_score`;
- `matched_keywords`;
- `matched_token_ratio`;
- `direct_match_ratio`;
- `direct_match_count`;
- `focus_match_ratio`;
- `focus_match_count`;
- `aligned_hint_markers`;
- `evidence_kind`.

### 8.3. XAI для findings государственной экспертизы

`ExpertiseFinding` хранит:

- `stage_key`;
- `document_id`;
- `title`;
- `description`;
- `severity`;
- `confidence_score`;
- `normative_basis`;
- `source_ref`;
- `recommendation`;
- `xai_json`;
- user decision fields;
- replacement metadata.

`xai_json` по findings объясняет:

- какой stage сработал;
- какой нормативный профиль применялся (`ПП 145` или `ПП 87`);
- какие маркеры имени/содержания найдены;
- какие snippets подтверждают вывод;
- что нашёл visual/terminology baseline;
- почему вывод является preliminary warning, а не юридическим финальным решением.

### 8.4. Пользовательская работа с XAI

В UI пользователь видит:

- XAI по требованиям;
- XAI drawer/floating context widget;
- XAI по findings спецworkflow через кнопку `XAI` или double click;
- confidence, severity, recommendation и source reference;
- действия `approve`, `skip`, `replacement`.

Экспорты сохраняют XAI в `HTML` и `ZIP` пакетах.

## 9. Метод государственной экспертизы

### 9.1. `ПП 145`

Workflow stages:

1. `start`;
2. `filename_content`;
3. `completeness`;
4. `quality_spell_signature`;
5. `final`.

Проверки:

- соответствие имени файла содержанию;
- комплектность групп документов;
- mandatory / recommended / conditional groups;
- низкая плотность text layer;
- local terminology/spelling/OCR-noise signals;
- text signature markers;
- visual signature/seal-like components;
- visual quality issues;
- unresolved findings before final readiness.

Текущий rule pack: `estimate-cost-pp145-rules-pack-v8`.

### 9.2. `ПП 87`

Для `ПП 87` реализован отдельный report type:

`state_expertise_estimate_cost_verification_pp87`

Отличие от `ПП 145`:

- не запускается этап комплектности подачи по `ПП 145`;
- используется `section_content`;
- проверяются разделы проектной документации и содержательные признаки по `ПП 87`.

### 9.3. Visual baselines

`layout-baseline-v1`:

- анализирует изображение или первую страницу PDF;
- ищет signature-like и seal-like компоненты;
- возвращает bbox, confidence, evidence;
- не утверждает юридическую подлинность подписи или печати.

`layout-quality-baseline-v1`:

- оценивает resolution, contrast, sharpness;
- dark/bright ratio;
- blank-like / low-resolution / low-contrast признаки;
- возвращает evidence and confidence.

## 10. Что уже подтверждено метриками

### 10.1. Gold benchmark

- `requirement extraction F1 = 1.0000`;
- `applicability accuracy = 1.0000`;
- `evidence linking F1 = 1.0000`;
- `report sections source coverage = 1.0000`.

### 10.2. Committed benchmark-suite

- `7` сценариев;
- `requirement extraction F1 = 1.0000`;
- `evidence linking precision = 0.9714`;
- `evidence linking recall = 1.0000`;
- `evidence linking F1 = 0.9855`;
- `section quality pass share = 100.00%`.

### 10.3. Pilot real corpus

- `5/5` cases passed;
- `20/20` targets passed;
- aggregate evidence precision/recall/F1 = `1.0000`;
- hardest residual OCR-backed case: `college_gamma_ocr_package`, `evidence_f1 = 0.7742`.

### 10.4. Estimate expertise synthetic corpus

- `4/4` cases passed;
- `10/10` targets passed;
- stages covered: `filename_content`, `completeness`, `quality_spell_signature`;
- current rule version in generated artifact: `estimate-cost-pp145-rules-pack-v8`.

## 11. Что не следует утверждать

Нельзя описывать текущую систему как:

- explainability внутренних весов LLM;
- юридически финальную систему государственной экспертизы;
- проверку подлинности рукописной подписи или печати;
- production-grade multimodal vision stack;
- domain fine-tuned model;
- полностью автономную систему без human review.

Корректная формулировка:

> `EvidenceXAI` использует гибридный локальный AI pipeline: neural embeddings через `Ollama`, локальную LLM для generation/classifier assist, rule-based decision logic, OCR/visual baselines и persisted XAI. XAI объясняет не веса модели, а прикладной вывод: requirement, evidence, logic chain, confidence, risk, normative basis, recommendation и действия пользователя.

## 12. Основные задачи `MVP 2`

Остаются в активной работе:

- comparative benchmark `baseline / quality / quality_plus`;
- расширение `real_corpus`;
- обезличенный real corpus проектно-сметных кейсов;
- OCR/vision beyond current baselines;
- снижение false-positive в `filename -> content`;
- stronger reranking на multi-evidence кейсах;
- semantic section quality;
- оптимизация больших папочных пакетов;
- нормативная проверка rules pack перед pilot/production use.
