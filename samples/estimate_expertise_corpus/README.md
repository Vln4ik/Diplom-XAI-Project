# Корпус проектно-сметных кейсов для спецworkflow

Этот каталог содержит pilot-корпус для проверки workflow:

`Отчет государственной экспертизы в части проверки достоверности определения сметной стоимости`.

## Текущее состояние

- `manifest.json` — synthetic pilot corpus.
- `real-corpus-template.json` — шаблон для подключения обезличенных реальных проектно-сметных кейсов.
- Он нужен для регрессионной проверки инженерной логики.
- Он не заменяет реальные обезличенные проектно-сметные документы.

## Валидация manifest

Перед benchmark-прогоном нужно проверить структуру manifest:

```bash
./.venv/bin/python backend/scripts/validate_estimate_expertise_manifest.py
```

Для реального обезличенного корпуса использовать строгий режим:

```bash
./.venv/bin/python backend/scripts/validate_estimate_expertise_manifest.py \
  samples/estimate_expertise_corpus/real-corpus-template.json \
  --strict-real-corpus
```

Validator проверяет:

- обязательные поля manifest, case, document и target;
- допустимые `stage_key` и `severity`;
- дубли `case_id` и `relative_path`;
- наличие обезличенного `text`-экстракта;
- privacy-блок для real-corpus слоя;
- запрет публикации неанонимизированных данных в репозитории.

Generated status:

- `docs/estimate-expertise-corpus-validation.json`;
- `docs/estimate-expertise-corpus-validation.md`.

## Как добавлять реальные кейсы

1. Создать отдельную папку кейса, например `real_cases/case_001/`.
2. Положить туда обезличенные документы.
3. Удалить персональные данные, коммерческие тайны, подписи физических лиц, номера договоров, адреса, телефоны и реквизиты, если нет разрешения на использование.
4. Добавить описание кейса в отдельный manifest.
5. Для каждого ожидаемого вывода указать target:
   - `stage_key`;
   - `title_contains`;
   - `severity`;
   - `expected_absent`, если finding не должен появиться.

## Минимальный target

```json
{
  "stage_key": "completeness",
  "title_contains": "Сводный сметный расчет",
  "severity": "danger"
}
```

## Ограничения

- Реальный корпус должен быть юридически допустимым для хранения в репозитории.
- Если документы нельзя публиковать, manifest должен ссылаться на локальный закрытый путь, который не коммитится.
- Для дипломной демонстрации достаточно synthetic corpus, но для product/pilot нужен real-corpus слой.
