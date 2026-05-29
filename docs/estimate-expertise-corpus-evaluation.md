# Benchmark проектно-сметного спецworkflow

Дата фиксации: `2026-05-29`

## 1. Сводка

- manifest: `estimate-expertise-pilot-synthetic`
- manifest_version: `2026-05-28`
- model_version: `estimate-expertise-local-terminology-baseline-v7`
- rule_version: `estimate-cost-pp145-rules-pack-v8`
- cases: `4`
- cases_passed: `4/4`
- targets_passed: `10/10`
- target_pass_rate: `1.0000`

## 2. Метрики по этапам

- `completeness`: `6/6` targets, pass_rate `1.0000`
- `filename_content`: `1/1` targets, pass_rate `1.0000`
- `quality_spell_signature`: `3/3` targets, pass_rate `1.0000`

## 3. Кейсы

### estimate_pack_missing_core_documents

- scenario: Неполный комплект: есть только заявление и проектная документация, нет ключевых сметных документов.
- documents: `2`
- case_passed: `True`
- findings_total: `16`
- findings_by_stage: `{'completeness': 14, 'quality_spell_signature': 2}`
- findings_by_severity: `{'danger': 4, 'info': 11, 'warning': 1}`

Targets:
- `completeness` / `Сводный сметный расчет` / `danger` / `present` -> `True`
- `completeness` / `Локальные сметные расчеты` / `danger` / `present` -> `True`
- `completeness` / `Ведомости объемов работ` / `danger` / `present` -> `True`

### estimate_pack_filename_content_mismatch

- scenario: Файл назван как ЛСР, но фактическое содержание относится к коммерческому предложению.
- documents: `3`
- case_passed: `True`
- findings_total: `18`
- findings_by_stage: `{'completeness': 14, 'filename_content': 1, 'quality_spell_signature': 3}`
- findings_by_severity: `{'danger': 4, 'info': 11, 'warning': 3}`

Targets:
- `filename_content` / `Название файла не совпадает` / `danger` / `present` -> `True`
- `quality_spell_signature` / `Найдены подозрительные орфографические ошибки` / `warning` / `present` -> `True`

### estimate_pack_scan_low_density

- scenario: PDF-скан с низкой плотностью текста и только текстовым признаком подписи.
- documents: `2`
- case_passed: `True`
- findings_total: `19`
- findings_by_stage: `{'completeness': 16, 'quality_spell_signature': 3}`
- findings_by_severity: `{'danger': 5, 'info': 10, 'warning': 4}`

Targets:
- `quality_spell_signature` / `Низкая плотность извлеченного текста` / `warning` / `present` -> `True`
- `quality_spell_signature` / `Текстовые признаки подписи или печати найдены` / `info` / `present` -> `True`

### estimate_pack_complete_baseline

- scenario: Базовый полный комплект без критичных missing findings по mandatory groups.
- documents: `5`
- case_passed: `True`
- findings_total: `16`
- findings_by_stage: `{'completeness': 13, 'quality_spell_signature': 3}`
- findings_by_severity: `{'danger': 1, 'info': 12, 'warning': 3}`

Targets:
- `completeness` / `Сводный сметный расчет` / `None` / `absent` -> `True`
- `completeness` / `Локальные сметные расчеты` / `None` / `absent` -> `True`
- `completeness` / `Ведомости объемов работ` / `None` / `absent` -> `True`

## 4. Интерпретация

Этот benchmark является synthetic pilot corpus для регрессионной проверки инженерной логики спецworkflow.
Он не заменяет расширенный обезличенный реальный корпус проектно-сметной документации.
Следующий шаг MVP 2/3 — добавить реальные обезличенные кейсы и проверить precision/recall по каждому stage.
