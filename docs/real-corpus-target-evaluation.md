# Real Corpus Target Evaluation

Дата фиксации: `2026-05-28`

## 1. Сводка

- manifest: `real-corpus-pilot-redacted`
- cases: `5`
- cases_passed: `5`
- targets_passed: `20/20`

## 2. Кейсы

### college_alpha_full_package

- scenario: `Рособрнадзор + колледж + redacted full package`
- difficulty: `medium`
- case_passed: `True`
- requirement_f1: `1.0000`
- status_accuracy: `1.0000`
- evidence_f1: `1.0000`
- section_coverage: `1.0000`

Фокусы анализа:
- `evidence_linking`
- `section_generation`
- `structured_rows`

Сравнение с quality targets:
- `requirement_f1_min`: actual `1.0000` vs target `0.9500` -> `True`
- `status_accuracy_min`: actual `1.0000` vs target `0.7000` -> `True`
- `evidence_f1_min`: actual `1.0000` vs target `0.6000` -> `True`
- `section_coverage_min`: actual `1.0000` vs target `0.8500` -> `True`

### college_beta_gap_package

- scenario: `Рособрнадзор + колледж + redacted gap package`
- difficulty: `medium`
- case_passed: `True`
- requirement_f1: `1.0000`
- status_accuracy: `1.0000`
- evidence_f1: `1.0000`
- section_coverage: `1.0000`

Фокусы анализа:
- `gap_detection`
- `applicability`
- `risk_sections`

Сравнение с quality targets:
- `requirement_f1_min`: actual `1.0000` vs target `0.9500` -> `True`
- `status_accuracy_min`: actual `1.0000` vs target `0.9000` -> `True`
- `evidence_f1_min`: actual `1.0000` vs target `0.7500` -> `True`
- `section_coverage_min`: actual `1.0000` vs target `0.9500` -> `True`

### college_gamma_ocr_package

- scenario: `Рособрнадзор + колледж + OCR-backed package`
- difficulty: `high`
- case_passed: `True`
- requirement_f1: `1.0000`
- status_accuracy: `1.0000`
- evidence_f1: `0.7742`
- section_coverage: `1.0000`

Фокусы анализа:
- `ocr_evidence`
- `retrieval_recall`
- `section_generation`

Сравнение с quality targets:
- `requirement_f1_min`: actual `1.0000` vs target `0.9500` -> `True`
- `status_accuracy_min`: actual `1.0000` vs target `0.7000` -> `True`
- `evidence_f1_min`: actual `0.7742` vs target `0.3500` -> `True`
- `section_coverage_min`: actual `1.0000` vs target `0.6500` -> `True`

### college_delta_structured_registry

- scenario: `Рособрнадзор + колледж + structured registry package`
- difficulty: `medium`
- case_passed: `True`
- requirement_f1: `1.0000`
- status_accuracy: `1.0000`
- evidence_f1: `1.0000`
- section_coverage: `1.0000`

Фокусы анализа:
- `structured_evidence`
- `registry_rows`
- `status_accuracy`

Сравнение с quality targets:
- `requirement_f1_min`: actual `1.0000` vs target `0.9500` -> `True`
- `status_accuracy_min`: actual `1.0000` vs target `0.7500` -> `True`
- `evidence_f1_min`: actual `1.0000` vs target `0.6000` -> `True`
- `section_coverage_min`: actual `1.0000` vs target `0.8500` -> `True`

### college_epsilon_graduate_registry

- scenario: `Рособрнадзор + колледж + graduate registry package`
- difficulty: `high`
- case_passed: `True`
- requirement_f1: `1.0000`
- status_accuracy: `1.0000`
- evidence_f1: `1.0000`
- section_coverage: `1.0000`

Фокусы анализа:
- `graduates_category`
- `mixed_positive_gap`
- `section_coverage`

Сравнение с quality targets:
- `requirement_f1_min`: actual `1.0000` vs target `0.9500` -> `True`
- `status_accuracy_min`: actual `1.0000` vs target `0.7000` -> `True`
- `evidence_f1_min`: actual `1.0000` vs target `0.5000` -> `True`
- `section_coverage_min`: actual `1.0000` vs target `0.8000` -> `True`

