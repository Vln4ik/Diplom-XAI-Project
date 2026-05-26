# Метрики качества

Дата актуализации: `2026-05-26`

## 1. Назначение документа

Документ собирает в одном месте качественные метрики проекта и объясняет, как их интерпретировать на текущем этапе.

Он разделяет:

- функциональное покрытие `MVP 1`
- формальные benchmark-метрики
- pilot `real_corpus`
- OCR-метрики
- ограничения текущей доказательной базы

## 2. Что уже подтверждает качество `MVP 1`

### 2.1. Функциональное покрытие на demo-сценарии

На demo-сценарии система уже подтверждает:

- обработку входного пакета
- наличие требований
- наличие evidence
- наличие XAI
- успешность export
- наличие sections и review-контура

Ключевой смысл этих метрик:

- продукт закрывает основной функциональный контур
- результат не ограничивается только генерацией текста

## 3. Формальный quality benchmark

### 3.1. Базовый gold benchmark

Для сценария `Рособрнадзор + образовательная организация` зафиксировано:

- `requirement extraction precision`: `1.0000`
- `requirement extraction recall`: `1.0000`
- `requirement extraction F1`: `1.0000`
- `applicability accuracy`: `1.0000`
- `evidence linking precision`: `0.8571`
- `evidence linking recall`: `1.0000`
- `evidence linking F1`: `0.9231`
- `report sections source coverage`: `1.0000`
- `report sections quality_score_mean`: `100.00%`

Источник: [quality-benchmark-results.md](quality-benchmark-results.md)

### 3.2. Расширенный committed benchmark-suite

Для `7` committed сценариев:

- `requirement extraction precision`: `1.0000`
- `requirement extraction recall`: `1.0000`
- `requirement extraction F1`: `1.0000`
- `status_accuracy_mean`: `100.00%`
- `applicability accuracy mean`: `100.00%`
- `evidence linking precision`: `0.8293`
- `evidence linking recall`: `1.0000`
- `evidence linking F1`: `0.9067`
- `report sections source coverage mean`: `100.00%`
- `report sections requirement_content_coverage_mean`: `100.00%`
- `report sections quality_score_mean`: `100.00%`
- `report sections quality_pass_share_mean`: `100.00%`

Источник: [quality-benchmark-suite-results.md](quality-benchmark-suite-results.md)

### 3.3. Как это интерпретировать

Из committed suite уже можно сделать честные выводы:

- extraction layer стабилен
- applicability на committed corpus закрывается уверенно
- section coverage и marker-based section quality не являются слабым местом на committed контуре
- основной оставшийся challenge — точность evidence linking на более сложных и реалистичных кейсах

## 4. Calibration-слой

### 4.1. Committed suite calibration

На committed `7`-сценарном suite автоматический sweep показал:

- `recommended profile`: `baseline_current`
- `objective_score`: `0.8409`

Это означает:

- текущий production-baseline остаётся лучшим компромиссом между evidence precision, статусами и coverage на committed suite

Источник: [calibration-sweep-results.md](calibration-sweep-results.md)

### 4.2. Почему это не финальный вывод для продукта

Это ещё не означает, что calibration можно считать окончательно закрытой.

Причина:

- и committed suite, и pilot `real_corpus` сейчас сходятся на `baseline_current`
- но evidence precision на committed contour всё ещё заметно ниже идеального уровня
- следовательно, следующий шаг — не искать новый набор порогов ради локального выигрыша, а расширять корпус и улучшать сам evidence linking

## 5. Pilot `real_corpus`

## 5.1. Структура слоя

Сейчас pilot `real_corpus` включает:

- `5` кейсов, готовых к benchmark-проверке
- `3` redacted real-like кейса
- `2` synthetic кейса
- `0` readiness issues

Источники:

- [real-corpus-status.md](real-corpus-status.md)
- [real-corpus-target-evaluation.md](real-corpus-target-evaluation.md)

## 5.2. Aggregate quality на pilot `real_corpus`

Текущие агрегированные показатели:

