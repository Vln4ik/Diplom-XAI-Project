# Experimental Methodology

## 1. Назначение документа

Документ описывает методику экспериментальной оценки проекта `XAI Report Builder` в рамках дипломной работы.

Методика нужна для того, чтобы:

- формально объяснить, что именно мы сравниваем;
- отделить фактически измеренные данные от экспертных допущений;
- сделать эксперимент воспроизводимым;
- подготовить основу для раздела `Экспериментальная часть`.

## 2. Объект оценки

Оценивается `web-first MVP` платформы подготовки объяснимой отчётности по сценарию:

- регулятор: `Рособрнадзор`
- тип организации: образовательная организация
- корпус входных данных: committed demo corpus, включающий базовый текстовый пакет и OCR-augmented сценарии

Дополнительно в проекте теперь есть pilot `real_corpus` слой из `3` redacted/synthetic кейсов. Он используется не как основной regression-baseline, а как промежуточный уровень реалистичности между committed demo corpus и будущим большим real-world benchmark архивом.

## 3. Сравниваемые сценарии

В эксперименте сравниваются два сценария:

### 3.1. Ручной сценарий

Специалист:

- самостоятельно читает нормативные документы;
- вручную выделяет требования;
- вручную определяет применимость;
- вручную ищет evidence в разных документах;
- вручную собирает матрицу;
- вручную готовит черновик отчёта.

### 3.2. Автоматизированный сценарий

Специалист:

- загружает документы в систему;
- запускает обработку;
- создаёт отчёт и запускает анализ;
- просматривает требования, XAI и риски;
- выполняет ручной review спорных мест;
- генерирует и экспортирует итоговый пакет.

## 4. Типы данных в эксперименте

В экспериментальной части используются два типа данных:

### 4.1. Фактически измеренные данные

Это данные, которые получены из системы автоматически:

- время `process`
- время `analyze`
- время `generate`
- время export
- `2x` load profile
- formal quality benchmark
- extended quality benchmark suite
- calibration sweep по профилям reranker/confidence
- pilot real-corpus validation
- pilot real-corpus quality suite
- pilot real-corpus calibration sweep
- доля обработанных документов
- доля требований с evidence
- доля требований с XAI
- успешность export

Источники:

- [docs/performance-baseline.json](performance-baseline.json)
- [docs/load-baseline.json](load-baseline.json)
- [docs/quality-metrics.md](quality-metrics.md)

### 4.2. Экспертно-инженерные допущения

Это данные, которые пока не измерены на большом массиве реальных организаций, но необходимы для сравнения с ручным сценарием:

- диапазон времени ручной подготовки отчёта;
- диапазон времени ручного review в автоматизированном процессе;
- предварительная оценка прироста качества.

Источник:

- [docs/experiment-assumptions.json](experiment-assumptions.json)

## 5. Метрики эксперимента

### 5.1. Метрики времени

- общее время ручного сценария;
- общее время автоматизированного сценария;
- абсолютная экономия времени;
- относительное сокращение времени в процентах.

### 5.2. Proxy-метрики качества

- `documents_processed_share`
- `evidence_coverage`
- `xai_coverage`
- `export_success_rate`
- наличие дедупликации требований

### 5.3. Формальные quality-метрики текущего committed corpus

- `requirement extraction precision/recall/F1`
- `applicability accuracy`
- `evidence linking precision/recall/F1`
- `report sections source coverage`
- `status_accuracy_mean` по benchmark-suite

### 5.4. Предварительные качественные эффекты

- снижение риска пропуска требования;
- улучшение полноты evidence-покрытия;
- повышение воспроизводимости проверки.

## 6. Почему часть метрик качества всё ещё остаётся proxy-метриками

На текущем этапе у проекта уже есть формальные `precision / recall / F1` на committed benchmark corpus, но пока ещё нет:

- большого real-world gold dataset с экспертной разметкой;
- отдельного benchmark для semantic correctness generated report sections на реальном архиве кейсов;
- широкой экспертной межразметочной проверки по нескольким организациям.

Поэтому в эксперименте текущей итерации корректно использовать:

- formal benchmark-метрики на committed corpus;
- functional и coverage metrics;
- экспертно-инженерные интервальные оценки.

## 7. Воспроизводимость

Экспериментальная часть воспроизводится через:

```bash
./.venv/bin/python backend/scripts/generate_experimental_report.py
```

Качество committed corpus воспроизводится через:

```bash
./.venv/bin/python backend/scripts/generate_quality_benchmark_suite_report.py
./.venv/bin/python backend/scripts/run_calibration_sweep.py
```

Pilot `real_corpus` воспроизводится через:

```bash
./.venv/bin/python backend/scripts/validate_real_corpus.py
./.venv/bin/python backend/scripts/generate_quality_benchmark_suite_report.py --real-corpus-manifest samples/real_corpus/manifests/pilot-redacted.json --output-json docs/real-corpus-quality-suite-results.json --output-md docs/real-corpus-quality-suite-results.md
./.venv/bin/python backend/scripts/run_calibration_sweep.py --real-corpus-manifest samples/real_corpus/manifests/pilot-redacted.json --output-json docs/real-corpus-calibration-sweep.json --output-md docs/real-corpus-calibration-sweep.md
```

Скрипт читает:

- `docs/performance-baseline.json`
- `docs/load-baseline.json`
- `docs/experiment-assumptions.json`

и генерирует:

- `docs/experimental-results.json`
- `docs/experimental-results.md`

## 8. Ограничения методики

- сравнение построено на малом demo dataset;
- formal benchmark-часть уже расширена до OCR-augmented committed corpus, но не до большого реального архива кейсов;
- pilot `real_corpus` уже введён, но пока содержит только `3` кейса и не является широким статистически репрезентативным корпусом;
- часть временных и качественных оценок носит экспертный характер;
- результаты не следует интерпретировать как окончательно доказанные научные метрики точности;
- для строгой научной валидации нужен следующий этап с размеченным корпусом и экспертной проверкой.

## 9. Практический вывод

Несмотря на ограничения, текущая методика уже позволяет:

- формально показать измеримый выигрыш по времени;
- показать formal quality-метрики на committed benchmark corpus и calibration sweep на расширенном suite;
- показать покрытие evidence/XAI/export;
- связать инженерные baseline-данные с прикладным пользовательским эффектом;
- подготовить воспроизводимую основу для защиты и дальнейшего исследования.
