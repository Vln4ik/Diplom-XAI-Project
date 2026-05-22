# Quality Benchmark Suite Results

Дата фиксации: `2026-05-22`

- сценариев в suite: `3`

## 1. Агрегированные метрики

### Requirement extraction

- `precision`: `1.0000`
- `recall`: `1.0000`
- `f1`: `1.0000`
- `category_accuracy_mean`: `100.00%`
- `status_accuracy_mean`: `69.44%`

### Applicability

- `accuracy_mean`: `100.00%`

### Evidence linking

- `precision`: `0.5714`
- `recall`: `0.6154`
- `f1`: `0.5926`
- `grounded_requirements_share_mean`: `61.11%`

### Report sections

- `presence_rate_mean`: `100.00%`
- `non_empty_content_share_mean`: `100.00%`
- `source_requirement_coverage_mean`: `84.72%`
- `min_source_requirement_pass_share_mean`: `77.78%`

## 2. Результаты по сценариям

### real_corpus_college_alpha_full_package

- scenario: `Рособрнадзор + колледж + redacted full package`
- extraction F1: `1.0000`
- applicability accuracy: `100.00%`
- evidence F1: `0.6250`
- evidence precision: `0.5000`
- evidence recall: `0.8333`
- section coverage: `87.50%`

### real_corpus_college_beta_gap_package

- scenario: `Рособрнадзор + колледж + redacted gap package`
- extraction F1: `1.0000`
- applicability accuracy: `100.00%`
- evidence F1: `0.8000`
- evidence precision: `0.6667`
- evidence recall: `1.0000`
- section coverage: `100.00%`

### real_corpus_college_gamma_ocr_package

- scenario: `Рособрнадзор + колледж + OCR-backed package`
- extraction F1: `1.0000`
- applicability accuracy: `100.00%`
- evidence F1: `0.3333`
- evidence precision: `1.0000`
- evidence recall: `0.2000`
- section coverage: `66.67%`

