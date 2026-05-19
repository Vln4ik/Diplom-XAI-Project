# GitHub Publication Status

## 1. Назначение документа

Этот документ фиксирует текущее состояние проекта с точки зрения публикации на GitHub:

- где опубликован репозиторий;
- какой commit сейчас является актуальным;
- что уже выложено;
- какие организационные ограничения ещё остаются.

## 2. Текущий статус

Проект опубликован на GitHub:

- repository: `https://github.com/Vln4ik/Diplom-XAI-Project`
- branch: `main`

Локальная ветка `main` должна быть синхронизирована с `origin/main` после каждого публикационного шага.

Актуальный commit проверяется командами:

```bash
git rev-parse HEAD
git rev-parse origin/main
git status -sb
```

## 3. Что уже опубликовано

В публичный репозиторий уже выложены:

- monorepo со структурой `backend`, `frontend`, `infra`, `docs`, `samples`;
- backend на `FastAPI + SQLAlchemy + Alembic + Celery + Redis + PostgreSQL + pgvector`;
- frontend на `React + TypeScript + Vite`;
- локальный AI-контур через `Ollama`;
- XAI, risk registry, report generation, exports, review-flow;
- document pipeline и OCR-контур;
- benchmark-suite для качества анализа;
- OCR benchmark;
- performance, load и stress baseline;
- CI workflow;
- подробная документация проекта.

Последний опубликованный commit проверяется через:

```bash
git log -1 --oneline origin/main
```

## 4. Текущие ограничения публикационного контура

Основной Git push работает через SSH deploy key:

- remote: `origin`
- URL: `git@github-xai-report-builder:Vln4ik/Diplom-XAI-Project.git`

При этом локальный `gh` CLI всё ещё не авторизован. Это не мешает обычному `git push`, но ограничивает операции, которые требуют GitHub API:

- создание Pull Request через CLI;
- управление Issues и Milestones через CLI;
- автоматическое изменение описания репозитория через CLI.

Для этих действий нужно выполнить:

```bash
gh auth login
```

## 5. Что стоит оформить дальше на GitHub

Следующие организационные улучшения:

- добавить GitHub Issues под оставшиеся этапы roadmap;
- оформить Milestones;
- добавить Release notes для текущего MVP;
- при необходимости добавить screenshots или demo video;
- обновить описание и topics репозитория.

## 6. Рекомендуемое описание репозитория

Рекомендуемая смысловая формулировка:

`Web-first XAI platform for evidence-grounded regulatory reporting with local AI, hybrid retrieval, OCR, and human-in-the-loop review.`

Ключевые теги:

- `xai`
- `llm`
- `retrieval`
- `fastapi`
- `react`
- `pgvector`
- `ollama`
- `ocr`
- `regtech`
- `document-ai`

## 7. Итоговый статус

Публикация проекта выполнена.

Оставшийся блокер относится не к коду и не к push, а к GitHub API workflow: для Pull Request, Issues, Milestones и управления metadata репозитория нужно авторизовать `gh`.
