# План развития XAI Report Builder

## 1. Назначение документа

Этот документ больше не фиксирует только стартовый план первой сборки.  
Теперь это основной roadmap проекта, который показывает:

- что уже реализовано
- какой scope закрыт в `MVP 1`
- что входит в `MVP 2`
- что входит в `MVP 3`
- какие доработки вынесены в `MVP 4+`

## 2. Текущая точка

Текущее состояние проекта:

- `MVP 1` завершён
- основной web-first сценарий реализован
- ядро доменной логики работает
- benchmark и acceptance-контур уже собраны
- следующий активный этап: `MVP 2`

## 3. Что включает завершённый `MVP 1`

`MVP 1` закрывает функциональное ядро платформы.

### 3.1. Backend и данные

- `FastAPI + SQLAlchemy + Alembic`
- роли и multi-tenant organization scope
- документы, фрагменты, требования, evidence, explanations, risks, reports
- storage abstraction
- audit / notifications / report versions

### 3.2. Документный контур

- upload документов
- обработка `PDF`, `DOCX`, `XLSX`, `CSV`, `TXT`, `JSON`
- chunking и индексирование
- embeddings и retrieval
- базовый OCR-контур для image-файлов и image-only `PDF`

### 3.3. Аналитический контур

- извлечение требований
- applicability
- evidence linking
- confidence
- risk generation
- сохранённые XAI-объяснения
- section generation

### 3.4. Пользовательский результат

- web UI для основного сценария
- matrix
- explanations
- risks
- report editor
- export `DOCX/XLSX/ZIP/HTML`
- контур review / submit / approve

### 3.5. Контур валидации

- tests
- acceptance demo-сценарий
- quality benchmark
- extended benchmark-suite
- pilot `real_corpus`
- calibration sweep
- базовый observability-контур

## 4. Roadmap по версиям

## 4.1. `MVP 2` — AI quality first

### Цель

Повысить качество аналитического AI-контура на более реалистичных данных и сделать quality-контур сильнее, чем в текущем MVP.

### Что входит

- расширенный `real_corpus`
- более богатая benchmark-разметка
- усиленный OCR / vision-контур
- улучшение reranker и evidence linking
- benchmark качества разделов
- более сильные локальные embeddings
- более сильная локальная LLM
- воспроизводимая calibration-стратегия на большем корпусе

### Ключевые результаты

- real corpus шире pilot-слоя
- quality benchmark для generated sections
- улучшенный OCR/mixed-layout contour
- стабильные calibration profiles
- снижение числа слабых доказательств и ложноположительных трасс

### Критерии завершения

- расширенный размеченный корпус внедрён в репозиторий
- качество на real-corpus слое стабилизировано
- section quality формально измеряется
- OCR/vision слой уже не ограничивается только базовым `Tesseract`

## 4.2. `MVP 3` — расширение процессного контура и интеграций

### Цель

Сделать систему пригодной не только для аналитической подготовки отчёта, но и для организационного выпуска пакета через более зрелый процессный контур.

### Что входит

- углублённый процесс согласования
- enterprise workflow
- расширенные роли и governance
- электронная подпись
- внешние интеграции
- multi-regulator templates
- более богатая логика уведомлений и согласования

### Ключевые deliverables

- сквозной выпускной процесс
- интеграционный контур
- шаблоны под несколько регуляторных сценариев
- process governance поверх текущего review-контура

### Критерии завершения

- пользователь проходит не только сценарий “подготовить отчёт”, но и сценарий “согласовать и выпустить пакет”
- система поддерживает более одного прикладного регуляторного шаблона
- согласование и выпуск опираются на встроенный процессный контур, а не на внешние ручные действия

## 4.3. `MVP 4` — production / platform maturity

### Цель

Поднять систему с уровня дипломного и инженерного MVP до уровня эксплуатационного pilot-ready решения.

### Что входит

- security hardening
- CI/CD
- deployment profiles
- retention / backup
- более зрелый observability-контур
- stress `10x+`
- эксплуатационные runbooks

### Ключевые deliverables

- стабильный deployment-контур
- зрелый monitoring / alerting
- резервирование и recovery-процедуры
- нагрузочный профиль выше текущего базового уровня

### Критерии завершения

- система готова как pilot-ready deployment
- есть эксплуатационные сценарии и recovery-процедуры
- наблюдаемость и нагрузочная устойчивость формально подтверждены

## 4.4. `Post-MVP / исследовательский горизонт`

### Горизонт дальнейшего развития

- multimodal document understanding
- layout-aware vision pipeline
- domain fine-tuning
- thin mobile client / iOS
- масштабирование multi-tenant контура
- расширение на новые отрасли и регуляторов

## 5. Текущий приоритет реализации

Активный рабочий этап сейчас:

1. `MVP 2`
2. внутри `MVP 2` приоритет у `AI quality`
3. после этого переход к `MVP 3`

## 6. Принципы развития

- `MVP 1` больше не расширяется бесконечно: новые большие доработки относятся к новым версиям
- generated benchmark docs считаются источником истины по числам
- narrative docs должны только корректно интерпретировать эти артефакты
- web-first остаётся базовой стратегией
- iOS остаётся вне ближайшего критического пути

## 7. Канонические документы

- версионный roadmap: [docs/product-roadmap.md](docs/product-roadmap.md)
- фактический статус: [docs/roadmap-status.md](docs/roadmap-status.md)
- системный обзор: [docs/system-handbook.md](docs/system-handbook.md)
- архитектура: [docs/architecture.md](docs/architecture.md)
