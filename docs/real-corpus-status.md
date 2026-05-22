# Real Corpus Status

Дата фиксации: `2026-05-22`

## 1. Назначение документа

Документ фиксирует структуру и readiness pilot real-world corpus слоя,
который используется как мост между committed demo corpus и будущим
расширенным benchmark-корпусом на более реалистичных кейсах.

- manifest: `real-corpus-pilot-redacted`
- total cases: `3`
- benchmark-ready cases: `3`
- total issues: `0`

## 2. Сводные распределения

### Статусы кейсов

- `benchmark_ready`: `3`

### Уровни редактирования

- `redacted_real_like`: `1`
- `synthetic`: `2`

### Категории документов

- `data_table`: `1`
- `evidence`: `5`
- `normative`: `3`
- `other`: `3`

### Форматы документов

- `csv`: `1`
- `json`: `3`
- `pdf`: `1`
- `png`: `2`
- `txt`: `5`

## 3. Кейсы pilot корпуса

### college_alpha_full_package

- scenario: `Рособрнадзор + колледж + redacted full package`
- status: `benchmark_ready`
- report_type: `readiness_report`
- redaction_level: `synthetic`
- documents: `4`
- benchmark_ready: `True`
- benchmark_path: `samples/real_corpus/cases/college_alpha_full_package/annotations/quality_benchmark.json`

### college_beta_gap_package

- scenario: `Рособрнадзор + колледж + redacted gap package`
- status: `benchmark_ready`
- report_type: `readiness_report`
- redaction_level: `redacted_real_like`
- documents: `3`
- benchmark_ready: `True`
- benchmark_path: `samples/real_corpus/cases/college_beta_gap_package/annotations/quality_benchmark.json`

### college_gamma_ocr_package

- scenario: `Рособрнадзор + колледж + OCR-backed package`
- status: `benchmark_ready`
- report_type: `readiness_report`
- redaction_level: `synthetic`
- documents: `5`
- benchmark_ready: `True`
- benchmark_path: `samples/real_corpus/cases/college_gamma_ocr_package/annotations/quality_benchmark.json`

