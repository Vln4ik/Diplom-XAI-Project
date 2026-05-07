# Acceptance Checklist

Дата актуализации: `2026-05-06`

## Цель

Этот документ фиксирует, как проверяется `web-first MVP` по сценарию `Рособрнадзор + образовательная организация`.

## Команды проверки

```bash
./.venv/bin/pytest -q backend/tests
cd frontend && npm run build
```

## Acceptance Matrix

| Критерий | Как проверяется | Артефакт |
| --- | --- | --- |
| Пользователь входит в систему и работает в контексте организации | API auth flow, создание организации и выбор организации в UI | `backend/tests/test_auth.py`, `frontend/src/pages/LoginPage.tsx` |
| Документы загружаются и обрабатываются | Upload + process + search по фрагментам | `backend/tests/test_pipeline.py`, `backend/tests/test_acceptance_demo_flow.py` |
| Система формирует требования и матрицу доказательств | Analyze report + matrix | `backend/tests/test_pipeline.py`, `backend/tests/test_acceptance_demo_flow.py` |
| Для требования доступна XAI-цепочка | `GET /requirements/{id}/explanation` и наличие evidence | `backend/tests/test_pipeline.py`, `backend/tests/test_acceptance_demo_flow.py` |
| Отчет генерируется и версионируется | Generate report + versions + restore | `backend/tests/test_pipeline.py` |
| Риски, уведомления и аудит работают | Assignment, resolve, submit, approve, read notifications | `backend/tests/test_pipeline.py` |
| Экспорт `DOCX/XLSX/ZIP/HTML` доступен | Проверка файлов на диске после export API | `backend/tests/test_pipeline.py`, `backend/tests/test_acceptance_demo_flow.py` |
| Сквозной web MVP можно показать без Swagger | Все основные пользовательские экраны есть во frontend | `frontend/src/pages/*`, `docs/demo-scenario.md` |

## Что считается закрытым

- Основной `demo flow` проходит автоматически.
- Build frontend проходит без ошибок.
- Для каждого требования, попавшего в источник разделов отчета, существует explanation с evidence.

## Что остается вне acceptance MVP

- Полноценный `iOS`-клиент.
- OCR сложных PDF/сканов.
- Интеграции с внешними государственными системами.
- Нагрузочное и security-тестирование production-уровня.
