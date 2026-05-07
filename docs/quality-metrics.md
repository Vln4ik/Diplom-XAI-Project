# Quality Metrics

Дата фиксации: `2026-05-07`

## Метрики для demo/MVP

- `requirements_created`: число требований после анализа.
- `deduplicated_requirements`: отсутствие дублей по заголовкам в acceptance flow.
- `evidence_coverage`: доля требований с хотя бы одним evidence.
- `xai_coverage`: доля требований с explanation и заполненным `logic_json`.
- `export_success`: успешность генерации `DOCX/XLSX/ZIP/HTML`.
- `review_flow_success`: успешность переходов `submit -> approve/return-to-revision`.

## Текущие числовые значения на demo dataset

Ниже указаны фактические значения для текущего MVP на нашем demo-сценарии `Рособрнадзор + образовательная организация`.

### 1. Покрытие входного пакета

- `documents_total`: `4`
- `documents_processed_or_review`: `4/4` (`100%`)
- статус всех документов в baseline-сценарии: `processed`

### 2. Требования и дедупликация

- `requirements_total`: `3`
- `unique_requirement_titles`: `3`
- `deduplication_rate`: `1.0` (`100%` уникальных заголовков на demo dataset)

### 3. Evidence и XAI coverage

- `matrix_rows_total`: `3`
- `requirements_with_evidence`: `3/3` (`100%`)
- `evidence_coverage`: `1.0`
- `requirements_with_xai_logic`: `3/3` (`100%`)
- `xai_coverage`: `1.0`
- `requirements_with_recommended_action`: `3/3` (`100%`)

### 4. Итог отчёта

- `report_status_after_analyze`: `requires_review`
- `report_readiness_percent`: `100.0`
- `sections_total`: `9`

### 5. Экспорт

- `exports_ready`: `4/4` (`100%`)
- `export_success_rate`: `1.0`

Форматы:

- `DOCX`
- `XLSX`
- `ZIP`
- `HTML explanations`

## Числовые данные по времени

По текущему sequential performance baseline:

- `process_total`: `4.1443s`
- `analyze`: `1.0202s`
- `generate`: `7.1013s`

Если смотреть полный машинный контур `process + analyze + generate`, он составляет около:

- `12.27s` на demo dataset без учёта ручного review

Отдельно:

- `search`: `0.0532s`
- `export_docx`: `0.0363s`
- `export_matrix`: `0.0088s`
- `export_package`: `0.0282s`
- `export_explanations`: `0.0046s`

## Что это означает для пользователя

### Уже измеренный технический эффект

На demo dataset система:

- полностью обрабатывает `4` входных документа
- выделяет `3` требования
- строит `3` строки матрицы
- формирует `9` разделов отчёта
- создаёт `4` export-артефакта
- делает машинный цикл подготовки примерно за `12.27s`

### Оценка выигрыша по времени против ручного сценария

Для малого пакета документов ручной сценарий подготовки обычно занимает:

- от `2.5` до `6` часов

С учётом этого консервативная инженерная оценка выглядит так:

- сокращение времени первичной подготовки: `40-70%`
- сокращение времени повторных review-циклов: `25-50%`

Важно:

- это не formal field study
- это engineering estimate на основе текущего demo-сценария и baseline-замеров
- для строгой научной фиксации нужна отдельная экспериментальная методика на реальных кейсах

## Что можно и нельзя честно называть "точностью" сейчас

### Что уже можно измерять численно

Сейчас у нас уже есть proxy-метрики качества:

- покрытие evidence
- покрытие XAI
- отсутствие дублей на demo dataset
- успешность export
- готовность отчёта в сценарии

### Чего пока нет

У нас пока нет formal semantic accuracy метрик уровня:

- `precision`
- `recall`
- `F1`
- экспертной оценки correctness итогового отчёта на размеченном gold dataset

Поэтому корректная формулировка сейчас такая:

- у нас уже есть измеримый functional quality и coverage
- у нас ещё нет формально доказанной semantic accuracy на репрезентативной выборке

## Что планируется добавить дальше

Следующий слой quality-метрик:

- annotated benchmark для requirement extraction
- `precision/recall/F1`
- сравнение качества между fallback и local model runtime
- отдельная экспертная оценка корректности generated report sections

## Как измеряется сейчас

- Автоматически через `backend/tests/test_pipeline.py`.
- Автоматически через `backend/tests/test_acceptance_demo_flow.py`.
- Косвенно через `dashboard`, `notifications` и `audit log`.
- Отдельно через live benchmark: [docs/performance-baseline.md](/Users/vinchik/Desktop/Diplom/docs/performance-baseline.md).
- Отдельно через concurrency/load profile: [docs/load-baseline.md](/Users/vinchik/Desktop/Diplom/docs/load-baseline.md).

## Ограничения текущей фиксации

- Нет отдельного benchmark-набора с эталонной разметкой.
- Нет формальной метрики precision/recall для requirement extraction.
- Есть начальный local baseline для `PostgreSQL + Ollama`, включая `2x` concurrency, но нет профиля на больших данных и нет системных `CPU/RAM` замеров.
