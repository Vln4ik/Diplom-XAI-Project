# LLM и XAI метод

## 1. Назначение документа

Документ описывает:

- какой AI/XAI контур уже используется в `MVP 1`
- как именно система принимает прикладные решения
- что подтверждено benchmark-артефактами
- что относится к `MVP 2+`, а не к текущей версии

В терминах бренда:

- `EvidenceXAI` — название продукта
- `EX.AI` — компактная UI-метка
- `XAI` — explainability-слой внутри продукта

## 2. Общий принцип AI-контура

В проекте используется не одна “магическая” модель, а гибридный pipeline:

`documents -> fragments -> embeddings -> retrieval -> requirement mining -> applicability -> evidence linking -> confidence/risk -> LLM generation -> XAI`

Это принципиально важно для регуляторного use case:

- логика должна быть аудируемой
- evidence должно быть прослеживаемым
- пользователь должен видеть причину вывода

## 3. Что реально используется в `MVP 1`

### 3.1. Embedding-модель

Текущий embedding-контур:

- runtime: `Ollama`
- модель: `all-minilm`
- роль: semantic search по фрагментам

### 3.2. Generative LLM

Текущий генеративный контур:

- runtime: `Ollama`
- модель: `gemma3:270m`
- роль: генерация разделов и текстовый синтез

### 3.3. Базовый OCR-контур

Текущий OCR-контур:

- provider: `Tesseract`
- роль: базовое извлечение текста из image-files и image-only `PDF`
- runtime: локальный backend/worker контур без отправки документов во внешний OCR API

### 3.4. Rule-based слой

В `MVP 1` значимая часть прикладной логики строится не на одной нейросети, а на rule-based контуре:

- applicability
- confidence
- risk level
- requirement / evidence status logic

### 3.5. Runtime profiles для локальных моделей

Начиная с активного этапа `MVP 2`, локальный AI runtime больше не жёстко привязан к одной паре моделей. В проекте введён слой `AI runtime profiles`, который позволяет переключать локальный контур без изменения прикладного кода.

Текущие профили:

- `baseline`
  - embeddings: `all-minilm`
  - LLM: `gemma3:270m`
  - назначение: быстрый и дешёвый локальный запуск
- `quality`
  - embeddings: `nomic-embed-text`, fallback `mxbai-embed-large`, затем `all-minilm`
  - LLM: `qwen2.5:3b`, fallback `llama3.2:3b`, затем `gemma3:1b`, затем `gemma3:270m`
  - назначение: улучшение retrieval и generation без перехода на самые тяжёлые модели
- `quality_plus`
  - embeddings: `mxbai-embed-large`, fallback `nomic-embed-text`, затем `all-minilm`
  - LLM: `qwen2.5:7b`, fallback `llama3.1:8b`, затем более лёгкие профили
  - назначение: максимально сильный локальный runtime для benchmark и демонстраций на более мощной машине

Выбор профиля задаётся через `XAI_APP_AI_RUNTIME_PROFILE`. При старте стека resolver проверяет доступные локальные модели в `Ollama` и выбирает наиболее сильную из списка профиля, которая реально присутствует на хосте.

## 4. Что не используется как завершённый контур

В `MVP 1` не используются как полноценно реализованные слои:

- `CNN`-based document vision pipeline
- multimodal end-to-end reasoning
- domain fine-tuning
- production neural reranker
- one-shot LLM decision system

## 5. Как работает текущий AI pipeline

### 5.1. Извлечение и chunking

Система извлекает текст из документов и делит его на фрагменты:

- paragraph
- page
- sheet row
- table row

### 5.2. Извлечение требований

Система выделяет candidate requirements из нормативных фрагментов:

- маркерная логика
- категоризация
- дедупликация
- отбор нормативных фрагментов

### 5.3. Applicability

Система оценивает применимость требования к сценарию организации через rule-based logic и organization profile.

### 5.4. Retrieval и evidence linking

Для каждого требования система:

- подбирает candidate evidence
- выполняет rescoring
- учитывает lexical overlap, focus markers, structured rows и penalties за noise

### 5.5. Confidence and risk