- `requirement extraction precision`: `1.0000`
- `requirement extraction recall`: `1.0000`
- `requirement extraction F1`: `1.0000`
- `status_accuracy_mean`: `100.00%`
- `applicability accuracy mean`: `100.00%`
- `evidence linking precision`: `0.7500`
- `evidence linking recall`: `0.9565`
- `evidence linking F1`: `0.8408`
- `report sections source coverage mean`: `100.00%`
- `min source requirement pass share mean`: `100.00%`
- `report sections requirement_content_coverage_mean`: `100.00%`
- `report sections quality_score_mean`: `100.00%`
- `report sections quality_pass_share_mean`: `100.00%`

Источник: [real-corpus-quality-suite-results.md](real-corpus-quality-suite-results.md)

## 5.3. Проверка целевых критериев

На текущем пилотном `real_corpus`:

- `cases_passed`: `5/5`
- `targets_passed`: `20/20`

Источник: [real-corpus-target-evaluation.md](real-corpus-target-evaluation.md)

## 5.4. Real-corpus calibration

На pilot `real_corpus` sweep показал:

- `recommended profile`: `baseline_current`
- дополнительные overrides не требуются как устойчивый default на текущем pilot-корпусе

Источник: [real-corpus-calibration-sweep.md](real-corpus-calibration-sweep.md)

## 5.5. Что это означает

Это один из самых важных выводов текущей итерации:

- committed suite и pilot `real_corpus` сейчас сходятся на `baseline_current`
- но это согласие не означает, что evidence linking уже полностью оптимален

Следовательно, основной следующий шаг `MVP 2` — расширять real corpus и улучшать сам механизм evidence linking, а не надеяться закрыть задачу только подбором порогов.

Дополнительный важный вывод после стабилизации section-quality benchmark:

- marker-based проверка sections уже встроена и стабильна и на committed suite, и на текущем pilot `real_corpus`
- слабый `structured-registry` кейс больше не проваливает section coverage и section-quality на текущем pilot-корпусе
- `status_accuracy` и `section coverage` уже удерживаются на `100.00%` и на committed suite, и на pilot `real_corpus`
- основной residual gap сместился в evidence precision и дальнейшую проверку на более широком real-world корпусе

## 6. OCR metrics

Для OCR benchmark уже подтверждено:

- `char_similarity_mean`: `0.9100`
- `token_precision_mean`: `0.9818`
- `token_recall_mean`: `0.9818`
- `token_f1_mean`: `0.9818`
- `keyword_coverage_mean`: `1.0000`

Источник: [ocr-benchmark-results.md](ocr-benchmark-results.md)

Практический смысл:

- базовый OCR-контур уже рабочий
- но layout-aware vision layer ещё не реализован как завершённый контур

## 7. Нагрузочные и runtime-артефакты

Качество продукта сейчас нельзя отделять от его runtime-поведения.  
Поэтому quality-контур дополняется следующими артефактами:

- [performance-baseline.md](performance-baseline.md)
- [load-baseline.md](load-baseline.md)
- [stress-baseline.md](stress-baseline.md)
- [stress-4x-baseline.md](stress-4x-baseline.md)
- [runtime-comparison-performance.md](runtime-comparison-performance.md)

Это важно для `MVP 4`, но уже полезно как инженерный контур `MVP 1`.

## 8. Чего пока нет

Пока не хватает:

- большого размеченного real-world gold corpus
- более глубокой semantic quality оценки generated sections поверх текущего marker-based benchmark
- широкой экспертной межразметочной проверки
- production-grade long-horizon quality tracking

## 9. Что является задачей `MVP 2`

По метрикам следующий главный шаг уже очевиден:

- расширить `real_corpus`
- усилить OCR / vision contour
- улучшить evidence reranking
- удержать coverage без деградации evidence precision на более широком корпусе
- довести calibration на более реалистичном корпусе

## 10. Короткий итог

`MVP 1` уже имеет измеримый quality-контур.  
Следующий этап проекта — не “впервые добавить метрики”, а усилить существующий benchmark-фундамент до уровня `MVP 2`.
