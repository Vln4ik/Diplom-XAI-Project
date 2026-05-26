# Чек-лист приёмки

Дата актуализации: `2026-05-24`

## 1. Цель документа

Документ фиксирует:

- что считается закрытым для `MVP 1`
- какими артефактами это подтверждается
- что не входит в приёмку `MVP 1`
- что станет фокусом приёмки `MVP 2`

## 2. Приёмка для `MVP 1`

### 2.1. Базовые проверки

```bash
./.venv/bin/pytest -q backend/tests
cd frontend && npm run build
```

### 2.2. Матрица приёмки

| Критерий | Как подтверждается | Артефакт |
|---|---|---|
| Пользователь работает в контексте организации | auth + organization scope | `backend/tests/test_auth.py` |
| Документы загружаются и обрабатываются | upload + processing + search | `backend/tests/test_pipeline.py` |
| Система создаёт требования и evidence matrix | analyze report | `backend/tests/test_pipeline.py` |
| Для требований есть XAI-цепочка | explanation endpoint + evidence payload | `backend/tests/test_pipeline.py` |
| Отчёт генерируется и версионируется | generate + report versions | `backend/tests/test_pipeline.py` |
| Риски, уведомления и аудит работают | risk / approval / notification flow | `backend/tests/test_pipeline.py` |
| Экспорт работает | `DOCX/XLSX/ZIP/HTML` files | `backend/tests/test_pipeline.py` |
| Web-сценарий можно показать без Swagger | страницы frontend и demo-сценарий | `docs/demo-scenario.md` |

### 2.3. Что считается закрытым

`MVP 1` считается закрытым, если:

- основной demo-сценарий проходит
- backend tests зелёные
- frontend build проходит
- для исходных требований отчёта доступны explanation и evidence

## 3. Что не входит в приёмку `MVP 1`

- большой real-world benchmark corpus
- продвинутый vision-конвейер
- внешние интеграции
- электронная подпись
- iOS client
- production-grade security / load contour

## 4. Что станет фокусом приёмки `MVP 2`

`MVP 2` должен закрывать приёмку не по новому UI-сценарию, а по качеству AI-контура.

Ключевые цели приёмки `MVP 2`:

- расширенный `real_corpus`
- более сильное OCR / vision-поведение
- более сильный evidence linking
- benchmark качества разделов
- calibration на более широком корпусе

## 5. Артефакты приёмки `MVP 2`

Ожидаемые артефакты:

- расширенный manifest `real_corpus`
- обновлённая проверка целевых критериев
- обновлённый OCR-benchmark
- артефакты benchmark-проверки качества разделов
- обновлённые calibration-отчёты

## 6. Короткий итог

Приёмка `MVP 1` уже относится к завершённой поставке.  
Приёмка `MVP 2` должна сместиться с вопроса “есть ли функция” на вопрос “каково качество аналитического контура”.