После отбора доказательств система вычисляет:

- requirement status
- confidence
- risk level
- recommended action

### 5.6. Генерация разделов

Только после этого LLM включается в генерацию разделов и сборку текста отчёта.

Это значит:

- LLM не является единственным источником прикладного решения
- бизнес-вывод определяется гибридным контуром, а не чистой генерацией

## 6. Текущий XAI-подход

### 6.1. Что означает XAI здесь

В проекте XAI — это не объяснение внутренних весов нейросети, а сохранённая decision trace по прикладному выводу.

Система сохраняет:

- conclusion
- requirement source
- evidence payload
- logic chain
- confidence
- risk
- recommended action

### 6.2. Почему это удобно пользователю

Пользователь видит:

- какое требование было выделено
- почему оно считается применимым
- какие доказательства его подтверждают
- насколько система уверена
- какой риск остаётся
- что делать дальше

### 6.3. Почему это лучше для данного use case

Для регуляторной отчётности важнее не explainability нейронных слоёв, а explainability прикладного вывода:

- откуда взялось требование
- на каком evidence стоит вывод
- почему статус именно такой

## 7. Что уже подтверждено на `MVP 1`

### 7.1. Gold benchmark

- `requirement extraction F1`: `1.0000`
- `evidence linking F1`: `1.0000`

### 7.2. Extended committed suite

- `7` сценариев
- `requirement extraction F1`: `1.0000`
- `evidence linking precision`: `0.9444`
- `evidence linking F1`: `0.9714`
- `source requirement coverage`: `100.00%`
- `section quality pass share`: `100.00%`

### 7.3. Пилотный `real_corpus`

- `5` кейсов, готовых к benchmark-проверке
- `5 из 5` кейсов прошли проверку
- `20 из 20` целевых критериев выполнены
- `evidence linking precision`: `1.0000`
- `evidence linking recall`: `1.0000`
- `evidence linking F1`: `1.0000`
- `source requirement coverage`: `100.00%`
- `section quality pass share`: `100.00%`

Эти цифры подтверждают, что `MVP 1` уже имеет рабочий и измеримый AI/XAI-контур, а не только демо на словах.

## 8. Что именно станет предметом `MVP 2`

`MVP 2` в AI-части включает:

- расширенный `real_corpus`
- более сильный OCR / vision-контур
- более сильные embeddings
- более сильную локальную LLM
- улучшение reranker / evidence linking
- benchmark качества разделов
- более широкую calibration-стратегию

На текущий момент внутри этого блока уже реализован инфраструктурный фундамент:

- profile-aware выбор локальной embedding-модели
- profile-aware выбор локальной LLM
- статус профиля и resolved model в `/api/system/ai-status`
- запуск backend stack с profile-aware резолвингом моделей
- гибридный classifier для спецотчета государственной экспертизы: `rules + optional LLM`, confidence и XAI evidence snippets для проверки `название файла -> содержание`
- quality baseline для спецотчета: OCR/text-layer эвристики, scan-like detector по плотности текста и XAI-сигналы по подписям/печатям
- layout-aware baseline для спецотчета: поиск signature-like/seal-like компонентов на изображении или первой странице PDF с bbox/confidence

То есть шаг `более сильные локальные модели` уже начат инженерно; следующий подэтап — измерить прирост качества на `quality` и `quality_plus` в benchmark-контуре.

Главная идея:

- не перепридумать `MVP 1`
- а усилить уже работающий AI/XAI-фундамент

## 9. Что относится к более дальнему горизонту

После `MVP 2` и `MVP 3` в AI/research ветке возможны:

- layout-aware document understanding
- multimodal evidence reasoning
- domain fine-tuning
- richer semantic evaluation of generated sections

## 10. Короткий итог

Корректная формулировка текущего состояния:

> В `MVP 1` проект использует text-centric hybrid AI pipeline с локальными transformer-моделями, rule-based decision logic, базовым OCR-контуром и сохранённым XAI. Следующий активный этап развития — `MVP 2`, где основной фокус смещается в качество анализа, OCR/vision и расширенный real-corpus benchmark.
