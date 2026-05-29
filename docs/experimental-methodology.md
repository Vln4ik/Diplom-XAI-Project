# Экспериментальная методология

Дата актуализации: `2026-05-29`

## 1. Назначение документа

Документ описывает, как экспериментальная часть проекта соотносится с текущим продуктовым статусом.

На текущем этапе:

- `MVP 1` завершён
- экспериментальная часть уже опирается не только на demo-сценарий, но и на benchmark-слой с `real_corpus`
- отдельный synthetic benchmark проверяет проектно-сметный спецworkflow государственной экспертизы

## 2. Что именно оценивается

Оценивается завершённый `MVP 1` платформы по сценарию:

- регулятор: `Рособрнадзор`
- тип организации: образовательная организация

Экспериментальная база сейчас состоит из четырёх уровней:

1. demo-сценарий
2. committed benchmark corpus
3. пилотный `real_corpus`
4. synthetic corpus для спецworkflow государственной экспертизы

## 3. Какие сценарии сравниваются

### 3.1. Ручной сценарий

Специалист:

- читает нормативную базу вручную
- выделяет требования вручную
- ищет доказательства вручную
- собирает матрицу вручную
- формирует черновик отчёта вручную

### 3.2. Автоматизированный сценарий

Специалист:

- загружает документы
- запускает обработку и анализ
- проверяет требования, доказательства, XAI и риски
- выполняет ручную проверку спорных мест
- генерирует и экспортирует итоговый пакет

## 4. Какие типы данных используются

### 4.1. Фактически измеренные данные

К фактически измеренным данным относятся:

- performance baseline
- load baseline
- stress-артефакты
- gold benchmark
- committed benchmark-suite
- calibration sweep
- OCR benchmark
- pilot `real_corpus`
- estimate expertise synthetic benchmark
- проверка целевых критериев для `real_corpus`

### 4.2. Экспертно-инженерные допущения

К допущениям относятся:

- диапазоны времени ручного процесса
- интервальные оценки выигрыша по времени
- интервальные оценки потенциального прироста качества

## 5. Как устроена текущая доказательная база

## 5.1. Demo-слой

Demo-слой показывает:

- рабочий пользовательский сценарий
- функциональное покрытие
- export / XAI / review-контур

## 5.2. Committed benchmark-слой

Committed benchmark-слой показывает:

- формальные quality-метрики на фиксированном корпусе
- воспроизводимость benchmark-замеров
- устойчивость committed scenario pack

## 5.3. Pilot `real_corpus`

Пилотный `real_corpus` показывает:

- поведение системы на более реалистичных кейсах
- где synthetic-базовый контур уже недостаточен
- как calibration ведёт себя на усложнённом корпусе

## 5.4. State expertise synthetic layer

Synthetic слой государственной экспертизы показывает:

- регрессионную проверку stage findings;
- работу `filename_content`, `completeness`, `quality_spell_signature`;
- прохождение `4/4` cases и `10/10` targets;
- необходимость следующего шага: real anonymized corpus с precision/recall по stages.

## 6. Основные группы метрик

### 6.1. Метрики времени

- время ручного процесса
- время автоматизированного процесса
- экономия времени
- latency отдельных этапов pipeline

### 6.2. Метрики функционального покрытия

- documents processed share
- evidence coverage
- XAI coverage
- export success rate

### 6.3. Формальные quality-метрики

- requirement extraction precision / recall / F1
- applicability accuracy
- evidence linking precision / recall / F1
- status accuracy
- section source coverage

### 6.4. Метрики `real_corpus`

- case readiness
- target pass rate
- aggregate quality on realistic pilot corpus

## 7. Что уже можно честно утверждать

По текущей итерации уже корректно утверждать:

- `MVP 1` имеет формальный контур quality-метрик
- committed benchmark-метрики воспроизводимы
- pilot `real_corpus` уже существует и закрывает `20/20` целевых критериев
- базовый OCR-контур измерен отдельно

## 8. Что пока нельзя считать полностью доказанным

Пока ещё нельзя считать полностью закрытыми следующие исследовательские вопросы:

- semantic quality generated sections на большом реальном корпусе
- окончательная calibration strategy на real-world data
- generalization на существенно более широкий архив кейсов

Именно это и составляет основу `MVP 2`.

## 9. Как воспроизводится эксперимент

### 9.1. Базовый экспериментальный отчёт

```bash
./.venv/bin/python backend/scripts/generate_experimental_report.py
```

### 9.2. Committed benchmark-слой

```bash
./.venv/bin/python backend/scripts/generate_quality_benchmark_report.py
./.venv/bin/python backend/scripts/generate_quality_benchmark_suite_report.py --suite-manifest samples/benchmark_suites/extended.json
./.venv/bin/python backend/scripts/run_calibration_sweep.py --suite-manifest samples/benchmark_suites/extended.json
```

### 9.3. Пилотный `real_corpus`

```bash
./.venv/bin/python backend/scripts/validate_real_corpus.py
./.venv/bin/python backend/scripts/generate_quality_benchmark_suite_report.py --real-corpus-manifest samples/real_corpus/manifests/pilot-redacted.json --output-json docs/real-corpus-quality-suite-results.json --output-md docs/real-corpus-quality-suite-results.md
./.venv/bin/python backend/scripts/evaluate_real_corpus_targets.py
./.venv/bin/python backend/scripts/run_calibration_sweep.py --real-corpus-manifest samples/real_corpus/manifests/pilot-redacted.json --output-json docs/real-corpus-calibration-sweep.json --output-md docs/real-corpus-calibration-sweep.md
```

## 10. Ограничения текущей методики

- сравнение ручного и автоматизированного времени всё ещё частично опирается на экспертные интервалы
- benchmark-часть уже сильнее demo, но ещё не равна большому реальному архиву кейсов
- pilot `real_corpus` полезен как мост, но не является окончательной широкой выборкой

## 11. Как это связано с roadmap

### `MVP 1`

Дал:

- воспроизводимый functional contour
- формальный benchmark-слой
- пилотный `real_corpus`

### `MVP 2`

Должен дать:

- более широкий `real_corpus`
- более сильную OCR / vision-оценку
- benchmark качества разделов
- более зрелую calibration-стратегию

## 12. Короткий итог

Экспериментальная методика уже достаточна для защиты завершённого `MVP 1`,  
но следующий исследовательский рост проекта напрямую связан с задачами `MVP 2`.
