# Real Corpus Status

Дата фиксации: `2026-05-25`

## 1. Назначение документа

Документ фиксирует структуру и readiness pilot real-world corpus слоя,
который используется как мост между committed demo corpus и будущим
расширенным benchmark-корпусом на более реалистичных кейсах.

- manifest: `real-corpus-pilot-redacted`
- total cases: `5`
- benchmark-ready cases: `5`
- total issues: `0`

## 2. Сводные распределения

### Статусы кейсов

- `benchmark_ready`: `5`

### Уровни редактирования

- `redacted_real_like`: `3`
- `synthetic`: `2`

### Уровни сложности

- `high`: `2`
- `medium`: `3`

### Фокусы анализа

- `applicability`: `1`
- `evidence_linking`: `1`
- `gap_detection`: `1`
- `graduates_category`: `1`
- `mixed_positive_gap`: `1`
- `ocr_evidence`: `1`
- `registry_rows`: `1`
- `retrieval_recall`: `1`
- `risk_sections`: `1`
- `section_coverage`: `1`
- `section_generation`: `2`
- `status_accuracy`: `1`
- `structured_evidence`: `1`
- `structured_rows`: `1`

### Категории документов

- `data_table`: `3`
- `evidence`: `7`
- `normative`: `5`
- `other`: `5`

### Форматы документов

- `csv`: `3`
- `json`: `5`
- `pdf`: `1`
- `png`: `2`
- `txt`: `9`

## 3. Кейсы pilot корпуса

### college_alpha_full_package

- scenario: `Рособрнадзор + колледж + redacted full package`
- status: `benchmark_ready`
- report_type: `readiness_report`
- redaction_level: `synthetic`
- difficulty: `medium`
- documents: `4`
- benchmark_ready: `True`
- benchmark_path: `samples/real_corpus/cases/college_alpha_full_package/annotations/quality_benchmark.json`

Фокусы анализа:
- `evidence_linking`
- `section_generation`
- `structured_rows`

Целевые quality thresholds:
- `requirement_f1_min`: `0.9500`
- `status_accuracy_min`: `0.7000`
- `evidence_f1_min`: `0.6000`
- `section_coverage_min`: `0.8500`

### college_beta_gap_package

- scenario: `Рособрнадзор + колледж + redacted gap package`
- status: `benchmark_ready`
- report_type: `readiness_report`
- redaction_level: `redacted_real_like`
- difficulty: `medium`
- documents: `3`
- benchmark_ready: `True`
- benchmark_path: `samples/real_corpus/cases/college_beta_gap_package/annotations/quality_benchmark.json`

Фокусы анализа:
- `gap_detection`
- `applicability`
- `risk_sections`

Целевые quality thresholds:
- `requirement_f1_min`: `0.9500`
- `status_accuracy_min`: `0.9000`
- `evidence_f1_min`: `0.7500`
- `section_coverage_min`: `0.9500`

### college_gamma_ocr_package

- scenario: `Рособрнадзор + колледж + OCR-backed package`
- status: `benchmark_ready`
- report_type: `readiness_report`
- redaction_level: `synthetic`
- difficulty: `high`
- documents: `5`
- benchmark_ready: `True`
- benchmark_path: `samples/real_corpus/cases/college_gamma_ocr_package/annotations/quality_benchmark.json`

Фокусы анализа:
- `ocr_evidence`
- `retrieval_recall`
- `section_generation`

Целевые quality thresholds:
- `requirement_f1_min`: `0.9500`
- `status_accuracy_min`: `0.7000`
- `evidence_f1_min`: `0.3500`
- `section_coverage_min`: `0.6500`

### college_delta_structured_registry

- scenario: `Рособрнадзор + колледж + structured registry package`
- status: `benchmark_ready`
- report_type: `readiness_report`
- redaction_level: `redacted_real_like`
- difficulty: `medium`
- documents: `4`
- benchmark_ready: `True`
- benchmark_path: `samples/real_corpus/cases/college_delta_structured_registry/annotations/quality_benchmark.json`

Фокусы анализа:
- `structured_evidence`
- `registry_rows`
- `status_accuracy`

Целевые quality thresholds:
- `requirement_f1_min`: `0.9500`
- `status_accuracy_min`: `0.7500`
- `evidence_f1_min`: `0.6000`
- `section_coverage_min`: `0.8500`

### college_epsilon_graduate_registry

- scenario: `Рособрнадзор + колледж + graduate registry package`
- status: `benchmark_ready`
- report_type: `readiness_report`
- redaction_level: `redacted_real_like`
- difficulty: `high`
- documents: `4`
- benchmark_ready: `True`
- benchmark_path: `samples/real_corpus/cases/college_epsilon_graduate_registry/annotations/quality_benchmark.json`

Фокусы анализа:
- `graduates_category`
- `mixed_positive_gap`
- `section_coverage`

Целевые quality thresholds:
- `requirement_f1_min`: `0.9500`
- `status_accuracy_min`: `0.7000`
- `evidence_f1_min`: `0.5000`
- `section_coverage_min`: `0.8000`

