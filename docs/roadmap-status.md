# Roadmap Status

## 1. Назначение этого документа

Этот документ фиксирует:

- что уже реализовано по roadmap
- что реализовано частично
- что сознательно отложено
- какие следующие шаги приоритетны

Он нужен для двух целей:

1. управлять разработкой проекта как инженерным планом
2. показать на защите, что MVP строился не хаотично, а поэтапно

## 2. Исходная roadmap-логика

Базовый roadmap проекта был разбит на фазы:

1. `Этап 0` — стартовая точка и scope
2. `Этап 1` — архитектурный каркас и данные
3. `Этап 2` — подсистема документов
4. `Этап 3` — реестр требований и матрица доказательств
5. `Этап 4` — XAI и риски
6. `Этап 5` — генерация и экспорт
7. `Этап 6` — web UI
8. `Этап 7` — мобильный контур
9. `Этап 8` — тестирование, приёмка, demo и метрики

## 3. Текущий статус по этапам

| Этап | Статус | Комментарий |
|---|---|---|
| `Этап 0` | `завершён` | scope MVP определён, web-first стратегия зафиксирована |
| `Этап 1` | `завершён` | backend каркас, доменная модель, auth, multi-tenant логика |
| `Этап 2` | `завершён на MVP-уровне` | загрузка и обработка документов работают |
| `Этап 3` | `завершён на MVP-уровне` | требования, evidence, matrix и ручной review реализованы |
| `Этап 4` | `завершён на MVP-уровне` | XAI, confidence, risks, explanations работают |
| `Этап 5` | `завершён на MVP-уровне` | generation, exports, versioning реализованы |
| `Этап 6` | `завершён на MVP-уровне` | web UI покрывает основной сценарий |
| `Этап 7` | `отложен сознательно` | нативный mobile/iOS не в критическом пути MVP |
| `Этап 8` | `частично завершён` | tests, acceptance, performance и load baseline уже есть, но остаются research-level расширения |

## 4. Что именно уже реализовано

## 4.1. Этап 0. Зафиксировать стартовую точку

Сделано:

- принято решение о `web-first MVP`
- определён основной регуляторный сценарий
- определён фокус на образовательной организации
- выделен новый monorepo-каркас вместо продолжения старого JSON-heavy прототипа как основной архитектуры

Результат:

- проект получил чёткий MVP scope

## 4.2. Этап 1. Архитектурный каркас и данные

Сделано:

- новый backend на `FastAPI + SQLAlchemy + Alembic`
- доменные сущности:
  - `User`
  - `Organization`
  - `OrganizationMember`
  - `Document`
  - `DocumentFragment`
  - `Requirement`
  - `Evidence`
  - `Explanation`
  - `Risk`
  - `Report`
  - `ReportSection`
  - `ReportVersion`
  - `Notification`
  - `AuditLog`
  - `ExportFile`
- аутентификация
- роли
- multi-tenant привязка данных к организации
- storage abstraction

Результат:

- backend стал прикладной системой, а не только исследовательским прототипом

## 4.3. Этап 2. Подсистема документов

Сделано:

- upload документов
- категории документов
- статусы обработки
- извлечение текста из:
  - `PDF`
  - `DOCX`
  - `XLSX`
  - `CSV`
  - `TXT`
  - `JSON`
- chunking на фрагменты
- хранение embeddings
- поиск по фрагментам
- фоновые задачи обработки через `Celery`

Результат:

- документы можно загружать, обрабатывать и использовать как базу для retrieval

## 4.4. Этап 3. Реестр требований и матрица доказательств

Сделано:

- requirement mining
- дедупликация части повторов
- категоризация требований
- определение применимости
- построение evidence matrix
- ручные операции по требованиям:
  - confirm
  - reject
  - edit
  - bulk update
  - refresh artifacts

Результат:

- пользователь работает уже не с “сырой LLM-выдачей”, а с управляемым реестром требований

## 4.5. Этап 4. XAI и модуль рисков

Сделано:

- persisted explanation entity
- logic chain
- evidence payload
- confidence
- recommended action
- risk registry
- назначения и закрытие рисков
- синхронизация explanation/risk после ручной правки требований

Результат:

- каждый важный вывод получил explainability layer

## 4.6. Этап 5. Генерация отчёта и экспорт

Сделано:

- pipeline `create -> analyze -> generate -> export`
- section generation
- versioning отчёта
- restore previous version
- export:
  - `DOCX`
  - `XLSX`
  - `ZIP`
  - `XAI HTML`

Результат:

- система выдаёт не только аналитику, но и конечный пользовательский артефакт

