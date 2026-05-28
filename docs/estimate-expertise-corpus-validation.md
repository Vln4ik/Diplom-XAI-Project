# Валидация корпуса проектно-сметной спецпроверки

Дата фиксации: `2026-05-28`

## 1. Сводка

- manifest: `estimate-expertise-pilot-synthetic`
- version: `2026-05-28`
- path: `samples/estimate_expertise_corpus/manifest.json`
- strict_real_corpus: `False`
- valid: `True`
- cases: `4`
- documents: `12`
- targets: `10`
- errors: `0`
- warnings: `1`

## 2. Targets по этапам

- `completeness`: `6`
- `filename_content`: `1`
- `quality_spell_signature`: `3`

## 3. Ошибки

- ошибок нет

## 4. Предупреждения

- `$.privacy`: privacy block is absent; acceptable for synthetic corpus only

## 5. Интерпретация

Этот отчет проверяет не качество AI-выводов, а готовность manifest к безопасному benchmark-прогону.
Для реальных проектно-сметных документов нужно запускать validator в режиме `--strict-real-corpus`
и хранить в репозитории только те данные, которые прошли обезличивание и publication review.
