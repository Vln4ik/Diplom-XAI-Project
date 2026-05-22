# Calibration Sweep Results

Дата фиксации: `2026-05-22`

## 1. Назначение документа

Документ фиксирует автоматический sweep по calibration-профилям для слоя
`evidence reranker + confidence thresholds` на текущем benchmark-suite.

- benchmark scenarios: `3`
- evaluated profiles: `4`
- baseline profile: `baseline_current`
- recommended profile: `coverage_plus`

## 2. Сводная таблица профилей

| Профиль | Objective | Evidence precision | Evidence recall | Evidence F1 | Status accuracy | Section coverage | Delta vs baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| `baseline_current` | `0.6826` | `0.5714` | `0.6154` | `0.5926` | `69.44%` | `84.72%` | `+0.0000` |
| `strict_precision` | `0.7005` | `0.6154` | `0.6154` | `0.6154` | `69.44%` | `84.72%` | `+0.0179` |
| `balanced_focus` | `0.6826` | `0.5714` | `0.6154` | `0.5926` | `69.44%` | `84.72%` | `+0.0000` |
| `coverage_plus` | `0.7013` | `0.5714` | `0.6154` | `0.5926` | `77.78%` | `88.89%` | `+0.0187` |

## 3. Рекомендованный профиль

- profile: `coverage_plus`
- objective_score: `0.7013`
- rationale: `Профиль для более агрессивного добора structured evidence и чуть более низкого статуса partial/data_found.`

### Активные env overrides

- `XAI_APP_REQUIREMENT_DATA_FOUND_CONFIDENCE_THRESHOLD=0.52`
- `XAI_APP_EVIDENCE_BOOLEAN_PENALTY=0.12`
- `XAI_APP_EVIDENCE_STRUCTURED_ROW_HINT_BONUS=0.08`
- `XAI_APP_EVIDENCE_HINT_BONUS_UNIT=0.07`
- `XAI_APP_EVIDENCE_FOCUS_BONUS_UNIT=0.03`

## 4. Интерпретация

- Sweep не заменяет большой реальный корпус, но делает подбор порогов воспроизводимым.
- Профили оцениваются не по одной метрике, а по composite objective с упором на `evidence F1`, `precision`, `status accuracy` и `section coverage`.
- Следующий исследовательский шаг — прогон этого же контура на расширенном реальном benchmark-корпусе организаций.

