# OCR Benchmark Results

Дата фиксации: `2026-05-12`

- benchmark: `ocr_demo_benchmark`
- OCR provider: `tesseract`
- mode: `model`

## 1. Агрегированные метрики

- `case_total`: `5`
- `char_similarity_mean`: `0.9100`
- `token_precision_mean`: `0.9818`
- `token_recall_mean`: `0.9818`
- `token_f1_mean`: `0.9818`
- `keyword_coverage_mean`: `1.0000`
- `requires_review_rate`: `0.00%`

## 2. По форматам

### image

- `case_total`: `3`
- `char_similarity_mean`: `0.9584`
- `token_f1_mean`: `0.9697`
- `keyword_coverage_mean`: `1.0000`
- `requires_review_rate`: `0.00%`

### pdf

- `case_total`: `2`
- `char_similarity_mean`: `0.8375`
- `token_f1_mean`: `1.0000`
- `keyword_coverage_mean`: `1.0000`
- `requires_review_rate`: `0.00%`

## 3. По сценариям

### ocr-clean-image

- scenario: `clean_image`
- file: `clean_notice.png`
- format: `image`
- `requires_review`: `False`
- `char_similarity`: `0.9727`
- `token_f1`: `1.0000`
- `keyword_coverage`: `1.0000`

### ocr-noisy-image

- scenario: `noisy_image`
- file: `noisy_notice.png`
- format: `image`
- `requires_review`: `False`
- `char_similarity`: `0.9704`
- `token_f1`: `1.0000`
- `keyword_coverage`: `1.0000`

### ocr-table-image

- scenario: `table_like_image`
- file: `table_scan.png`
- format: `image`
- `requires_review`: `False`
- `char_similarity`: `0.9320`
- `token_f1`: `0.9091`
- `keyword_coverage`: `1.0000`

### ocr-image-pdf

- scenario: `image_only_pdf`
- file: `site_scan.pdf`
- format: `pdf`
- `requires_review`: `False`
- `char_similarity`: `0.9799`
- `token_f1`: `1.0000`
- `keyword_coverage`: `1.0000`

### ocr-mixed-layout-pdf

- scenario: `mixed_layout_pdf`
- file: `mixed_layout_scan.pdf`
- format: `pdf`
- `requires_review`: `False`
- `char_similarity`: `0.6951`
- `token_f1`: `1.0000`
- `keyword_coverage`: `1.0000`

