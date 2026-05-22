# Real Corpus Layer

Этот каталог содержит pilot-слой для будущего `real-world benchmark corpus`.

Назначение слоя:

- перейти от малого committed demo corpus к более реалистичным кейсам;
- хранить `redacted` и `real-like` кейсы отдельно от базовых demo samples;
- готовить будущий annotated corpus без смешивания с production-данными;
- воспроизводимо собирать benchmark-suite и calibration sweep по case-manifest'ам.

Важно:

- в репозиторий не включаются живые пользовательские документы;
- pilot-кейсы в этом каталоге являются `synthetic` или `redacted_real_like`;
- структура каталога рассчитана на последующее расширение реальными анонимизированными кейсами.

## Структура

- `schema/` — JSON schema для manifest-ов.
- `manifests/` — набор corpus-level manifest-ов.
- `cases/` — отдельные кейсы с документами и аннотациями.

## Минимальная модель case

Каждый кейс содержит:

- `documents/` — redacted/source-like документы;
- `annotations/quality_benchmark.json` — benchmark-аннотацию в формате текущего quality runner;
- `annotations/review-notes.md` — инженерные и методические заметки;
- `case-manifest.json` — краткое описание кейса, состава документов, статуса и ссылок на аннотации.

## Базовые команды

Валидация pilot корпуса:

```bash
./.venv/bin/python backend/scripts/validate_real_corpus.py
```

Прогон quality-suite по real corpus manifest:

```bash
./.venv/bin/python backend/scripts/generate_quality_benchmark_suite_report.py \
  --real-corpus-manifest samples/real_corpus/manifests/pilot-redacted.json
```

Calibration sweep по real corpus manifest:

```bash
./.venv/bin/python backend/scripts/run_calibration_sweep.py \
  --real-corpus-manifest samples/real_corpus/manifests/pilot-redacted.json
```
