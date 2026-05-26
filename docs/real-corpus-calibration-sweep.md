# Calibration Sweep Results

Дата фиксации: `2026-05-25`

## 1. Назначение документа

Документ фиксирует автоматический sweep по calibration-профилям для слоя
`evidence reranker + confidence thresholds` на текущем benchmark-suite.

- benchmark scenarios: `5`
- evaluated profiles: `4`
- baseline profile: `baseline_current`
- recommended profile: `baseline_current`

## 2. Сводная таблица профилей

| Профиль | Objective | Evidence precision | Evidence recall | Evidence F1 | Status accuracy | Section coverage | Delta vs baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| `baseline_current` | `0.8581` | `0.6765` | `1.0000` | `0.8070` | `100.00%` | `100.00%` | `+0.0000` |
| `strict_precision` | `0.8305` | `0.6970` | `1.0000` | `0.8214` | `83.33%` | `91.67%` | `-0.0276` |
| `balanced_focus` | `0.8356` | `0.6765` | `1.0000` | `0.8070` | `90.00%` | `95.00%` | `-0.0225` |
| `coverage_plus` | `0.8581` | `0.6765` | `1.0000` | `0.8070` | `100.00%` | `100.00%` | `+0.0000` |

## 3. Рекомендованный профиль

- profile: `baseline_current`
- objective_score: `0.8581`
- rationale: `Текущий production-профиль без дополнительных overrides.`

### Активные env overrides

- дополнительные overrides не требуются; рекомендован текущий baseline

## 4. Интерпретация

- Sweep не заменяет большой реальный корпус, но делает подбор порогов воспроизводимым.
- Профили оцениваются не по одной метрике, а по composite objective с упором на `evidence F1`, `precision`, `status accuracy` и `section coverage`.
- Следующий исследовательский шаг — прогон этого же контура на расширенном реальном benchmark-корпусе организаций.

