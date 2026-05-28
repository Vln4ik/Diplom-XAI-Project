# Статус roadmap

## 1. Назначение документа

Этот документ фиксирует не желаемый, а фактический статус проекта по отношению к актуальному roadmap.

Канонический roadmap версий находится в [product-roadmap.md](product-roadmap.md).  
Здесь фиксируется:

- что завершено
- что частично готово
- что отложено
- какой этап сейчас активен

## 2. Сводка по версиям

| Версия | Статус | Смысл |
|---|---|---|
| `MVP 1` | `завершён` | функциональное ядро реализовано |
| `MVP 2` | `следующий активный этап` | следующий основной фокус — качество AI-контура |
| `MVP 3` | `запланирован` | процессный контур, интеграции, ЭП и governance |
| `MVP 4` | `запланирован` | production/platform maturity |
| `Post-MVP` | `исследовательский горизонт` | multimodal, fine-tuning, mobile branch |

## 3. Что реально закрыто в `MVP 1`

### 3.1. Продуктовый scope

В `MVP 1` уже реализованы:

- web-first пользовательский сценарий
- загрузка и обработка документов
- реестр требований
- матрица доказательств
- risks
- XAI explanations
- report generation
- export
- базовый контур review / approval

### 3.2. Инженерный scope

Реализованы:

- `FastAPI + SQLAlchemy + Alembic`
- `PostgreSQL + pgvector`
- `Celery + Redis`
- `React + TypeScript + Vite`
- локальный AI runtime через `Ollama`
- базовый OCR-контур через `Tesseract`
- базовый observability-контур на `Prometheus + Grafana + Alertmanager`

### 3.3. Scope валидации

В репозитории уже есть:

- backend tests
- acceptance demo-сценарий
- quality benchmark
- extended committed benchmark-suite
- pilot `real_corpus`
- calibration sweep
- performance / load / stress artifacts

## 4. Артефакты, подтверждающие статус `MVP 1`

### 4.1. Core benchmark layer

- gold benchmark: [quality-benchmark-results.md](quality-benchmark-results.md)
- committed suite: [quality-benchmark-suite-results.md](quality-benchmark-suite-results.md)
- calibration: [calibration-sweep-results.md](calibration-sweep-results.md)

### 4.2. Real corpus layer

- corpus status: [real-corpus-status.md](real-corpus-status.md)
- suite results: [real-corpus-quality-suite-results.md](real-corpus-quality-suite-results.md)
- target evaluation: [real-corpus-target-evaluation.md](real-corpus-target-evaluation.md)
- calibration: [real-corpus-calibration-sweep.md](real-corpus-calibration-sweep.md)

### 4.3. Performance and operations

- performance baseline: [performance-baseline.md](performance-baseline.md)
- load baseline: [load-baseline.md](load-baseline.md)
- stress baseline: [stress-baseline.md](stress-baseline.md)
- stress `4x`: [stress-4x-baseline.md](stress-4x-baseline.md)
- runtime comparison: [runtime-comparison-performance.md](runtime-comparison-performance.md)
- observability stack: [observability-stack.md](observability-stack.md)

## 5. Что ещё не входит в завершённый `MVP 1`

Это не блокеры статуса `MVP 1` как завершённой версии, а задачи следующих этапов.

### 5.1. AI quality gaps

- более широкий real-world benchmark corpus
- более богатая оценка качества sections
- более сильные embeddings / локальная LLM
- более зрелый OCR / vision-контур
- более сильная calibration-стратегия на широком корпусе

### 5.2. Workflow / enterprise gaps

- richer process governance
- электронная подпись
- внешние интеграции
- multi-regulator templates

### 5.3. Platform gaps

- CI/CD maturity
- security hardening
- retention / backup
- stress-профили выше текущего базового уровня
- more mature deployment profiles

## 6. Активный следующий этап: `MVP 2`

Текущий активный этап roadmap — `MVP 2`.

### Главная цель

Поднять качество AI-контура на более реалистичных данных.

### Что уже удалось зафиксировать на текущем подэтапе

- committed suite: `7` сценариев, `requirement extraction F1 = 1.0000`, `evidence linking precision = 0.9444`, `evidence linking F1 = 0.9714`
- pilot `real_corpus`: `5/5` кейсов и `20/20` quality targets
- pilot `real_corpus`: `requirement extraction F1 = 1.0000`, `status_accuracy_mean = 100.00%`, `source requirement coverage = 100.00%`, `section quality pass share = 100.00%`
- pilot `real_corpus`: `evidence linking precision = 1.0000`, `recall = 1.0000`, `F1 = 1.0000`
- реализован profile-aware локальный AI runtime: `baseline / quality / quality_plus`
- `/api/system/ai-status` теперь показывает активный профиль и `resolved_model` для embeddings и LLM
- launcher и Docker runtime умеют автоматически выбирать сильнейшую доступную локальную модель в рамках профиля

Это означает, что aggregate quality-контур `MVP 2` уже значительно усилился: статусы, section coverage и suite-level evidence linking больше не выглядят главным ограничением. Текущий самый жёсткий residual case сместился в строгий OCR-backed target evaluation, где `college_gamma_ocr_package` всё ещё даёт `evidence_f1 = 0.7742`.

### Ближайшие приоритеты

1. расширение `real_corpus`
2. улучшение OCR / vision-контура
3. усиление reranker / evidence linking с лучшей precision на multi-evidence кейсах
4. сравнительный benchmark профилей `quality` и `quality_plus` против `baseline`
5. воспроизводимая calibration-стратегия на большем корпусе
6. более глубокая semantic-оценка generated sections поверх текущего marker-based benchmark

## 7. Что запланировано на `MVP 3`

После стабилизации `MVP 2` следующий основной продуктовый слой:

- развитие процессного контура
- enterprise process governance
- внешние интеграции
- electronic signature
- multi-regulator templates

## 8. Что запланировано на `MVP 4`

После `MVP 3` основной фокус смещается в platform maturity:

- security
- deployment
- observability maturity
- stress `10x+`
- backup / recovery / retention

## 9. Что сознательно вынесено за ближайший горизонт

Вне ближайшего критического пути:

- thin iOS client
- большой multimodal-контур document understanding
- domain fine-tuning as separate research track
- масштабирование на новые отрасли без завершения текущего образовательного сценария

## 10. Текущий честный итог

Проект уже можно корректно описывать как:

- завершённый `MVP 1`
- с работающим продуктовым ядром
- с верифицируемым benchmark и acceptance-контуром
- с ясным следующим этапом `MVP 2`
