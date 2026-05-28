# Архитектура системы

## 1. Назначение документа

Документ фиксирует текущую архитектуру `MVP 1` и направление её эволюции в `MVP 2`, `MVP 3` и `MVP 4`.

## 2. Архитектура `MVP 1`

### 2.1. Runtime-контур

Текущий runtime состоит из следующих компонентов:

- `frontend` — web-клиент на `React + Vite`
- `backend-api` — REST API на `FastAPI`
- `backend-worker` — `Celery` worker для обработки документов и отчётов
- `postgres` — транзакционные данные, full-text search и `pgvector`
- `redis` — broker/result backend и shared runtime state
- `filesystem storage` — исходные файлы и экспортные артефакты
- `ollama` — локальный AI runtime для embeddings и LLM
- `prometheus / grafana / alertmanager` — optional observability-профиль

Локальный AI runtime уже работает в profile-aware режиме:

- `baseline`
- `quality`
- `quality_plus`

### 2.2. Основные доменные контуры

- аутентификация и роли
- организации и участники
- документы и фрагменты
- требования и доказательства
- XAI-объяснения
- риски
- отчёты, версии и экспорты
- аудит и уведомления

## 3. Текущий прикладной pipeline

### 3.1. Документный pipeline

1. Пользователь загружает документ в контексте организации.
2. API сохраняет метаданные и файл.
3. В очередь уходит `document_process`.
4. Worker извлекает текст, дробит документ на фрагменты и индексирует их.
5. Фрагменты и embeddings сохраняются в `PostgreSQL`.

### 3.2. Аналитический pipeline

1. Пользователь создаёт отчёт и выбирает документы.
2. В очередь уходит `report_analyze`.
3. Система выделяет требования.
4. Система определяет применимость.
5. Система подбирает evidence.
6. Система рассчитывает `confidence`, `status`, `risk`.
7. Система сохраняет XAI-цепочку.
8. Система создаёт разделы отчёта и экспорты.

## 4. AI/XAI контур `MVP 1`

### 4.1. Что работает сейчас

- text-centric pipeline
- embeddings через локальную модель
- локальная LLM для генерации
- profile-aware выбор локальной embedding-модели и LLM
- гибридный retrieval
- rule-based applicability / confidence / risk
- сохранённый XAI-артефакт
- базовый OCR-контур для image-файлов и image-only `PDF`

### 4.2. Что не является частью `MVP 1`

- multimodal end-to-end reasoning
- layout-aware document vision
- domain fine-tuning
- production-grade neural reranker

## 5. Хранение данных

### 5.1. Где что хранится

- бизнес-сущности: `PostgreSQL`
- векторы фрагментов: `pgvector` в `PostgreSQL`
- исходные файлы: локальное файловое хранилище
- export-файлы: файловое хранилище + записи в БД
- task runtime state: `Redis`

### 5.2. Почему так устроено

- один транзакционный и retrieval-контур для MVP
- минимально необходимая инфраструктура
- локальная воспроизводимость стенда
- прозрачная связь `document -> fragment -> requirement -> evidence -> report`

## 6. Контур наблюдаемости `MVP 1`

Сейчас уже доступны:

- runtime metrics endpoint-ы
- Celery lifecycle diagnostics
- Redis-backed shared task metrics
- `Prometheus` scraping
- `Grafana` dashboard
- базовая маршрутизация alert-уведомлений через `Alertmanager`

Это достаточно для инженерного MVP, но ещё не равно полноценной production-эксплуатации.

## 7. Архитектурное развитие по версиям

## 7.1. `MVP 2`

Главные архитектурные усиления:

- более широкий `real_corpus` и benchmark-слой
- более сильный OCR / vision-контур
- более сильный стек AI-моделей
- более качественный evidence reranking
- контур оценки качества sections

Главный архитектурный переход:

- от базового text/OCR-контура к более сильному document-understanding контуру

## 7.2. `MVP 3`

Главные архитектурные усиления:

- enterprise workflow
- более зрелый процесс согласования
- внешние интеграции
- электронная подпись
- multi-regulator template layer

Главный архитектурный переход:

- от изолированного reporting tool к workflow-aware integration platform

## 7.3. `MVP 4`

Главные архитектурные усиления:

- CI/CD maturity
- security hardening
- deployment profiles
- retention / backup
- stress `10x+`
- production-grade observability

Главный архитектурный переход:

- от pilot-ready product к operationally mature platform

## 8. Короткий итог

Текущая архитектура уже достаточна для завершённого `MVP 1`.  
Следующий слой эволюции не связан с переделкой всего ядра, а строится как поэтапное усиление:

- сначала `AI quality`
- затем `процессный контур и integrations`
- затем `production maturity`