## 4.7. Этап 6. Web UI

Сделано:

- login
- dashboard
- organizations
- documents
- reports
- matrix
- requirements
- risks
- report editor
- explanations
- notifications
- audit

Результат:

- основной сценарий проходит без Swagger

## 4.8. Этап 8. Тестирование, приёмка и benchmark

Сделано:

- backend tests
- acceptance demo flow
- browser e2e
- performance baseline
- load baseline
- docs по demo и приёмке

Результат:

- система уже имеет не только функционал, но и проверяемый validation contour

## 5. Что реализовано частично

### 5.1. AI quality

Сейчас реализован рабочий локальный AI-контур, но он ещё не доведён до полноценного domain-tuned production quality.

Частично решено:

- local embeddings
- local LLM
- hybrid retrieval
- structured XAI

Ещё не доведено:

- domain fine-tuning
- calibration на реальных кейсах
- reranking quality
- formal precision/recall metrics

### 5.2. Performance and load

Сейчас есть:

- sequential performance baseline
- `2x` concurrency load baseline

Ещё нет:

- `3x+` stress профилей
- CPU/RAM системного профиля
- больших документных наборов
- separate comparison `fallback` vs `Ollama model`

## 6. Что сознательно отложено

### 6.1. Этап 7. Мобильный контур

Нативный мобильный клиент не является критическим блоком MVP, поэтому он отложен.

Причины:

- приоритет у web-first сценария
- важно сначала довести core domain logic
- мобильный контур без зрелого backend и XAI-логики малоценен

### 6.2. OCR и vision

Поддержка image-heavy сценариев и сканов отложена.

Причины:

- текущий MVP строится вокруг текстовых источников
- OCR и layout analysis сильно увеличивают техническую сложность

## 7. Следующие шаги по приоритету

### 7.1. Приоритет A. Документация, упаковка и публикация

Следующие прикладные шаги:

- собрать полный documentation pack
- описать стек, архитектуру, LLM/XAI метод
- формализовать roadmap status
- оформить репозиторий под публикацию
- выложить проект на GitHub

Текущий статус по этому блоку:

- documentation pack уже собран
- архитектурные и AI/XAI документы уже оформлены
- фактическая публикация пока упирается в `remote` и `gh auth`

### 7.2. Приоритет B. Экспериментальная и защитная часть

- оформить acceptance trace по ТЗ
- собрать связку “проблема -> решение -> метрики -> ограничения”
- зафиксировать статистические и инженерные результаты

### 7.3. Приоритет C. Следующее качество AI

- stronger local model
- better embeddings
- reranker
- richer requirement extraction
- более сильный reasoning layer по explanations

### 7.4. Приоритет D. Расширение функциональности

- OCR
- multi-regulator templates
- mobile contour
- внешние интеграции

## 8. Что именно уже можно показывать как результат

С практической точки зрения уже можно демонстрировать:

- локальный web-интерфейс
- загрузку и обработку документов
- поиск и retrieval
- анализ и построение реестра требований
- XAI explanations и risk registry
- генерацию отчёта
- экспорт и review-flow
- baseline по производительности и нагрузке

Это важно, потому что roadmap уже материализован не только в коде, но и в демонстрируемом пользовательском сценарии.

## 9. План развития после MVP

### 9.1. Краткосрочный горизонт

- опубликовать проект
- стабилизировать docs и packaging
- провести ещё 1-2 экспериментальных сценария
- при необходимости расширить benchmark

### 9.2. Среднесрочный горизонт

- усилить AI-качество
- ввести OCR/vision contour
- расширить число поддерживаемых типов отчётов
- добавить более зрелую observability и CI/CD

### 9.3. Долгосрочный горизонт

- multi-regulator platform
- production-grade role workflows
- template libraries
- stronger analytics and dashboards

## 10. Технические долги и ограничения

На текущий момент остаются такие объективные точки внимания:

- GitHub remote ещё не настроен
- `gh auth` не выполнен
- текущий Git worktree всё ещё содержит переход от старого прототипа к новому monorepo
- mobile contour не реализован
- OCR не реализован
- AI-качество пока ограничено lightweight local runtime

## 11. Честный итог по roadmap

Если оценивать проект прагматично, то сейчас у нас не “идея на бумаге”, а уже собранный:

- working backend
- working web UI
- working local AI contour
- working XAI layer
- working export pipeline
- working acceptance/performance/load validation contour

То есть roadmap в части MVP фактически реализован.

То, что осталось дальше, — это уже не сборка ядра с нуля, а:

- упаковка
- расширение качества
- масштабирование
- публикация
- развитие за пределы первого MVP-контура
